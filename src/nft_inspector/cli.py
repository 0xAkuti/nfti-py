from typing import Optional
import typer
from .client import NFTInspector


app = typer.Typer()


@app.command()
def inspect(
    contract_address: str,
    token_id: int,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    output: str = typer.Option("pretty", help="Output format", rich_help_panel="Output"),
):
    """Inspect an NFT and fetch its metadata"""
    inspector = NFTInspector(rpc_url=rpc_url)
    
    try:
        token_info = inspector.inspect_token(contract_address, token_id)
        
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
                
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Abort()


if __name__ == "__main__":
    app()