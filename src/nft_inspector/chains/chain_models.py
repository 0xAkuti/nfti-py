from typing import Any, Optional, List, Union
from pydantic import BaseModel, Field, field_validator


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
    icon: Optional[Any] = None


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
    icon: Optional[Any] = None
    isTestnet: Optional[bool] = None
    infoURL: Optional[str] = None
    slip44: Optional[int] = None
    ens: Optional[ENS] = None
    faucets: Optional[List[str]] = Field(default_factory=list)

    @field_validator("icon", mode="before")
    @classmethod
    def _coerce_icon(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return v.get("url")
        return v

    @field_validator("faucets", mode="before")
    @classmethod
    def _coerce_faucets(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [v]
        return v

    class Config:
        extra = "allow"