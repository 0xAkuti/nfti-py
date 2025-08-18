import re
from typing import List
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from .models import ExternalResource, DependencyReport, UrlInfo
from .types import MediaProtocol


class HtmlAnalyzer:
    """Analyzes HTML content for external dependencies"""
    
    def __init__(self):
        if not BS4_AVAILABLE:
            raise ImportError(
                "beautifulsoup4 is required for HTML analysis. "
                "Install with: pip install beautifulsoup4"
            )
    
    async def analyze_html_content(self, html_content: str, url_analyzer) -> DependencyReport:
        """
        Analyze HTML content for external dependencies
        
        Args:
            html_content: The HTML content as a string
            url_analyzer: UrlAnalyzer instance for analyzing found URLs
            
        Returns:
            DependencyReport with dependency analysis
        """
        external_resources = []
        
        try:
            soup = self._parse_html_content(html_content)
            urls = self._extract_external_urls(soup)
            
            # Analyze each found URL
            for url, element_type, attribute in urls:
                try:
                    url_info = await url_analyzer.analyze_media(url)
                    external_resource = ExternalResource(
                        url=url,
                        element_type=element_type,
                        attribute=attribute,
                        url_info=url_info
                    )
                    external_resources.append(external_resource)
                except Exception as e:
                    # Create a failed UrlInfo for the resource
                    url_info = UrlInfo(
                        url=url,
                        protocol=MediaProtocol.UNKNOWN,
                        accessible=False,
                        error=str(e)
                    )
                    external_resource = ExternalResource(
                        url=url,
                        element_type=element_type,
                        attribute=attribute,
                        url_info=url_info
                    )
                    external_resources.append(external_resource)
        
        except Exception as e:
            # If HTML parsing fails, return a basic report
            return DependencyReport(
                is_fully_onchain=False,
                min_protocol_score=0,
                min_protocol=MediaProtocol.UNKNOWN,
                external_resources=[],
                total_dependencies=0
            )
        
        return self._calculate_dependency_score(external_resources)
    
    def _parse_html_content(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content using BeautifulSoup with HTML parser"""
        return BeautifulSoup(html_content, features="html.parser")
    
    def _extract_external_urls(self, soup: BeautifulSoup) -> List[tuple[str, str, str]]:
        """
        Extract all external URLs from HTML content
        
        Returns:
            List of tuples: (url, element_type, attribute)
        """
        urls = []
        
        # Define HTML elements and their URL attributes
        url_attributes = {
            'img': ['src'],
            'script': ['src'],
            'link': ['href'],
            'iframe': ['src'],
            'embed': ['src'],
            'object': ['data'],
            'video': ['src', 'poster'],
            'audio': ['src'],
            'source': ['src'],
        }
        
        # Extract URLs from elements with URL attributes
        for element_name, attributes in url_attributes.items():
            elements = soup.find_all(element_name)
            for element in elements:
                for attr in attributes:
                    url = element.get(attr)
                    if url and self._is_external_url(url):
                        urls.append((url, element_name, attr))
        
        # Extract URLs from CSS content in style elements and attributes
        css_urls = self._extract_css_urls(soup)
        urls.extend(css_urls)
        
        return urls
    
    def _extract_css_urls(self, soup: BeautifulSoup) -> List[tuple[str, str, str]]:
        """Extract URLs from CSS content in style elements and attributes"""
        urls = []
        
        # Extract from <style> elements
        style_elements = soup.find_all('style')
        for style_element in style_elements:
            if style_element.string:
                css_urls = self._find_urls_in_css(style_element.string)
                for url in css_urls:
                    urls.append((url, 'style', 'css-content'))
        
        # Extract from style attributes
        styled_elements = soup.find_all(attrs={'style': True})
        for element in styled_elements:
            style_content = element.get('style')
            css_urls = self._find_urls_in_css(style_content)
            for url in css_urls:
                urls.append((url, element.name, 'style-attribute'))
        
        return urls
    
    def _find_urls_in_css(self, css_content: str) -> List[str]:
        """Find URLs in CSS content using regex"""
        urls = []
        
        # Match url() functions in CSS
        url_pattern = r'url\s*\(\s*["\']?([^"\')\s]+)["\']?\s*\)'
        matches = re.findall(url_pattern, css_content, re.IGNORECASE)
        
        for match in matches:
            if self._is_external_url(match):
                urls.append(match)
        
        # Match @import statements
        import_pattern = r'@import\s+["\']([^"\']+)["\']'
        import_matches = re.findall(import_pattern, css_content, re.IGNORECASE)
        
        for match in import_matches:
            if self._is_external_url(match):
                urls.append(match)
        
        return urls
    
    def _is_external_url(self, url: str) -> bool:
        """
        Check if a URL is external (not a fragment identifier)
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is external, False if it's a fragment or relative reference
        """
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # Skip fragment identifiers (e.g., "#myId")
        if url.startswith('#'):
            return False
        
        # Skip empty URLs
        if not url:
            return False
        
        # Skip javascript: and mailto: URLs
        if url.startswith(('javascript:', 'mailto:')):
            return False
        
        # Parse URL to check if it has a scheme
        parsed = urlparse(url)
        
        # Consider URLs with schemes as external
        if parsed.scheme:
            return True
        
        # Consider relative URLs with paths as potentially external
        # (they could reference external resources)
        if parsed.path and not parsed.path.startswith('#'):
            return True
        
        return False
    
    def _calculate_dependency_score(self, external_resources: List[ExternalResource]) -> DependencyReport:
        """
        Calculate the dependency score based on the weakest link principle
        
        Args:
            external_resources: List of external resources found
            
        Returns:
            DependencyReport with calculated scores
        """
        if not external_resources:
            return DependencyReport(
                is_fully_onchain=True,
                min_protocol_score=10,  # No external dependencies = fully on-chain
                min_protocol=None,
                external_resources=[],
                total_dependencies=0
            )
        
        # Find the minimum protocol score (weakest link)
        min_score = float('inf')
        min_protocol = None
        
        for resource in external_resources:
            protocol = resource.url_info.protocol
            score = protocol.get_score()
            
            if score < min_score:
                min_score = score
                min_protocol = protocol
        
        # Convert infinity to 0 if no valid scores found
        if min_score == float('inf'):
            min_score = 0
            min_protocol = MediaProtocol.UNKNOWN
        
        return DependencyReport(
            is_fully_onchain=(min_score >= 10),  # DATA_URI or better
            min_protocol_score=int(min_score),
            min_protocol=min_protocol,
            external_resources=external_resources,
            total_dependencies=len(external_resources)
        )