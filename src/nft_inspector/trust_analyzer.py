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
    
    # L2Beat rollup stage scoring
    L2BEAT_STAGE_SCORES = {
        "Stage 2": 10,    # Full decentralization
        "Stage 1": 7,     # Limited decentralization  
        "Stage 0": 4,     # Centralized with training wheels
        None: 2           # No stage information available
    }
    
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
        
        # Handle native IPFS URLs - they're commonly accessed via gateways
        if url.startswith('ipfs://'):
            return True, 'ipfs.io'  # Most common gateway
        
        # Handle native Arweave URLs - they're commonly accessed via gateways  
        if url.startswith('ar://'):
            return True, 'arweave.net'  # Most common gateway
            
        host = self._get_host_from_url(url)
        if not host:
            return False, None
        
        # Common IPFS gateways
        ipfs_gateways = ['ipfs.io', 'gateway.ipfs.io', 'cloudflare-ipfs.com', 'dweb.link']
        # Common Arweave gateways  
        arweave_gateways = ['arweave.net', 'ar.io', 'gateway.arweave.net']
        
        # Check for HTTP gateway patterns
        is_gateway = (
            any(gateway in host for gateway in ipfs_gateways) and '/ipfs/' in url or
            any(gateway in host for gateway in arweave_gateways)
        )
        
        return is_gateway, host if is_gateway else None
    
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
        
        # Analyze access control
        access_control_score, has_owner, owner_type, governance_transparency = self._score_access_control(token_info.access_control_info)
        
        # Analyze governance type
        governance_score = self._score_governance_type(token_info.access_control_info)
        
        # Analyze upgradeability
        upgradeability_score, is_upgradeable, proxy_type = self._score_upgradeability(token_info.proxy_info)
        
        # Calculate weighted overall score
        # Access control is most important, then upgradeability, then governance transparency
        overall_score = round(
            0.5 * access_control_score + 
            0.3 * upgradeability_score + 
            0.2 * governance_score
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
            access_control_score=access_control_score,
            governance_score=governance_score,
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
    
    def _score_access_control(self, access_control_info: Optional[Any]) -> Tuple[int, bool, str, int]:
        """Score access control patterns and return (score, has_owner, owner_type, transparency)"""
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
    
    def _score_governance_type(self, access_control_info: Optional[Any]) -> int:
        """Score based on governance type characteristics"""
        if not access_control_info:
            return 10  # No access control info = no governance needed
        
        # If there's no owner, governance type doesn't matter
        has_owner = access_control_info.has_owner or access_control_info.has_roles
        if not has_owner:
            return 10  # No owner = no governance needed = perfect score
        
        if not access_control_info.governance_type:
            return 8  # Has owner but unknown governance type
        
        governance_scores = {
            GovernanceType.RENOUNCED: 10,    # Perfect - no governance
            GovernanceType.TIMELOCK: 7,      # Good - time-delayed but still governance
            GovernanceType.MULTISIG: 5,      # Moderate - requires trust in signers  
            GovernanceType.CONTRACT: 3,      # Poor - opaque contract logic
            GovernanceType.EOA: 2,           # Very poor - single point of control
            GovernanceType.UNKNOWN: 1        # Critical - has owner but governance unclear
        }
        
        return governance_scores.get(access_control_info.governance_type, 5)
    
    def _score_upgradeability(self, proxy_info: Optional[Any]) -> Tuple[int, bool, Optional[str]]:
        """Score based on upgradeability and return (score, is_upgradeable, proxy_type)"""
        if not proxy_info:
            return 10, False, None  # No proxy = immutable = best score
        
        if not proxy_info.is_proxy:
            return 10, False, None  # Not a proxy = immutable
        
        # Contract is upgradeable - determine severity based on proxy type
        proxy_type = proxy_info.proxy_standard.value if proxy_info.proxy_standard else "unknown"
        is_upgradeable = proxy_info.is_upgradeable
        
        if not is_upgradeable:
            return 8, False, proxy_type  # Proxy but not upgradeable (e.g., minimal proxy)
        
        # Upgradeable proxy - score based on type
        proxy_scores = {
            ProxyStandard.EIP_1167_MINIMAL: 8,      # Minimal proxy - usually immutable
            ProxyStandard.EIP_1822_UUPS: 4,         # UUPS - self-upgradeable
            ProxyStandard.EIP_1967_TRANSPARENT: 5,  # Transparent - admin controlled
            ProxyStandard.BEACON_PROXY: 4,          # Beacon - centrally controlled
            ProxyStandard.EIP_2535_DIAMOND: 3,      # Diamond - complex upgradeability
            ProxyStandard.CUSTOM_PROXY: 4,          # Unknown custom logic
            ProxyStandard.NOT_PROXY: 10             # Should not happen here
        }
        
        score = proxy_scores.get(proxy_info.proxy_standard, 4)
        return score, True, proxy_type
    
    def _analyze_chain_trust(self, _token_info: TokenInfo) -> ChainTrustScore:
        """Analyze chain-specific trust factors"""
        chain_id = self.chain_info.chainId if self.chain_info else 1
        chain_name = self.chain_info.name if self.chain_info else "Ethereum"
        is_testnet = self.chain_info.isTestnet if self.chain_info else False
        
        # Get L2Beat data for this chain - simple stage-based analysis
        chain_data = self._l2beat_data.get(str(chain_id))
        l2beat_stage = chain_data.stage if chain_data else None
        
        # Calculate stage score - this is our main L2 trust metric
        stage_score = self.L2BEAT_STAGE_SCORES.get(l2beat_stage, 2)
        
        return ChainTrustScore(
            chain_id=chain_id,
            chain_name=chain_name,
            is_testnet=is_testnet,
            l2beat_stage=l2beat_stage,
            stage_score=stage_score
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
        """Generate specific trust assumptions following TrustProfileCard.tsx style"""
        assumptions = []
        
        # Get URL information for each component
        metadata_url = token_info.data_report.token_uri if token_info.data_report else None
        image_url = token_info.data_report.image if token_info.data_report else None
        animation_url = token_info.data_report.animation_url if token_info.data_report else None
        
        # Check if metadata is centralized (affects other components)
        metadata_protocol, metadata_is_gateway, metadata_host = self._get_protocol_and_gateway(metadata_url)
        metadata_central = metadata_protocol in ["http", "https"] or metadata_is_gateway
        metadata_risk_suffix = " and is also affected by metadata hosting" if metadata_central else ""
        
        # Metadata assumptions (following TrustProfileCard patterns)
        if metadata_central and metadata_host:
            if metadata_is_gateway:
                # Determine protocol for gateway usage
                if metadata_protocol == "ipfs" or (metadata_url and str(metadata_url.url).startswith('ipfs://')):
                    description = f"Metadata uses IPFS via gateway {metadata_host}; relies on the gateway and IPFS pinning"
                elif metadata_protocol == "arweave" or (metadata_url and str(metadata_url.url).startswith('ar://')):
                    description = f"Metadata uses Arweave via gateway {metadata_host}; relies on the gateway and Arweave permanence"
                else:
                    description = f"Metadata uses gateway {metadata_host}; relies on the gateway service"
            else:
                description = f"Metadata is centralized and can change, relies on {metadata_host}"
            
            assumptions.append(TrustAssumption(
                category="Data Storage",
                description=description,
                severity=AssumptionSeverity.HIGH,
                impact="NFT metadata could become inaccessible or change, affecting display and value",
                recommendation="Store metadata on on-chain for permanence"
            ))
        
        # Image assumptions
        if image_url:
            image_protocol, image_is_gateway, image_host = self._get_protocol_and_gateway(image_url)
            image_central = image_protocol in ["http", "https"] or image_is_gateway
            
            if image_central and image_host:
                if image_is_gateway:
                    # Determine protocol for gateway usage
                    if image_protocol == "ipfs" or (image_url and str(image_url.url).startswith('ipfs://')):
                        description = f"Image uses IPFS via gateway {image_host}; relies on the gateway and IPFS pinning{metadata_risk_suffix}"
                    elif image_protocol == "arweave" or (image_url and str(image_url.url).startswith('ar://')):
                        description = f"Image uses Arweave via gateway {image_host}; relies on the gateway and Arweave permanence{metadata_risk_suffix}"
                    else:
                        description = f"Image uses gateway {image_host}; relies on the gateway service{metadata_risk_suffix}"
                else:
                    description = f"Image is centralized and can change{metadata_risk_suffix}, relies on {image_host}"
                
                assumptions.append(TrustAssumption(
                    category="Data Storage",
                    description=description,
                    severity=AssumptionSeverity.MEDIUM,
                    impact="Image could become unavailable or change, affecting NFT appearance",
                    recommendation="Store images on-chain"
                ))
            elif str(image_url.url).startswith('ipfs://'):
                assumptions.append(TrustAssumption(
                    category="Data Storage",
                    description=f"Image relies on IPFS pinning{metadata_risk_suffix}",
                    severity=AssumptionSeverity.LOW,
                    impact="Image may disappear if not pinned",
                    recommendation="Ensure reliable IPFS pinning"
                ))
        
        # Animation assumptions (similar pattern)
        if animation_url:
            animation_protocol, animation_is_gateway, animation_host = self._get_protocol_and_gateway(animation_url)
            animation_central = animation_protocol in ["http", "https"] or animation_is_gateway
            
            if animation_central and animation_host:
                if animation_is_gateway:
                    # Determine protocol for gateway usage
                    if animation_protocol == "ipfs" or (animation_url and str(animation_url.url).startswith('ipfs://')):
                        description = f"Animation uses IPFS via gateway {animation_host}; relies on the gateway and IPFS pinning{metadata_risk_suffix}"
                    elif animation_protocol == "arweave" or (animation_url and str(animation_url.url).startswith('ar://')):
                        description = f"Animation uses Arweave via gateway {animation_host}; relies on the gateway and Arweave permanence{metadata_risk_suffix}"
                    else:
                        description = f"Animation uses gateway {animation_host}; relies on the gateway service{metadata_risk_suffix}"
                else:
                    description = f"Animation is centralized and can change{metadata_risk_suffix}, relies on {animation_host}"
                
                assumptions.append(TrustAssumption(
                    category="Data Storage",
                    description=description,
                    severity=AssumptionSeverity.MEDIUM,
                    impact="Animation could become unavailable or change",
                    recommendation="Store animations on-chain"
                ))
        
        # Contract control assumptions (ENS-enhanced)
        if trustlessness.has_owner and trustlessness.owner_type != "renounced":
            owner_display = trustlessness.owner_ens if trustlessness.owner_ens else "contract owner"
            assumptions.append(TrustAssumption(
                category="Contract Control",
                description=f"Contract has {owner_display} as owner that might have control",
                severity=AssumptionSeverity.MEDIUM if trustlessness.owner_type in ["multisig", "timelock"] else AssumptionSeverity.HIGH,
                impact="Owner could modify contract behavior or transfer ownership",
                recommendation="Verify owner's intentions and track ownership changes"
            ))
        
        # Proxy assumptions
        if trustlessness.is_upgradeable and trustlessness.proxy_type:
            assumptions.append(TrustAssumption(
                category="Contract Control", 
                description=f"Uses a {trustlessness.proxy_type} proxy, the implementation might be upgraded in the future",
                severity=AssumptionSeverity.HIGH,
                impact="Contract logic could be completely changed via upgrade",
                recommendation="Monitor upgrade activities and proxy admin actions"
            ))
        
        # Chain dependency (following L2Beat pattern)
        if chain_trust.chain_id != 1 and not chain_trust.is_testnet:
            if chain_trust.l2beat_stage:
                description = f"Relies on {chain_trust.chain_name} being operational — which is {chain_trust.l2beat_stage} according to L2Beat"
                severity = AssumptionSeverity.LOW if chain_trust.l2beat_stage == "Stage 2" else AssumptionSeverity.MEDIUM
            else:
                description = f"Relies on {chain_trust.chain_name} being operational — no Stage on L2Beat!"
                severity = AssumptionSeverity.HIGH
            
            assumptions.append(TrustAssumption(
                category="Infrastructure",
                description=description,
                severity=severity,
                impact="NFT becomes inaccessible if the chain experiences issues",
                recommendation="Consider the chain's decentralization level for critical assets"
            ))
        
        return assumptions
    
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
        
        if chain_trust.chain_id != 1 and not chain_trust.is_testnet and chain_trust.stage_score <= 4:
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