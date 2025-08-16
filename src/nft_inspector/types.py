from pydantic import AnyUrl
from pydantic.networks import UrlConstraints


class TokenURI(AnyUrl):
    """A type that will accept token URIs with various schemes"""
    
    _constraints = UrlConstraints(
        allowed_schemes=['http', 'https', 'ipfs', 'ipns', 'ar', 'data']
    )