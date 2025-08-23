import httpx
import json
from typing import Optional
from urllib.parse import urlparse

from .models import UrlInfo, TokenDataReport, ContractDataReport, NFTMetadata, ContractURI
from .types import MediaProtocol, GatewayLevel
from .data_uri_utils import DataURIParser
from .svg_analyzer import SvgAnalyzer
from .html_analyzer import HtmlAnalyzer
from .uri_parsers import URIResolver

def is_valid_json(json_string):
    try:
        json.loads(json_string)
        return True
    except (ValueError, TypeError):
        return False

class UrlAnalyzer:
    def __init__(self, timeout: float = 10.0, uri_resolver: Optional[URIResolver] = None):
        self.timeout = timeout
        self.uri_resolver = uri_resolver or URIResolver()
        self.svg_analyzer = None  # Lazy initialization to handle optional dependency
        self.html_analyzer = None  # Lazy initialization to handle optional dependency
    
    def _extract_protocol(self, url: str) -> MediaProtocol:
        """Extract protocol from URL"""
        if url.startswith("data:"):
            return MediaProtocol.DATA_URI
        
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        protocol_map = {
            "": MediaProtocol.NONE,
            "http": MediaProtocol.HTTP,
            "https": MediaProtocol.HTTPS,
            "ipfs": MediaProtocol.IPFS,
            "ipns": MediaProtocol.IPNS,
            "ar": MediaProtocol.ARWEAVE,
        }
        
        return protocol_map.get(scheme, MediaProtocol.UNKNOWN)
    
    def _determine_gateway_level(self, url: str, protocol: MediaProtocol) -> tuple[bool, Optional[GatewayLevel]]:
        """Determine gateway level and usage for URL"""
        if url.startswith('data:'):
            return False, None
        
        # Native protocol URLs are typically accessed via gateways
        if url.startswith('ipfs://'):
            return True, GatewayLevel.NATIVE
        if url.startswith('ar://'):
            return True, GatewayLevel.NATIVE
        
        # HTTP URLs could be direct hosting or gateway access
        if protocol in [MediaProtocol.HTTP, MediaProtocol.HTTPS]:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            
            # Check for IPFS gateways
            if '/ipfs/' in url or '/ipns/' in url:
                return True, GatewayLevel.IPFS_GATEWAY
            
            # Check for Arweave gateways
            if 'arweave' in url:
                return True, GatewayLevel.ARWEAVE_GATEWAY
            
            # Otherwise it's centralized hosting
            return False, GatewayLevel.CENTRALIZED
        
        # Other protocols are native
        return False, GatewayLevel.NATIVE
    
    def _analyze_data_uri(self, url: str) -> UrlInfo:
        """Analyze data URI"""
        try:
            data_info = DataURIParser.parse(url)
            
            return UrlInfo(
                url=url,
                protocol=MediaProtocol.DATA_URI,
                is_gateway=False,
                gateway_level=None,
                mime_type=data_info.media_type,
                size_bytes=data_info.size_bytes,
                accessible=True,
                encoding=data_info.encoding
            )
        except Exception as e:
            return UrlInfo(
                url=url,
                protocol=MediaProtocol.DATA_URI,
                is_gateway=False,
                gateway_level=None,
                accessible=False,
                error=str(e)
            )
    
    def _analyze_plain_data(self, url: str) -> UrlInfo:
        """Analyze plain data"""
        size_bytes = len(url)
        # try to guess mime type from plain text
        if '<svg' in url:
            mime_type = 'image/svg+xml'
        elif '<html' in url.lower() or '<!doctype html' in url.lower():
            mime_type = 'text/html'
        elif is_valid_json(url):
            mime_type = 'application/json'
        else:
            mime_type = 'text/plain'

        return UrlInfo(
            url=url,
            protocol=MediaProtocol.NONE,
            is_gateway=False,
            gateway_level=None,
            mime_type=mime_type,
            size_bytes=size_bytes,
            accessible=True
        )

    async def _analyze_http_url(self, url: str, protocol: MediaProtocol) -> UrlInfo:
        """Analyze HTTP/HTTPS URL"""
        
        # Determine gateway level and usage
        is_gateway, gateway_level = self._determine_gateway_level(url, protocol)
        
        # Convert IPFS/Arweave URLs to HTTP for analysis
        analysis_url = url
        if protocol == MediaProtocol.IPFS:
            analysis_url = url.replace("ipfs://", "https://ipfs.io/ipfs/")
        elif protocol == MediaProtocol.ARWEAVE:
            analysis_url = url.replace("ar://", "https://arweave.net/")
        
        try:            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Try HEAD request first
                response = await client.head(analysis_url)
                response.raise_for_status()
                
                mime_type = response.headers.get("content-type")
                size_bytes = None
                if "content-length" in response.headers:
                    size_bytes = int(response.headers["content-length"])
                else:
                    # Fallback to GET request if HEAD doesn't provide content-length
                    try:
                        get_response = await client.get(analysis_url)
                        get_response.raise_for_status()
                        size_bytes = len(get_response.content)
                        # Update mime_type from GET if it wasn't in HEAD
                        if not mime_type:
                            mime_type = get_response.headers.get("content-type")
                    except Exception:
                        # If GET fails, continue without size
                        pass
                
                return UrlInfo(
                    url=url,
                    protocol=protocol,
                    is_gateway=is_gateway,
                    gateway_level=gateway_level,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    accessible=True
                )
        except Exception as e:
            return UrlInfo(
                url=url,
                protocol=protocol,
                is_gateway=is_gateway,
                gateway_level=gateway_level,
                accessible=False,
                error=str(e)
            )
    
    async def analyze_media(self, url: str) -> UrlInfo:
        """Analyze a single media URL"""
        protocol = self._extract_protocol(url)

        
        if protocol == MediaProtocol.DATA_URI:
            url_info = self._analyze_data_uri(url)
        elif protocol == MediaProtocol.NONE:
            url_info = self._analyze_plain_data(url)
        else:
            url_info = await self._analyze_http_url(url, protocol)
        
        # Check if this is an SVG or HTML and analyze its dependencies
        if url_info.mime_type:
            mime_type_lower = url_info.mime_type.lower()
            if 'svg' in mime_type_lower:
                url_info.external_dependencies = await self._analyze_svg_dependencies(url, url_info)
            elif 'html' in mime_type_lower:
                url_info.external_dependencies = await self._analyze_html_dependencies(url, url_info)
        
        return url_info
    
    async def _analyze_svg_dependencies(self, url: str, url_info: UrlInfo):
        """Analyze SVG content for external dependencies"""
        try:
            # Lazy initialize SVG analyzer
            if self.svg_analyzer is None:
                self.svg_analyzer = SvgAnalyzer()
            
            # Get SVG content
            svg_content = await self._get_content(url, url_info)
            if not svg_content:
                return None
            
            # Analyze dependencies
            return await self.svg_analyzer.analyze_svg_content(svg_content, self)
            
        except Exception as e:
            # If SVG analysis fails, return None (no dependency info)
            print(f"SVG analysis failed for {url}: {e}")
            return None
    
    async def _get_content(self, url: str, url_info: UrlInfo) -> Optional[str]:
        """Get content from URL using the URI resolver"""
        try:
            protocol = url_info.protocol
            
            if protocol == MediaProtocol.NONE:
                # Direct content (plain text/SVG/HTML)
                return url
            else:
                # Use URI resolver for all other schemes
                return await self.uri_resolver.resolve(url)
                    
        except Exception as e:
            print(f"Failed to get content for {url}: {e}")
            return None
    
    async def _analyze_html_dependencies(self, url: str, url_info: UrlInfo):
        """Analyze HTML content for external dependencies"""
        try:
            # Lazy initialize HTML analyzer
            if self.html_analyzer is None:
                self.html_analyzer = HtmlAnalyzer()
            
            # Get HTML content
            html_content = await self._get_content(url, url_info)
            if not html_content:
                return None
            
            # Analyze dependencies
            return await self.html_analyzer.analyze_html_content(html_content, self)
            
        except Exception as e:
            # If HTML analysis fails, return None (no dependency info)
            print(f"HTML analysis failed for {url}: {e}")
            return None
    
    
    async def analyze(self, token_uri: str, metadata: NFTMetadata) -> TokenDataReport:
        """Analyze all media URLs in metadata"""
        report = TokenDataReport(token_uri=await self.analyze_media(token_uri))

        # iterate optional fields
        for field_name, field_info in TokenDataReport.model_fields.items():
            if field_info.is_required() or (field_value := getattr(metadata, field_name)) is None:
                continue
            setattr(report, field_name, await self.analyze_media(field_value))
        
        return report
    
    async def analyze_contract(self, contract_uri: str, metadata: ContractURI) -> ContractDataReport:
        """Analyze all media URLs in contract metadata"""
        report = ContractDataReport(contract_uri=await self.analyze_media(contract_uri))
        
        # iterate optional fields
        for field_name, field_info in ContractDataReport.model_fields.items():
            if field_info.is_required() or (field_value := getattr(metadata, field_name)) is None:
                continue
            setattr(report, field_name, await self.analyze_media(field_value))
        
        return report