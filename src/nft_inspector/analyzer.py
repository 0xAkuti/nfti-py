import httpx
from urllib.parse import urlparse

from .models import UrlInfo, TokenDataReport, NFTMetadata
from .types import MediaProtocol


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
            # Parse data URI: data:[<mediatype>][;base64],<data>
            if not url.startswith("data:"):
                raise ValueError("Not a data URI")
            
            header, data = url.split(",", 1)
            mediatype = header.replace("data:", "").split(";")[0]
            
            # Estimate size (base64 encoded data is ~1.33x original size)
            if ";base64" in header:
                estimated_size = len(data) * 3 // 4
            else:
                estimated_size = len(data)
            
            return UrlInfo(
                url=url,
                protocol=MediaProtocol.DATA_URI,
                mime_type=mediatype or None,
                size_bytes=estimated_size,
                accessible=True
            )
        except Exception as e:
            return UrlInfo(
                url=url,
                protocol=MediaProtocol.DATA_URI,
                accessible=False,
                error=str(e)
            )
    
    def _analyze_http_url(self, url: str, protocol: MediaProtocol) -> UrlInfo:
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
            with httpx.Client(timeout=self.timeout) as client:
                response = client.head(analysis_url)
                response.raise_for_status()
                
                mime_type = response.headers.get("content-type")
                size_bytes = None
                if "content-length" in response.headers:
                    size_bytes = int(response.headers["content-length"])
                
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
    
    def analyze_media(self, url: str) -> UrlInfo:
        """Analyze a single media URL"""
        protocol = self._extract_protocol(url)

        
        if protocol == MediaProtocol.DATA_URI:
            return self._analyze_data_uri(url)
        else:
            return self._analyze_http_url(url, protocol)
    
    def analyze(self, token_uri: str, metadata: NFTMetadata) -> TokenDataReport:
        """Analyze all media URLs in metadata"""
        report = TokenDataReport(token_uri=self.analyze_media(token_uri))
        
        if metadata.image:
            report.image = self.analyze_media(str(metadata.image))
        
        if metadata.image_data:
            report.image_data = self.analyze_media(str(metadata.image_data))
        
        if metadata.animation_url:
            report.animation_url = self.analyze_media(str(metadata.animation_url))
        
        if metadata.external_url:
            report.external_url = self.analyze_media(str(metadata.external_url))
        
        return report