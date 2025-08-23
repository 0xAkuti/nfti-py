"""
Trust analysis models for NFT permanence and trustlessness assessment.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class TrustLevel(str, Enum):
    """Trust level classifications for NFT analysis"""
    EXCELLENT = "excellent"      # 9-10: Fully on-chain, renounced, no dependencies
    GOOD = "good"               # 7-8: Mostly decentralized, minimal trust assumptions
    MODERATE = "moderate"       # 5-6: Mixed approach, some centralized components
    POOR = "poor"              # 3-4: Mostly centralized, significant trust assumptions
    CRITICAL = "critical"      # 0-2: Fully centralized, high dependency risk


class AssumptionSeverity(str, Enum):
    """Severity levels for trust assumptions"""
    LOW = "low"                # Minor risk, unlikely to affect NFT
    MEDIUM = "medium"          # Moderate risk, could affect availability/mutability
    HIGH = "high"             # High risk, significant dependency or control
    CRITICAL = "critical"     # Critical risk, complete dependence on centralized entity


class L2BeatData(BaseModel):
    """L2Beat rollup data model"""
    chain_name: str
    rollup_type: str
    stage: Optional[str] = None
    link: Optional[str] = None


class TrustAssumption(BaseModel):
    """Individual trust assumption with context"""
    category: str              # e.g., "Data Storage", "Contract Control", "Infrastructure"
    description: str           # Human-readable description
    severity: AssumptionSeverity
    impact: str               # What happens if this assumption fails
    recommendation: Optional[str] = None  # How to mitigate this risk


class PermanenceScore(BaseModel):
    """Detailed breakdown of data permanence scoring"""
    overall_score: int         # 0-10 composite score
    metadata_score: int        # Score for tokenURI/metadata storage
    image_score: int          # Score for image storage  
    animation_score: int      # Score for animation storage
    contract_metadata_score: int  # Score for contractURI storage
    
    # Modifiers and penalties
    gateway_penalty: float = 0.0      # Penalty for using centralized gateways
    dependency_penalty: float = 0.0   # Penalty for external dependencies in SVG/HTML
    chain_penalty: float = 0.0        # Penalty for L2/sidechain dependencies
    
    # Analysis details
    is_fully_onchain: bool     # True if all data is on-chain (data URIs)
    has_external_deps: bool    # True if SVG/HTML has external dependencies
    weakest_component: str     # Which component has the lowest score
    protocol_breakdown: Dict[str, str]  # Protocol used for each component


class TrustlessnessScore(BaseModel):
    """Detailed breakdown of trustlessness/control scoring"""
    overall_score: int         # 0-10 composite score
    access_control_score: int  # Score based on ownership/access patterns
    governance_score: int      # Score based on governance type (EOA vs multisig vs timelock)
    upgradeability_score: int  # Score based on proxy/upgrade patterns
    
    # Analysis details
    has_owner: bool           # Contract has an owner
    owner_type: str          # Type of owner (EOA, multisig, timelock, renounced)
    is_upgradeable: bool     # Contract can be upgraded
    proxy_type: Optional[str] = None  # Type of proxy if applicable
    
    # ENS information for transparency
    owner_ens: Optional[str] = None     # ENS name of owner if available
    admin_ens: Optional[str] = None     # ENS name of admin if available
    
    # Governance details
    governance_transparency: int  # 0-10 score for governance transparency
    timelock_delay: Optional[int] = None  # Timelock delay in seconds if applicable


class ChainTrustScore(BaseModel):
    """Simplified chain trust assessment"""
    chain_id: int
    chain_name: str
    is_testnet: bool
    l2beat_stage: Optional[str] = None  # "Stage 0", "Stage 1", "Stage 2", None
    stage_score: int          # 0-10 score based on stage only


class TrustAnalysisResult(BaseModel):
    """Complete trust analysis result"""
    # Overall scores
    overall_score: int                    # 0-10 weighted composite score
    overall_level: TrustLevel            # Classification based on score
    
    # Component scores
    permanence: PermanenceScore
    trustlessness: TrustlessnessScore
    chain_trust: ChainTrustScore
    
    # Analysis metadata
    analysis_version: str = "1.0"        # Version of analysis algorithm
    timestamp: Optional[str] = None       # When analysis was performed
    
    # Findings
    trust_assumptions: List[TrustAssumption] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # Summary
    key_risks: List[str] = Field(default_factory=list)      # Top 3-5 key risks
    strengths: List[str] = Field(default_factory=list)      # What's done well
    
    # Scoring weights used
    permanence_weight: float = 0.7       # Weight for permanence in overall score
    trustlessness_weight: float = 0.3    # Weight for trustlessness in overall score
    
    def get_score_breakdown(self) -> Dict[str, Any]:
        """Get detailed breakdown of how the score was calculated"""
        return {
            "overall": {
                "score": self.overall_score,
                "level": self.overall_level,
                "calculation": f"{self.permanence.overall_score} * {self.permanence_weight} + {self.trustlessness.overall_score} * {self.trustlessness_weight}"
            },
            "permanence": {
                "score": self.permanence.overall_score,
                "components": {
                    "metadata": self.permanence.metadata_score,
                    "image": self.permanence.image_score,
                    "animation": self.permanence.animation_score,
                    "contract_metadata": self.permanence.contract_metadata_score
                },
                "penalties": {
                    "gateway": self.permanence.gateway_penalty,
                    "dependencies": self.permanence.dependency_penalty,
                    "chain": self.permanence.chain_penalty
                }
            },
            "trustlessness": {
                "score": self.trustlessness.overall_score,
                "components": {
                    "access_control": self.trustlessness.access_control_score,
                    "governance": self.trustlessness.governance_score,
                    "upgradeability": self.trustlessness.upgradeability_score
                }
            },
            "chain": {
                "score": self.chain_trust.stage_score,
                "l2beat_stage": self.chain_trust.l2beat_stage
            }
        }
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the analysis"""
        level_descriptions = {
            TrustLevel.EXCELLENT: "Excellent - Fully decentralized and trustless",
            TrustLevel.GOOD: "Good - Mostly decentralized with minimal trust assumptions", 
            TrustLevel.MODERATE: "Moderate - Mixed approach with some centralized components",
            TrustLevel.POOR: "Poor - Mostly centralized with significant trust requirements",
            TrustLevel.CRITICAL: "Critical - Fully centralized with high dependency risk"
        }
        
        return f"{self.overall_score}/10 - {level_descriptions[self.overall_level]}"