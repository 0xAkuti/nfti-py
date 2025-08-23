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
    analyze_trust: bool,
):
    """Async implementation of inspect"""
    inspector = NFTInspector(rpc_url=rpc_url, chain_id=chain_id, analyze_media=analyze_media, analyze_trust=analyze_trust)
    
    token_info = await inspector.inspect_token(contract_address, token_id)

    return token_info


@app.command()
def inspect(
    contract_address: str,
    token_id: int,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    chain_id: int = typer.Option(1, help="Chain ID (default: 1 for Ethereum mainnet)"),
    analyze_media: bool = typer.Option(True, help="Analyze media URLs"),
    analyze_trust: bool = typer.Option(True, help="Analyze trust and permanence"),
    max_length: int = typer.Option(100, help="Maximum length for string values in output (0 = no truncation)"),
):
    """Inspect an NFT and fetch its metadata"""
    token_info = asyncio.run(_inspect_async(contract_address, token_id, rpc_url, chain_id, analyze_media, analyze_trust))
    
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

@app.command("access-control")
def access_control(
    contract_address: str,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    chain_id: int = typer.Option(1, help="Chain ID (default: 1 for Ethereum mainnet)"),
):
    """Get access control information for a contract"""
    inspector = NFTInspector(rpc_url=rpc_url, chain_id=chain_id)
    access_control_info = asyncio.run(inspector.get_access_control_info(contract_address))
    typer.echo(json.dumps(access_control_info.model_dump(exclude_unset=True), indent=4, default=str))


@app.command("trust-analysis")
def trust_analysis(
    contract_address: str,
    token_id: int,
    rpc_url: Optional[str] = typer.Option(None, help="Ethereum RPC URL"),
    chain_id: int = typer.Option(1, help="Chain ID (default: 1 for Ethereum mainnet)"),
    format: str = typer.Option("summary", help="Output format: 'summary', 'detailed', 'json'"),
):
    """Analyze trust and permanence of an NFT"""
    
    async def _analyze_trust():
        inspector = NFTInspector(rpc_url=rpc_url, chain_id=chain_id, analyze_trust=True)
        token_info = await inspector.inspect_token(contract_address, token_id)
        return token_info.trust_analysis
    
    trust_result = asyncio.run(_analyze_trust())
    
    if not trust_result:
        typer.echo("Trust analysis not available for this NFT")
        return
    
    if format == "json":
        typer.echo(json.dumps(trust_result.model_dump(exclude_unset=True), indent=4, default=str))
    elif format == "detailed":
        _print_detailed_trust_analysis(trust_result)
    else:  # summary
        _print_trust_summary(trust_result)


def _print_trust_summary(analysis):
    """Print a concise trust analysis summary"""
    typer.echo(f"🛡️  NFT Trust Analysis")
    typer.echo("=" * 50)
    
    # Overall score with color
    score = analysis.overall_score
    level = analysis.overall_level.value.title()
    
    if score >= 8:
        color = typer.colors.GREEN
    elif score >= 6:
        color = typer.colors.YELLOW
    elif score >= 4:
        color = typer.colors.MAGENTA
    else:
        color = typer.colors.RED
    
    typer.secho(f"Overall Score: {score}/10 ({level})", fg=color, bold=True)
    typer.echo()
    
    # Component scores
    typer.echo("📊 Component Scores:")
    typer.echo(f"   Data Permanence: {analysis.permanence.overall_score}/10")
    typer.echo(f"   Trustlessness:   {analysis.trustlessness.overall_score}/10")
    typer.echo(f"   Chain Trust:     {analysis.chain_trust.stage_score}/10")
    typer.echo()
    
    # Key insights
    if analysis.key_risks:
        typer.echo("⚠️  Key Risks:")
        for risk in analysis.key_risks[:3]:  # Show top 3
            typer.echo(f"   • {risk}")
        typer.echo()
    
    if analysis.strengths:
        typer.echo("✅ Strengths:")
        for strength in analysis.strengths[:3]:  # Show top 3
            typer.echo(f"   • {strength}")
        typer.echo()
    
    # Summary line
    typer.echo(f"💡 {analysis.get_summary()}")


def _print_detailed_trust_analysis(analysis):
    """Print detailed trust analysis with all components"""
    typer.echo(f"🛡️  Detailed NFT Trust Analysis")
    typer.echo("=" * 60)
    
    # Overall
    typer.secho(f"Overall: {analysis.overall_score}/10 ({analysis.overall_level.value.title()})", bold=True)
    typer.echo()
    
    # Permanence details
    typer.echo("📁 Data Permanence Analysis:")
    p = analysis.permanence
    typer.echo(f"   Overall Score:        {p.overall_score}/10")
    typer.echo(f"   Metadata:            {p.metadata_score}/10 ({p.protocol_breakdown['metadata']})")
    typer.echo(f"   Image:               {p.image_score}/10 ({p.protocol_breakdown['image']})")
    typer.echo(f"   Animation:           {p.animation_score}/10 ({p.protocol_breakdown['animation']})")
    typer.echo(f"   Contract Metadata:   {p.contract_metadata_score}/10 ({p.protocol_breakdown['contract_metadata']})")
    typer.echo(f"   Fully On-chain:      {'Yes' if p.is_fully_onchain else 'No'}")
    typer.echo(f"   External Dependencies: {'Yes' if p.has_external_deps else 'No'}")
    typer.echo(f"   Weakest Component:   {p.weakest_component}")
    if p.gateway_penalty > 0:
        typer.echo(f"   Gateway Penalty:     -{p.gateway_penalty:.1f}")
    if p.dependency_penalty > 0:
        typer.echo(f"   Dependency Penalty:  -{p.dependency_penalty:.1f}")
    if p.chain_penalty > 0:
        typer.echo(f"   Chain Penalty:       -{p.chain_penalty:.1f}")
    typer.echo()
    
    # Trustlessness details
    typer.echo("🔐 Trustlessness Analysis:")
    t = analysis.trustlessness
    typer.echo(f"   Overall Score:       {t.overall_score}/10")
    typer.echo(f"   Access Control:      {t.access_control_score}/10")
    typer.echo(f"   Governance:          {t.governance_score}/10")
    typer.echo(f"   Upgradeability:      {t.upgradeability_score}/10")
    typer.echo(f"   Has Owner:           {'Yes' if t.has_owner else 'No'}")
    if t.has_owner:
        owner_display = t.owner_ens if t.owner_ens else "No ENS"
        typer.echo(f"   Owner Type:          {t.owner_type} ({owner_display})")
    typer.echo(f"   Is Upgradeable:      {'Yes' if t.is_upgradeable else 'No'}")
    if t.is_upgradeable and t.proxy_type:
        typer.echo(f"   Proxy Type:          {t.proxy_type}")
    if t.timelock_delay:
        typer.echo(f"   Timelock Delay:      {t.timelock_delay}s")
    typer.echo()
    
    # Chain details
    typer.echo("⛓️  Chain Trust Analysis:")
    c = analysis.chain_trust
    typer.echo(f"   Chain:               {c.chain_name} (ID: {c.chain_id})")
    typer.echo(f"   Stage Score:         {c.stage_score}/10")
    if c.l2beat_stage:
        typer.echo(f"   L2Beat Stage:        {c.l2beat_stage}")
    typer.echo(f"   Is Testnet:          {'Yes' if c.is_testnet else 'No'}")
    typer.echo()
    
    # Trust assumptions
    if analysis.trust_assumptions:
        typer.echo("🔍 Trust Assumptions:")
        for assumption in analysis.trust_assumptions:
            severity_color = {
                "low": typer.colors.GREEN,
                "medium": typer.colors.YELLOW,
                "high": typer.colors.MAGENTA,
                "critical": typer.colors.RED
            }.get(assumption.severity.value, typer.colors.WHITE)
            
            typer.secho(f"   [{assumption.severity.value.upper()}] {assumption.description}", fg=severity_color)
            typer.echo(f"      Impact: {assumption.impact}")
            if assumption.recommendation:
                typer.echo(f"      Recommendation: {assumption.recommendation}")
            typer.echo()
    
    # Recommendations
    if analysis.recommendations:
        typer.echo("💡 Recommendations:")
        for rec in analysis.recommendations:
            typer.echo(f"   • {rec}")
        typer.echo()


if __name__ == "__main__":
    app()