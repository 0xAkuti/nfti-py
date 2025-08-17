from typing import Optional
import asyncio
import typer
from .client import NFTInspector


app = typer.Typer()


async def _inspect_async(
    contract_address: str,
    token_id: int,
    rpc_url: Optional[str],
    output: str,
    analyze_media: bool,
):
    """Async implementation of inspect"""
    inspector = NFTInspector(rpc_url=rpc_url, analyze_media=analyze_media)
    
    token_info = await inspector.inspect_token(contract_address, token_id)
    
    return token_info


@app.command()
def inspect(
    contract_address: str,
    token_id: int,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    output: str = typer.Option("pretty", help="Output format", rich_help_panel="Output"),
    analyze_media: bool = typer.Option(True, help="Analyze media URLs"),
):
    """Inspect an NFT and fetch its metadata"""
    token_info = asyncio.run(_inspect_async(contract_address, token_id, rpc_url, output, analyze_media))
    
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
            


if __name__ == "__main__":
    app()