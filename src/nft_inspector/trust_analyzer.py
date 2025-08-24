"""
NFT Trust and Permanence Analyzer Service

Analyzes TokenInfo data to generate comprehensive trust and permanence scores
with detailed assumptions and recommendations.
"""

import json
import os
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timezone
from urllib.parse import urlparse

from .trust_models import (
    TrustLevel, TrustAnalysisResult, PermanenceScore, TrustlessnessScore, 
    ChainTrustScore, TrustAssumption, AssumptionSeverity, L2BeatData
)
from .models import TokenInfo, UrlInfo
from .types import AccessControlType, GovernanceType, ProxyStandard
from .chains.chain_models import ChainInfo


class TrustAnalyzer:
    """
    Simplified NFT trust and permanence analyzer.
    
    Evaluates data permanence and trustlessness with clear, specific trust assumptions.
    """
    
    # Configurable scoring weights
    PERMANENCE_WEIGHT = 0.7
    TRUSTLESSNESS_WEIGHT = 0.3
    
    # Chain penalty multipliers for permanence scoring - only mainnet gets 0.0
    CHAIN_PENALTIES = {
        "Stage 2": 0.5,   # Small penalty even for best L2
        "Stage 1": 1.0,   # Moderate penalty
        "Stage 0": 1.5,   # High penalty
        None: 2.0         # Maximum penalty for unknown
    }
    
    def __init__(self, chain_info: Optional[ChainInfo] = None):
        """Initialize trust analyzer with optional chain information"""
        self.chain_info = chain_info
        self._l2beat_data = self._load_l2beat_data()
    
    def _get_host_from_url(self, url: Optional[str]) -> Optional[str]:
        """Extract hostname from URL for specific trust assumptions"""
        if not url or url.startswith('data:') or url.startswith('ipfs://') or url.startswith('ar://'):
            return None
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None
    
    def _detect_gateway_usage(self, url: Optional[str]) -> tuple[bool, Optional[str]]:
        """Detect if URL uses centralized gateway and return host"""
        if not url:
            return False, None
        
        # Only detect HTTP(S) URLs that use gateway patterns
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, None
            
        host = self._get_host_from_url(url)
        if not host:
            return False, None
        
        # Detect IPFS gateways by checking for 'ipfs' in URL path or host
        if 'ipfs' in url.lower() and ('/ipfs/' in url or 'ipfs' in host.lower()):
            return True, host
            
        # Detect Arweave gateways by checking for 'arweave' or 'ar' patterns
        if ('arweave' in url.lower() or 'arweave' in host.lower() or 
            ('.ar' in host.lower() and len(host.split('.')) >= 2)):
            return True, host
        
        return False, None
    
    def _get_protocol_and_gateway(self, url_info: Optional[UrlInfo]) -> tuple[str, bool, Optional[str]]:
        """Get protocol, gateway status, and host for URL"""
        if not url_info:
            return "none", False, None
        
        protocol = url_info.protocol.value
        url = str(url_info.url) if url_info.url else ""
        
        # Check for gateway usage
        is_gateway, gateway_host = self._detect_gateway_usage(url)
        
        # For non-gateway HTTP URLs, get the regular host
        if protocol in ["http", "https"] and not is_gateway:
            host = self._get_host_from_url(url)
            return protocol, False, host
        
        return protocol, is_gateway, gateway_host
    
    def _load_l2beat_data(self) -> Dict[str, L2BeatData]:
        """Load L2Beat rollup stage data"""
        try:
            # Use the project data directory - go up to the project root
            project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            l2beat_file = os.path.join(project_dir, 'data', 'rollup_stages.json')
            
            if os.path.exists(l2beat_file):
                with open(l2beat_file, 'r') as f:
                    raw_data = json.load(f)
                    return {
                        chain_id: L2BeatData(**data) 
                        for chain_id, data in raw_data.items()
                    }
        except Exception:
            pass  # Fail silently and use defaults
        
        return {}
    
    def analyze_token_trust(self, token_info: TokenInfo) -> TrustAnalysisResult:
        """
        Perform comprehensive trust analysis on a TokenInfo object.
        
        Args:
            token_info: Complete token information from NFTInspector
            
        Returns:
            TrustAnalysisResult with detailed scoring and analysis
        """
        # Analyze each component
        permanence = self._analyze_permanence(token_info)
        trustlessness = self._analyze_trustlessness(token_info)
        chain_trust = self._analyze_chain_trust(token_info)
        
        # Calculate overall score using configurable weights
        overall_raw = (permanence.overall_score * self.PERMANENCE_WEIGHT + 
                      trustlessness.overall_score * self.TRUSTLESSNESS_WEIGHT)
        overall_score = max(0, min(10, round(overall_raw)))
        
        # Determine trust level
        overall_level = self._score_to_trust_level(overall_score)
        
        # Generate trust assumptions and recommendations
        assumptions = self._generate_trust_assumptions(token_info, permanence, trustlessness, chain_trust)
        recommendations = self._generate_recommendations(token_info, permanence, trustlessness)
        
        # Identify key risks and strengths
        key_risks = self._identify_key_risks(token_info, permanence, trustlessness, chain_trust)
        strengths = self._identify_strengths(token_info, permanence, trustlessness, chain_trust)
        
        return TrustAnalysisResult(
            overall_score=overall_score,
            overall_level=overall_level,
            permanence=permanence,
            trustlessness=trustlessness,
            chain_trust=chain_trust,
            trust_assumptions=assumptions,
            recommendations=recommendations,
            key_risks=key_risks,
            strengths=strengths,
            permanence_weight=self.PERMANENCE_WEIGHT,
            trustlessness_weight=self.TRUSTLESSNESS_WEIGHT,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def _analyze_permanence(self, token_info: TokenInfo) -> PermanenceScore:
        """Analyze data permanence across all token components with simplified gating system"""
        
        # Get base protocol scores
        metadata_score = self._get_url_protocol_score(token_info.data_report.token_uri if token_info.data_report else None)
        image_score = self._get_url_protocol_score(token_info.data_report.image if token_info.data_report else None)
        animation_score = self._get_url_protocol_score(token_info.data_report.animation_url if token_info.data_report else None)
        contract_metadata_score = self._get_url_protocol_score(token_info.contract_data_report.contract_uri if token_info.contract_data_report else None)
        
        # Apply protocol gating - metadata gates token components
        gated_image_score = min(metadata_score, image_score) if image_score > 0 else 0
        gated_animation_score = min(metadata_score, animation_score) if animation_score > 0 else 0
        
        # Contract metadata gating - contract URI gates contract metadata images
        contract_uri_score = self._get_url_protocol_score(token_info.contract_data_report.contract_uri if token_info.contract_data_report else None)
        gated_contract_score = min(contract_uri_score, contract_metadata_score) if contract_metadata_score > 0 else 0
        
        # Simplified base score calculation: 90% token data + 10% contract metadata
        token_components = []
        if gated_image_score > 0:
            token_components.append(gated_image_score)
        if gated_animation_score > 0:
            token_components.append(gated_animation_score)
        
        # Token score is mean of available components
        token_score = sum(token_components) / len(token_components) if token_components else 0
        
        # Base score with 90/10 split
        base_score = token_score
        if gated_contract_score > 0:
            base_score = 0.9 * token_score + 0.1 * gated_contract_score
        
        # Calculate chain penalties for L2s
        chain_penalty = self._calculate_chain_penalty()
        
        # Apply penalties (dependency gating handled by protocol scoring)
        adjusted_score = base_score - chain_penalty
        overall_score = max(0, min(10, round(adjusted_score)))
        
        # Determine characteristics using original scores for consistency
        is_fully_onchain = (metadata_score == 10 and 
                           (image_score == 0 or image_score == 10) and 
                           (animation_score == 0 or animation_score == 10))
        
        has_external_deps = self._has_external_dependencies(token_info)
        
        # Find weakest component using gated scores
        scores = {"metadata": metadata_score}
        if gated_image_score > 0:
            scores["image"] = gated_image_score
        if gated_animation_score > 0:
            scores["animation"] = gated_animation_score
        if gated_contract_score > 0:
            scores["contract_metadata"] = gated_contract_score
            
        weakest_component = min(scores.keys(), key=lambda k: scores[k])
        
        # Protocol breakdown
        protocol_breakdown = {
            "metadata": self._get_url_protocol_name(token_info.data_report.token_uri if token_info.data_report else None),
            "image": self._get_url_protocol_name(token_info.data_report.image if token_info.data_report else None),
            "animation": self._get_url_protocol_name(token_info.data_report.animation_url if token_info.data_report else None),
            "contract_metadata": self._get_url_protocol_name(token_info.contract_data_report.contract_uri if token_info.contract_data_report else None)
        }
        
        return PermanenceScore(
            overall_score=overall_score,
            metadata_score=metadata_score,
            image_score=gated_image_score,
            animation_score=gated_animation_score,
            contract_metadata_score=gated_contract_score,
            chain_penalty=chain_penalty,
            is_fully_onchain=is_fully_onchain,
            has_external_deps=has_external_deps,
            weakest_component=weakest_component,
            protocol_breakdown=protocol_breakdown
        )
    
    def _get_url_protocol_score(self, url_info: Optional[UrlInfo], gate_by_dependencies: bool = True) -> int:
        """Get protocol score for a URL, returning 0 if None"""
        if not url_info:
            return 0
        base_score = url_info.protocol.get_score()
        
        # Apply dependency gating for SVG/HTML
        if (gate_by_dependencies and url_info.external_dependencies and 
            not url_info.external_dependencies.is_fully_onchain):
            
            # Gate by lowest dependency protocol score
            dep_score = url_info.external_dependencies.min_protocol_score
            return min(base_score, dep_score)
        
        return base_score
    
    def _get_url_protocol_name(self, url_info: Optional[UrlInfo]) -> str:
        """Get protocol name for a URL, returning 'none' if None"""
        if not url_info:
            return "none"
        return url_info.protocol.value
    
    def _calculate_chain_penalty(self) -> float:
        """Calculate penalty for L2/sidechain dependencies - only mainnet gets 0.0"""
        if not self.chain_info or self.chain_info.isTestnet:
            return 0.0
        
        # Only Ethereum mainnet (chainId == 1) gets no penalty
        if self.chain_info.chainId == 1:
            return 0.0
        
        # Get L2Beat data for penalty calculation
        chain_data = self._l2beat_data.get(str(self.chain_info.chainId))
        stage = chain_data.stage if chain_data else None
        
        # Use configurable penalty multipliers
        return self.CHAIN_PENALTIES.get(stage, 2.0)
    
    def _has_external_dependencies(self, token_info: TokenInfo) -> bool:
        """Check if token has external dependencies in SVG/HTML"""
        if not token_info.data_report:
            return False
        
        # Check image dependencies
        if (token_info.data_report.image and 
            token_info.data_report.image.external_dependencies and
            not token_info.data_report.image.external_dependencies.is_fully_onchain):
            return True
        
        # Check animation dependencies
        if (token_info.data_report.animation_url and
            token_info.data_report.animation_url.external_dependencies and
            not token_info.data_report.animation_url.external_dependencies.is_fully_onchain):
            return True
        
        return False
    
    def _analyze_trustlessness(self, token_info: TokenInfo) -> TrustlessnessScore:
        """Analyze trustlessness based on contract control patterns"""
        
        # Analyze contract control (merged access control and governance)
        control_score, has_owner, owner_type, governance_transparency = self._score_contract_control(token_info.access_control_info)
        
        # Analyze upgradeability/proxy risks
        upgradeability_score, is_upgradeable, proxy_type = self._score_upgradeability(token_info.proxy_info)
        
        # Calculate weighted overall score
        # Contract control is primary concern, then proxy/upgrade risks
        overall_score = round(
            0.7 * control_score + 
            0.3 * upgradeability_score
        )
        
        # Get ENS information
        owner_ens = None
        admin_ens = None
        timelock_delay = None
        
        if token_info.access_control_info:
            owner_ens = token_info.access_control_info.owner_ens_name
            admin_ens = token_info.access_control_info.admin_ens_name
            timelock_delay = token_info.access_control_info.timelock_delay
        
        return TrustlessnessScore(
            overall_score=overall_score,
            access_control_score=control_score,
            upgradeability_score=upgradeability_score,
            has_owner=has_owner,
            owner_type=owner_type,
            is_upgradeable=is_upgradeable,
            proxy_type=proxy_type,
            owner_ens=owner_ens,
            admin_ens=admin_ens,
            governance_transparency=governance_transparency,
            timelock_delay=timelock_delay
        )
    
    def _score_contract_control(self, access_control_info: Optional[Any]) -> Tuple[int, bool, str, int]:
        """Score contract control patterns (merged access control and governance) and return (score, has_owner, owner_type, transparency)"""
        if not access_control_info:
            return 10, False, "none", 10  # No access control info = assume no owner
        
        score = 10
        has_owner = access_control_info.has_owner or access_control_info.has_roles
        transparency = 10
        
        # Determine owner type from governance type and actual ownership
        if not has_owner:
            owner_type = "none"
            score = 10  # No owner = best score
            transparency = 10
        elif access_control_info.governance_type == GovernanceType.RENOUNCED:
            owner_type = "renounced"
            score = 10  # Best case - no owner
            transparency = 10
        elif access_control_info.governance_type == GovernanceType.EOA:
            owner_type = "eoa"
            score = 3   # Worst case - single EOA control
            transparency = 2  # Low transparency for EOA
        elif access_control_info.governance_type == GovernanceType.MULTISIG:
            owner_type = "multisig"
            score = 6   # Better - requires multiple signatures
            transparency = 6  # Moderate transparency
        elif access_control_info.governance_type == GovernanceType.TIMELOCK:
            owner_type = "timelock"
            score = 8   # Good - time-delayed execution
            transparency = 8  # Good transparency
        elif access_control_info.governance_type == GovernanceType.CONTRACT:
            owner_type = "contract"
            score = 5   # Unknown contract behavior
            transparency = 4  # Low transparency without analysis
        else:
            owner_type = "unknown"
            score = 4   # Conservative scoring for unknown types
            transparency = 3
        
        # Access control type adjustments
        if access_control_info.access_control_type:
            if access_control_info.access_control_type == AccessControlType.ACCESS_CONTROL:
                # Role-based access is generally better than single owner
                score = min(score + 1, 10)
                transparency = min(transparency + 2, 10)
            elif access_control_info.access_control_type == AccessControlType.TIMELOCK:
                # Timelock governance gets bonus
                score = min(score + 2, 10)
                transparency = min(transparency + 2, 10)
        
        return score, has_owner, owner_type, transparency
    
    
    def _score_upgradeability(self, proxy_info: Optional[Any]) -> Tuple[int, bool, Optional[str]]:
        """Score based on proxy risk for NFT tokenURI permanence and return (score, is_upgradeable, proxy_type)"""
        if not proxy_info:
            return 10, False, None  # No proxy = immutable = best score
        
        if not proxy_info.is_proxy:
            return 10, False, None  # Not a proxy = immutable
        
        # Contract is a proxy - assess tokenURI risk based on proxy type
        proxy_type = proxy_info.proxy_standard.value if proxy_info.proxy_standard else "unknown"
        is_upgradeable = proxy_info.is_upgradeable
        
        if not is_upgradeable:
            return 9, False, proxy_type  # Proxy but not upgradeable (e.g., minimal proxy) = very good
        
        # Upgradeable proxy - severe scoring for tokenURI risk
        proxy_scores = {
            ProxyStandard.EIP_1167_MINIMAL: 9,      # Clone - usually safe for tokenURI
            ProxyStandard.EIP_1967_TRANSPARENT: 3,  # Admin can change tokenURI implementation
            ProxyStandard.EIP_1822_UUPS: 2,         # Self-upgrade can modify tokenURI function
            ProxyStandard.BEACON_PROXY: 2,          # Central beacon can change tokenURI behavior
            ProxyStandard.EIP_2535_DIAMOND: 2,      # Complex facets - highest tokenURI risk
            ProxyStandard.CUSTOM_PROXY: 2,          # Unknown logic - assume high tokenURI risk
            ProxyStandard.NOT_PROXY: 10             # Should not happen here
        }
        
        score = proxy_scores.get(proxy_info.proxy_standard, 2)
        return score, True, proxy_type
    
    def _analyze_chain_trust(self, _token_info: TokenInfo) -> ChainTrustScore:
        """Analyze chain-specific trust factors"""
        chain_id = self.chain_info.chainId if self.chain_info else 1
        chain_name = self.chain_info.name if self.chain_info else "Ethereum"
        is_testnet = self.chain_info.isTestnet if self.chain_info else False
        
        # Get L2Beat data for this chain - simple stage-based analysis
        chain_data = self._l2beat_data.get(str(chain_id))
        l2beat_stage = chain_data.stage if chain_data else None
        
        return ChainTrustScore(
            chain_id=chain_id,
            chain_name=chain_name,
            is_testnet=is_testnet,
            l2beat_stage=l2beat_stage
        )
    
    def _score_to_trust_level(self, score: int) -> TrustLevel:
        """Convert numeric score to trust level"""
        if score >= 9:
            return TrustLevel.EXCELLENT
        elif score >= 7:
            return TrustLevel.GOOD
        elif score >= 5:
            return TrustLevel.MODERATE
        elif score >= 3:
            return TrustLevel.POOR
        else:
            return TrustLevel.CRITICAL
    
    def _generate_trust_assumptions(self, token_info: TokenInfo, _permanence: PermanenceScore, 
                                  trustlessness: TrustlessnessScore, chain_trust: ChainTrustScore) -> List[TrustAssumption]:
        """Generate trust assumptions based on analysis findings"""
        assumptions = []
        
        # Data storage assumptions - simplified approach
        self._add_storage_assumptions(token_info, assumptions)
        
        # Contract control assumptions
        if trustlessness.has_owner and trustlessness.owner_type != "renounced":
            owner_display = trustlessness.owner_ens if trustlessness.owner_ens else "contract owner"
            assumptions.append(TrustAssumption(
                category="Contract Control",
                description=f"Contract controlled by {owner_display}",
                severity=AssumptionSeverity.MEDIUM if trustlessness.owner_type in ["multisig", "timelock"] else AssumptionSeverity.HIGH,
                impact="Owner could modify contract behavior or transfer ownership",
                recommendation="Verify owner's intentions and track ownership changes"
            ))
        
        # Proxy assumptions - NFT focused
        if trustlessness.is_upgradeable and trustlessness.proxy_type:
            assumptions.append(TrustAssumption(
                category="Contract Control", 
                description=f"Uses {trustlessness.proxy_type} proxy, tokenURI can be upgraded",
                severity=AssumptionSeverity.HIGH,
                impact="NFT metadata access could be completely broken by contract upgrade",
                recommendation="Monitor upgrade activities and proxy admin actions"
            ))
        
        # Chain dependency
        if chain_trust.chain_id != 1 and not chain_trust.is_testnet:
            if chain_trust.l2beat_stage:
                description = f"Relies on {chain_trust.chain_name} being operational ({chain_trust.l2beat_stage} on L2Beat)"
                severity = AssumptionSeverity.LOW if chain_trust.l2beat_stage == "Stage 2" else AssumptionSeverity.MEDIUM
            else:
                description = f"Relies on {chain_trust.chain_name} being operational (no L2Beat stage info)"
                severity = AssumptionSeverity.HIGH
            
            assumptions.append(TrustAssumption(
                category="Infrastructure",
                description=description,
                severity=severity,
                impact="NFT becomes inaccessible if chain experiences issues",
                recommendation="Consider chain's decentralization level for critical assets"
            ))
        
        return assumptions
    
    def _add_storage_assumptions(self, token_info: TokenInfo, assumptions: List[TrustAssumption]):
        """Add storage-related trust assumptions with simplified logic"""
        if not token_info.data_report:
            return
            
        # Check each component for centralization risks
        components = [
            ("metadata", token_info.data_report.token_uri, AssumptionSeverity.HIGH),
            ("image", token_info.data_report.image, AssumptionSeverity.MEDIUM),
            ("animation", token_info.data_report.animation_url, AssumptionSeverity.MEDIUM)
        ]
        
        for component_name, url_info, severity in components:
            if not url_info:
                continue
                
            protocol, is_gateway, host = self._get_protocol_and_gateway(url_info)
            
            # Centralized storage risk
            if protocol in ["http", "https"] and not is_gateway:
                assumptions.append(TrustAssumption(
                    category="Data Storage",
                    description=f"NFT {component_name} hosted on centralized server {host}",
                    severity=severity,
                    impact=f"{component_name.title()} could become unavailable or change",
                    recommendation="Store data on-chain or use IPFS/Arweave"
                ))
            
            # Gateway dependency risk
            elif is_gateway and host:
                if protocol == "ipfs" or str(url_info.url).startswith('ipfs://'):
                    assumptions.append(TrustAssumption(
                        category="Data Storage", 
                        description=f"NFT {component_name} uses IPFS via gateway {host}",
                        severity=AssumptionSeverity.LOW,
                        impact=f"{component_name.title()} depends on gateway and IPFS pinning",
                        recommendation="Use native IPFS access or store on-chain"
                    ))
                elif protocol == "arweave" or str(url_info.url).startswith('ar://'):
                    assumptions.append(TrustAssumption(
                        category="Data Storage",
                        description=f"NFT {component_name} uses Arweave via gateway {host}",
                        severity=AssumptionSeverity.LOW, 
                        impact=f"{component_name.title()} depends on gateway availability",
                        recommendation="Use native Arweave access"
                    ))
    
    def _generate_recommendations(self, _token_info: TokenInfo, permanence: PermanenceScore, 
                                trustlessness: TrustlessnessScore) -> List[str]:
        """Generate simple actionable recommendations"""
        recommendations = []
        
        if permanence.overall_score < 6:
            recommendations.append("Improve data permanence by using IPFS or on-chain storage")
        
        # Only suggest ownership changes if there's actually an owner
        if trustlessness.overall_score < 8 and trustlessness.has_owner:
            recommendations.append("Consider renouncing ownership or using time-locked governance")
        
        return recommendations
    
    def _identify_key_risks(self, token_info: TokenInfo, _permanence: PermanenceScore,
                           trustlessness: TrustlessnessScore, chain_trust: ChainTrustScore) -> List[str]:
        """Identify top risks from trust assumptions"""
        risks = []
        
        # Get protocol info for risk identification
        metadata_protocol, metadata_is_gateway, _ = self._get_protocol_and_gateway(
            token_info.data_report.token_uri if token_info.data_report else None)
        
        if metadata_protocol in ["http", "https"] and not metadata_is_gateway:
            risks.append("Metadata stored on centralized server")
        
        if trustlessness.is_upgradeable:
            risks.append("Contract can be upgraded")
        
        if chain_trust.chain_id != 1 and not chain_trust.is_testnet and chain_trust.l2beat_stage != "Stage 2":
            risks.append("Depends on centralized L2 infrastructure")
        
        return risks[:3]  # Keep it simple
    
    def _identify_strengths(self, _token_info: TokenInfo, permanence: PermanenceScore,
                           trustlessness: TrustlessnessScore, chain_trust: ChainTrustScore) -> List[str]:
        """Identify key strengths"""
        strengths = []
        
        if permanence.is_fully_onchain:
            strengths.append("All data stored on-chain")
        
        if not trustlessness.has_owner:
            strengths.append("No contract owner")
        
        if not trustlessness.is_upgradeable:
            strengths.append("Immutable contract")
        
        if chain_trust.chain_id == 1:
            strengths.append("Deployed on Ethereum mainnet")
        
        return strengths