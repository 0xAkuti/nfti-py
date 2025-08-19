from typing import Optional, Any, Union
import asyncio
import json
import typer
from .client import NFTInspector


app = typer.Typer()


def truncate_json_values(obj: Any, max_length: int = 100) -> Any:
    """
    Recursively truncate long string values in JSON structure
    
    Args:
        obj: The object to process (dict, list, string, etc.)
        max_length: Maximum length for string values (0 = no truncation)
        
    Returns:
        Processed object with truncated string values
    """
    if max_length <= 0:
        return obj
        
    if isinstance(obj, dict):
        return {k: truncate_json_values(v, max_length) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [truncate_json_values(item, max_length) for item in obj]
    elif isinstance(obj, str) and len(obj) > max_length:
        # Format: beginning...end
        if max_length <= 6:  # Too short for meaningful truncation
            return obj[:max_length] + "..."
        
        # Reserve 3 characters for "..."
        remaining = max_length - 3
        half = remaining // 2
        return f"{obj[:half]}...{obj[-half:]}"
    else:
        return obj


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
    max_length: int = typer.Option(100, help="Maximum length for string values in output (0 = no truncation)"),
):
    """Inspect an NFT and fetch its metadata"""
    token_info = asyncio.run(_inspect_async(contract_address, token_id, rpc_url, chain_id, analyze_media))
    
    # Convert to dict and truncate long values
    data = json.loads(token_info.model_dump_json(exclude_unset=True)) # to make sure all data is reduced to basic types
    truncated_data = truncate_json_values(data, max_length)
    
    typer.echo(json.dumps(truncated_data, indent=4, default=str))



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
    chain_id: int = typer.Option(1, help="Chain ID (default: 1 for Ethereum mainnet)"),
    max_length: int = typer.Option(100, help="Maximum length for string values in output (0 = no truncation)"),
):
    """Inspect contract metadata via contractURI"""
    contract_info = asyncio.run(_inspect_contract_async(contract_address, rpc_url, chain_id))

    # Convert ContractURI and ContractDataReport to dict for JSON serialization
    if contract_info["contract_metadata"]:
        contract_info["contract_metadata"] = contract_info["contract_metadata"].model_dump(exclude_unset=True)
    if contract_info["contract_data_report"]:
        contract_info["contract_data_report"] = contract_info["contract_data_report"].model_dump(exclude_unset=True)
    
    # Truncate long values
    truncated_data = truncate_json_values(contract_info, max_length)
    
    typer.echo(json.dumps(truncated_data, indent=4, default=str))


@app.command("supported-interfaces")
def supported_interfaces(
    contract_address: str,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    chain_id: int = typer.Option(1, help="Chain ID (default: 1 for Ethereum mainnet)"),
):
    """Get supported interfaces for a contract"""
    inspector = NFTInspector(rpc_url=rpc_url, chain_id=chain_id)
    interfaces = asyncio.run(inspector.get_supported_interfaces(contract_address))
    typer.echo(json.dumps(interfaces, indent=4, default=str))


@app.command("proxy-info")

def proxy_info(
    contract_address: str,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    chain_id: int = typer.Option(1, help="Chain ID (default: 1 for Ethereum mainnet)"),
):
    """Get proxy information for a contract"""
    inspector = NFTInspector(rpc_url=rpc_url, chain_id=chain_id)
    proxy_info = asyncio.run(inspector.get_proxy_info(contract_address))
    typer.echo(json.dumps(proxy_info.model_dump(exclude_unset=True), indent=4, default=str))


if __name__ == "__main__":
    app()