import re
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from .models import SvgExternalResource, SvgDependencyReport, UrlInfo
from .types import MediaProtocol


class SvgAnalyzer:
    """Analyzes SVG content for external dependencies"""
    
    def __init__(self):
        if not BS4_AVAILABLE:
            raise ImportError(
                "beautifulsoup4 and lxml are required for SVG analysis. "
                "Install with: pip install beautifulsoup4 lxml"
            )
    
    async def analyze_svg_content(self, svg_content: str, url_analyzer) -> SvgDependencyReport:
        """
        Analyze SVG content for external dependencies
        
        Args:
            svg_content: The SVG content as a string
            url_analyzer: UrlAnalyzer instance for analyzing found URLs
            
        Returns:
            SvgDependencyReport with dependency analysis
        """
        external_resources = []
        
        try:
            soup = self._parse_svg_content(svg_content)
            urls = self._extract_external_urls(soup)
            
            # Analyze each found URL
            for url, element_type, attribute in urls:
                try:
                    url_info = await url_analyzer.analyze_media(url)
                    external_resource = SvgExternalResource(
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
                    external_resource = SvgExternalResource(
                        url=url,
                        element_type=element_type,
                        attribute=attribute,
                        url_info=url_info
                    )
                    external_resources.append(external_resource)
        
        except Exception as e:
            # If SVG parsing fails, return a basic report
            return SvgDependencyReport(
                is_fully_onchain=False,
                min_protocol_score=0,
                min_protocol=MediaProtocol.UNKNOWN,
                external_resources=[],
                total_dependencies=0
            )
        
        return self._calculate_dependency_score(external_resources)
    
    def _parse_svg_content(self, svg_content: str) -> BeautifulSoup:
        """Parse SVG content using BeautifulSoup with XML parser"""
        return BeautifulSoup(svg_content, features="xml")
    
    def _extract_external_urls(self, soup: BeautifulSoup) -> List[tuple[str, str, str]]:
        """
        Extract all external URLs from SVG content
        
        Returns:
            List of tuples: (url, element_type, attribute)
        """
        urls = []
        
        # Extract from href and xlink:href attributes
        for attr in ['href', 'xlink:href']:
            elements = soup.find_all(attrs={attr: True})
            for element in elements:
                url = element.get(attr)
                if self._is_external_url(url):
                    urls.append((url, element.name, attr))
        
        # Extract from src attributes (for script elements)
        src_elements = soup.find_all(attrs={'src': True})
        for element in src_elements:
            url = element.get('src')
            if self._is_external_url(url):
                urls.append((url, element.name, 'src'))
        
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
    
    def _calculate_dependency_score(self, external_resources: List[SvgExternalResource]) -> SvgDependencyReport:
        """
        Calculate the dependency score based on the weakest link principle
        
        Args:
            external_resources: List of external resources found
            
        Returns:
            SvgDependencyReport with calculated scores
        """
        if not external_resources:
            return SvgDependencyReport(
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
        
        return SvgDependencyReport(
            is_fully_onchain=(min_score >= 10),  # DATA_URI or better
            min_protocol_score=int(min_score),
            min_protocol=min_protocol,
            external_resources=external_resources,
            total_dependencies=len(external_resources)
        )