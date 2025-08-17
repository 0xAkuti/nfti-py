import httpx
import urllib.parse
import json
from urllib.parse import urlparse

from .models import UrlInfo, TokenDataReport, ContractDataReport, NFTMetadata, ContractURI
from .types import MediaProtocol
from .data_uri_utils import DataURIParser

def is_valid_json(json_string):
    try:
        json.loads(json_string)
        return True
    except (ValueError, TypeError):
        return False

class UrlAnalyzer:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
    
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
    
    def _analyze_data_uri(self, url: str) -> UrlInfo:
        """Analyze data URI"""
        try:
            data_info = DataURIParser.parse(url)
            
            return UrlInfo(
                url=url,
                protocol=MediaProtocol.DATA_URI,
                mime_type=data_info.media_type,
                size_bytes=data_info.size_bytes,
                accessible=True,
                encoding=data_info.encoding
            )
        except Exception as e:
            return UrlInfo(
                url=url,
                protocol=MediaProtocol.DATA_URI,
                accessible=False,
                error=str(e)
            )
    
    def _analyze_plain_data(self, url: str) -> UrlInfo:
        """Analyze plain data"""
        size_bytes = len(url)
        # try to guess mime type from plain text
        if '<svg' in url:
            mime_type = 'image/svg+xml'
        elif is_valid_json(url):
            mime_type = 'application/json'
        else:
            mime_type = 'text/plain'

        return UrlInfo(
            url=url,
            protocol=MediaProtocol.NONE,
            mime_type=mime_type,
            size_bytes=size_bytes,
            accessible=True
        )

    async def _analyze_http_url(self, url: str, protocol: MediaProtocol) -> UrlInfo:
        """Analyze HTTP/HTTPS URL"""

        is_gateway = False
        # Convert IPFS/Arweave URLs to HTTP for analysis
        analysis_url = url
        if protocol == MediaProtocol.IPFS:
            analysis_url = url.replace("ipfs://", "https://ipfs.io/ipfs/")
        elif protocol == MediaProtocol.ARWEAVE:
            analysis_url = url.replace("ar://", "https://arweave.net/")
        elif protocol == MediaProtocol.HTTP or protocol == MediaProtocol.HTTPS:
            # check if the url is a gateway
            is_gateway = 'ipfs' in url or 'arweave' in url
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
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    accessible=True
                )
        except Exception as e:
            return UrlInfo(
                url=url,
                protocol=protocol,
                is_gateway=is_gateway,
                accessible=False,
                error=str(e)
            )
    
    async def analyze_media(self, url: str) -> UrlInfo:
        """Analyze a single media URL"""
        protocol = self._extract_protocol(url)

        
        if protocol == MediaProtocol.DATA_URI:
            return self._analyze_data_uri(url)
        elif protocol == MediaProtocol.NONE:
            return self._analyze_plain_data(url)
        else:
            return await self._analyze_http_url(url, protocol)
    
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