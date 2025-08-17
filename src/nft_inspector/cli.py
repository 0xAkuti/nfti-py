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
    output: str = typer.Option("pretty", help="Output format", rich_help_panel="Output"),
    analyze_media: bool = typer.Option(True, help="Analyze media URLs"),
):
    """Inspect an NFT and fetch its metadata"""
    token_info = asyncio.run(_inspect_async(contract_address, token_id, rpc_url, chain_id, analyze_media))
    
    if output == "json":
        typer.echo(token_info.model_dump_json(indent=2))
    else:
        typer.echo(f"Contract: {token_info.contract_address}")
        typer.echo(f"Token ID: {token_info.token_id}")
        typer.echo(f"Token URI: {token_info.token_uri or 'Not found'}")
        
        if token_info.metadata:
            typer.echo("\nMetadata:")
            typer.echo(f"  Name: {token_info.metadata.name or 'N/A'}")
            typer.echo(f"  Description: {token_info.metadata.description or 'N/A'}")
            typer.echo(f"  Image: {token_info.metadata.image or 'N/A'}")
            
            if token_info.metadata.attributes:
                typer.echo("  Attributes:")
                for attr in token_info.metadata.attributes:
                    typer.echo(f"    {attr.trait_type}: {attr.value}")
        else:
            typer.echo("\nMetadata: Not available")
        
        if token_info.data_report:
            typer.echo("\nMedia Analysis:")
            
            def show_media_info(name: str, media_info):
                if media_info:
                    typer.echo(f"  {name}:")
                    typer.echo(f"    Protocol: {media_info.protocol}")
                    typer.echo(f"    MIME Type: {media_info.mime_type or 'Unknown'}")
                    typer.echo(f"    Size: {media_info.size_bytes if media_info.size_bytes else 'Unknown'} bytes")
                    typer.echo(f"    Accessible: {'Yes' if media_info.accessible else 'No'}")
                    if media_info.error:
                        typer.echo(f"    Error: {media_info.error}")
            
            show_media_info("Image", token_info.data_report.image)
            show_media_info("Animation", token_info.data_report.animation_url)
            show_media_info("External URL", token_info.data_report.external_url)
            show_media_info("Image Data", token_info.data_report.image_data)
        
        # Show contract metadata if available
        if token_info.contract_metadata:
            typer.echo("\nContract Metadata:")
            typer.echo(f"  Name: {token_info.contract_metadata.name}")
            if token_info.contract_metadata.description:
                typer.echo(f"  Description: {token_info.contract_metadata.description}")
            if token_info.contract_metadata.symbol:
                typer.echo(f"  Symbol: {token_info.contract_metadata.symbol}")
            if token_info.contract_metadata.external_link:
                typer.echo(f"  External Link: {token_info.contract_metadata.external_link}")


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
    output: str = typer.Option("pretty", help="Output format", rich_help_panel="Output"),
):
    """Inspect contract metadata via contractURI"""
    contract_info = asyncio.run(_inspect_contract_async(contract_address, rpc_url, chain_id))
    
    if output == "json":
        import json
        # Convert ContractURI to dict for JSON serialization
        if contract_info["contract_metadata"]:
            contract_info["contract_metadata"] = contract_info["contract_metadata"].model_dump()
        typer.echo(json.dumps(contract_info, indent=2, default=str))
    else:
        typer.echo(f"Contract: {contract_info['contract_address']}")
        typer.echo(f"Contract URI: {contract_info['contract_uri'] or 'Not found'}")
        
        if contract_info["contract_metadata"]:
            metadata = contract_info["contract_metadata"]
            typer.echo("\nContract Metadata:")
            typer.echo(f"  Name: {metadata.name}")
            if metadata.description:
                typer.echo(f"  Description: {metadata.description}")
            if metadata.symbol:
                typer.echo(f"  Symbol: {metadata.symbol}")
            if metadata.external_link:
                typer.echo(f"  External Link: {metadata.external_link}")
            if metadata.image:
                typer.echo(f"  Image: {metadata.image}")
            if metadata.banner_image:
                typer.echo(f"  Banner Image: {metadata.banner_image}")
            if metadata.featured_image:
                typer.echo(f"  Featured Image: {metadata.featured_image}")
            if metadata.seller_fee_basis_points is not None:
                typer.echo(f"  Seller Fee: {metadata.seller_fee_basis_points / 100}%")
            if metadata.fee_recipient:
                typer.echo(f"  Fee Recipient: {metadata.fee_recipient}")
            if metadata.collaborators:
                typer.echo(f"  Collaborators: {', '.join(str(addr) for addr in metadata.collaborators)}")
        else:
            typer.echo("\nContract Metadata: Not available")


if __name__ == "__main__":
    app()