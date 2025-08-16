import base64
import json
from typing import Dict, Any, Tuple, Optional
from urllib.parse import unquote
from .types import DataEncoding


class DataURIInfo:
    """Information extracted from a data URI"""
    def __init__(self, 
                 media_type: str, 
                 encoding: DataEncoding, 
                 raw_data: str, 
                 decoded_data: bytes):
        self.media_type = media_type
        self.encoding = encoding
        self.raw_data = raw_data
        self.decoded_data = decoded_data
        self.size_bytes = len(decoded_data)
    
    def as_text(self) -> str:
        """Get decoded data as text"""
        return self.decoded_data.decode('utf-8')
    
    def as_json(self) -> Dict[str, Any]:
        """Parse decoded data as JSON"""
        return json.loads(self.as_text())


class DataURIParser:
    """Utility class for parsing data URIs"""
    
    @staticmethod
    def parse(uri: str) -> DataURIInfo:
        """Parse a data URI and return structured information"""
        if not uri.startswith("data:"):
            raise ValueError("Invalid data URI")
        
        # Parse data URI: data:[<mediatype>][;base64],<data>
        header, data = uri.split(",", 1)
        header_parts = header.replace("data:", "").split(";")
        media_type = header_parts[0] if header_parts[0] else "text/plain"
        # maybe use mimetypes.guess_type(url)[0]
        
        # Determine encoding and decode data
        if "base64" in header_parts:
            encoding = DataEncoding.BASE64
            decoded_data = base64.b64decode(data)
        elif "%" in data:
            encoding = DataEncoding.PERCENT
            decoded_text = unquote(data)
            decoded_data = decoded_text.encode('utf-8')
        else:
            encoding = DataEncoding.PLAIN
            decoded_data = data.encode('utf-8')
        
        return DataURIInfo(media_type, encoding, data, decoded_data)