from typing import Optional, List, Union
from pydantic import BaseModel, Field


class RpcEndpoint(BaseModel):
    url: str
    tracking: Optional[str] = None
    isOpenSource: Optional[bool] = None


class NativeCurrency(BaseModel):
    name: str
    symbol: str
    decimals: int


class Explorer(BaseModel):
    name: str
    url: str
    standard: Optional[str] = None
    icon: Optional[str] = None


class ENS(BaseModel):
    registry: str


class ChainInfo(BaseModel):
    chainId: int
    name: str
    shortName: str
    chain: Optional[str] = None
    networkId: Optional[int] = None
    nativeCurrency: NativeCurrency
    rpc: List[Union[RpcEndpoint, str]]
    explorers: Optional[List[Explorer]] = None
    chainSlug: Optional[str] = None
    icon: Optional[str] = None
    isTestnet: Optional[bool] = None
    infoURL: Optional[str] = None
    slip44: Optional[int] = None
    ens: Optional[ENS] = None
    faucets: Optional[List[str]] = Field(default_factory=list)
    
    class Config:
        extra = "allow"