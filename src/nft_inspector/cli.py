from typing import Optional
import asyncio
import typer
from .client import NFTInspector


app = typer.Typer()


async def _inspect_async(
    contract_address: str,
    token_id: int,
    rpc_url: Optional[str],
    chain_id: int,
    analyze_media: bool,
):
    """Async implementation of inspect"""
    inspector = NFTInspector(rpc_url=rpc_url, chain_id=chain_id, analyze_media=analyze_media)
    
    token_info = await inspector.inspect_token(contract_address, token_id)

    return token_info


@app.command()
def inspect(
    contract_address: str,
    token_id: int,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    chain_id: int = typer.Option(1, help="Chain ID (default: 1 for Ethereum mainnet)"),
    analyze_media: bool = typer.Option(True, help="Analyze media URLs"),
):
    """Inspect an NFT and fetch its metadata"""
    token_info = asyncio.run(_inspect_async(contract_address, token_id, rpc_url, chain_id, analyze_media))
    typer.echo(token_info.model_dump_json(indent=4, exclude_unset=True))



async def _inspect_contract_async(
    contract_address: str,
    rpc_url: Optional[str],
    chain_id: int,
):
    """Async implementation of contract inspection"""
    inspector = NFTInspector(rpc_url=rpc_url, chain_id=chain_id)
    
    contract_info = await inspector.inspect_contract(contract_address)
    
    return contract_info


@app.command("contract-uri")
def contract_uri(
    contract_address: str,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    chain_id: int = typer.Option(1, help="Chain ID (default: 1 for Ethereum mainnet)")
):
    """Inspect contract metadata via contractURI"""
    contract_info = asyncio.run(_inspect_contract_async(contract_address, rpc_url, chain_id))

    import json
    # Convert ContractURI and ContractDataReport to dict for JSON serialization
    if contract_info["contract_metadata"]:
        contract_info["contract_metadata"] = contract_info["contract_metadata"].model_dump(exclude_unset=True)
    if contract_info["contract_data_report"]:
        contract_info["contract_data_report"] = contract_info["contract_data_report"].model_dump(exclude_unset=True)
    typer.echo(json.dumps(contract_info, indent=4, default=str))


if __name__ == "__main__":
    app()