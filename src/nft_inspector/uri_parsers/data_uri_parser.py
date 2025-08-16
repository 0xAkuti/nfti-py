import json
import base64
from typing import Dict, Any
from .base import URIParser


class DataURIParser(URIParser):
    def can_handle(self, uri: str) -> bool:
        return uri.startswith("data:")
    
    def parse(self, uri: str) -> Dict[str, Any]:
        if not uri.startswith("data:application/json;base64,"):
            raise ValueError("Only base64 encoded JSON data URIs are supported")
        
        base64_data = uri.split("data:application/json;base64,")[1]
        decoded_data = base64.b64decode(base64_data).decode('utf-8')
        return json.loads(decoded_data)