from typing import Dict, Any, List, Optional
from .base import URIParser
from .http_parser import HTTPParser
from .ipfs_parser import IPFSParser
from .data_uri_parser import DataURIParser
from .arweave_parser import ArweaveParser


class URIResolver:
    def __init__(self, parsers: Optional[List[URIParser]] = None):
        if parsers is None:
            self.parsers = [
                DataURIParser(),
                IPFSParser(),
                ArweaveParser(),
                HTTPParser(),
            ]
        else:
            self.parsers = parsers
    
    def resolve(self, uri: str) -> Dict[str, Any]:
        for parser in self.parsers:
            if parser.can_handle(uri):
                return parser.parse(uri)
        
        raise ValueError(f"No parser available for URI: {uri}")