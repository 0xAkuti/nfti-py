from typing import Dict, Any
from .base import URIParser
from ..data_uri_utils import DataURIParser as DataURIUtility


class DataURIParser(URIParser):
    def can_handle(self, uri: str) -> bool:
        return uri.startswith("data:")
    
    def parse(self, uri: str) -> Dict[str, Any]:
        data_info = DataURIUtility.parse(uri)
        return data_info.as_json()