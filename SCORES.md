# NFT Trust Analysis Scoring System

This document explains how the NFT Inspector calculates trust and permanence scores for NFTs.

## Overview

The overall trust score combines two main components:
- **Data Permanence (70% weight)**: How permanent and decentralized the NFT data is
- **Trustlessness (30% weight)**: How trustless the smart contract is

```
Overall Score = (Permanence Score × 0.7) + (Trustlessness Score × 0.3)
```

## Score Ranges

| Score | Level | Description |
|-------|-------|-------------|
| 9-10  | **Excellent** 🟢 | Fully decentralized and permanent |
| 7-8   | **Good** 🟡 | Mostly trustless with minor dependencies |
| 5-6   | **Moderate** 🟠 | Mixed centralization, some risks |
| 3-4   | **Poor** 🔴 | Highly centralized, significant risks |
| 0-2   | **Critical** ⚠️ | Completely centralized, maximum risk |

---

## Data Permanence Analysis (70% Weight)

### Protocol Base Scores

Each URL component gets a base score based on its protocol:

| Protocol | Score | Description |
|----------|-------|-------------|
| `data:` | 10 | Fully on-chain, permanent |
| `ar://` | 7 | Arweave permanent storage |
| `ipfs://` | 5 | IPFS decentralized storage (pinning dependent) |
| `ipns://` | 3 | IPNS mutable naming |
| `https://` | 2 | Centralized server |
| `http://` | 1 | Insecure centralized server |
| None | 0 | No data |

### Simplified Component Calculation

The permanence score uses a streamlined approach:

**Protocol Gating:**
```
gated_image_score = min(metadata_protocol_score, image_protocol_score)
gated_animation_score = min(metadata_protocol_score, animation_protocol_score)
```

**Base Score Calculation:**
```
token_score = mean(gated_image_score, gated_animation_score)  # Only existing components
base_score = (0.9 × token_score) + (0.1 × contract_metadata_score)
```

### Protocol Gating System

**Metadata gates all token components** - can only lower scores, not raise them:
- If metadata is HTTPS (score 2) and image is IPFS (score 6) → image becomes 2
- If metadata is data URI (score 10) and image is IPFS (score 6) → image stays 6

**Contract URI gates contract metadata** the same way:
- Contract URI protocol score gates any images found in contract metadata

### Dependency Gating

**SVG/HTML External Dependencies:**
- If SVG is on Arweave (score 8) but has HTTPS dependencies (score 2) → SVG becomes 2
- If HTML is on-chain (score 10) but loads IPFS images (score 6) → HTML becomes 6

### Penalties

#### Chain Penalty (L2/Sidechain)
Based on L2Beat stage data - **only Ethereum mainnet gets 0.0 penalty**:

| L2Beat Stage | Penalty | Description |
|--------------|---------|-------------|
| Mainnet (ETH) | 0.0 | Ethereum mainnet only |
| Stage 2 | 0.5 | Best L2s still get penalty |
| Stage 1 | 1.0 | Moderate penalty |
| Stage 0 | 1.5 | High penalty |
| None | 2.0 | Maximum penalty for unknown |

### Final Calculation
```
final_score = base_score - chain_penalty
permanence_score = max(0, min(10, round(final_score)))
```

**Note:** Gateway and dependency penalties are eliminated since protocol gating handles both centralization and external dependencies.

---

## Trustlessness Analysis (30% Weight)

Combines two components:

```
trustlessness = (0.8 × contract_control) + (0.2 × upgradeability)
```

### 1. Contract Control Score (70% of Trustlessness)

Base scores by governance type:

| Governance Type | Base Score | Description |
|-----------------|------------|-------------|
| No Owner | 10.0 | Perfect - no control |
| Renounced | 10.0 | Owner gave up control |
| Timelock | 8.5 | Time-delayed execution |
| Multisig | 7.0 | Multiple signers required |
| Contract | 4.5 | Unknown contract logic |
| Unknown | 4.0 | Has owner but unclear governance |
| EOA | 2.0 | Single person control |

No additional bonuses or caps are applied. The score is a direct weighted combination of contract control and upgradeability.

### 2. Proxy Risk Score (30% of Trustlessness)

**Focus**: Risk of tokenURI function changes that could break NFT metadata access.

| Proxy Type | Score | Description |
|------------|-------|-------------|
| Not Proxy | 10.0 | Immutable contract - tokenURI cannot change |
| Minimal Proxy (EIP-1167) | 9.0 | Clone pattern - usually safe for tokenURI |
| Non-upgradeable Proxy | 9.0 | Proxy but immutable - tokenURI protected |
| Transparent Proxy (EIP-1967) | 3.5 | Admin can change tokenURI implementation |
| UUPS Proxy (EIP-1822) | 2.0 | Self-upgrade can modify tokenURI function |
| Beacon Proxy | 2.0 | Central beacon can change tokenURI behavior |
| Custom Proxy | 2.0 | Unknown logic - assume high tokenURI risk |
| Diamond Proxy (EIP-2535) | 2.0 | Complex facets - high tokenURI risk |

---

## Chain Trust Analysis

Chain trust is calculated but **not included** in the overall score. It affects:
- Permanence chain penalties
- Trust assumptions generation
- Risk identification

### L2Beat Stage Scoring

| Stage | Score | Description |
|-------|-------|-------------|
| Stage 2 | 10 | Full decentralization |
| Stage 1 | 7 | Limited decentralization |
| Stage 0 | 4 | Centralized with training wheels |
| None | 2 | No stage information |

---

## Examples

### Example 1: Fully On-Chain NFT
```
Metadata: data: (10)
Image: data: (10) 
Animation: data: (10)

Permanence = (0.4×10 + 0.35×10 + 0.25×10) - 0 = 10/10
Trustlessness = No owner, immutable = 10/10
Overall = (10×0.7) + (10×0.3) = 10/10 "Excellent"
```

### Example 2: BAYC #1
```
Metadata: ipfs: (5)
Image: ipfs: (5) 
Gated image: min(5, 5) = 5
Base = 0.9 × mean(5) = 0.9 × 5 = 4.5

Permanence = 4.5 → 4/10 (no penalties on mainnet)
Trustlessness = No owner, immutable = 10/10  
Overall = (4×0.7) + (10×0.3) = 2.8 + 3.0 = 5.8 → 6/10 "Moderate"
```

### Example 3: Mixed Protocol NFT (Showing Gating)
```
Metadata: https://api.example.com (2)  
Image: ipfs://QmXXX (6)
Gated image: min(2, 6) = 2  ← Metadata gates image down to HTTPS level
Base = 0.9 × mean(2) = 0.9 × 2 = 1.8

Permanence = 1.8/10
Trustlessness = 10/10 (no owner, immutable)
Overall = (1.8×0.7) + (10×0.3) = 1.26 + 3.0 = 4.3 → 4/10 "Poor"
```

### Example 4: L2 NFT
```
Metadata: data: (10)
Image: data: (10)
Base = 0.9 × mean(10) = 9.0
Chain penalty = 1.0 (Stage 1 L2)

Permanence = 9.0 - 1.0 = 8/10
Trustlessness = 10/10
Overall = (8×0.7) + (10×0.3) = 5.6 + 3.0 = 8.6 → 9/10 "Excellent"
```

---

## Trust Assumptions

The system generates specific trust assumptions based on detected patterns:

### Gateway Dependencies
- **IPFS via gateway**: "Metadata uses IPFS via gateway ipfs.io; relies on the gateway and IPFS pinning"
- **Arweave via gateway**: "Image uses Arweave via gateway arweave.net; relies on the gateway and Arweave permanence"
- **Centralized hosting**: "Animation is centralized and can change, relies on cdn.example.com"

### Contract Control
- **Has owner**: "Contract has alice.eth as owner that might have control"
- **Upgradeable**: "Uses a transparent proxy, the implementation might be upgraded in the future"

### Chain Dependencies
- **L2 chains**: "Relies on Arbitrum One being operational — which is Stage 1 according to L2Beat"

---

## Configuration

The scoring system uses configurable weights:

```python
PERMANENCE_WEIGHT = 0.7    # Data permanence importance
TRUSTLESSNESS_WEIGHT = 0.3 # Contract trustlessness importance

# L2 chain penalties - only mainnet gets 0.0
CHAIN_PENALTIES = {
    "Stage 2": 0.5,   # Small penalty even for best L2
    "Stage 1": 1.0,   # Moderate penalty
    "Stage 0": 1.5,   # High penalty
    None: 2.0         # Maximum penalty for unknown
}

# Base score calculation split
TOKEN_DATA_WEIGHT = 0.9    # Image/animation importance
CONTRACT_METADATA_WEIGHT = 0.1  # Contract metadata importance

# Trustlessness component weights
CONTRACT_CONTROL_WEIGHT = 0.8   # Contract control importance
UPGRADEABILITY_WEIGHT = 0.2     # Proxy/upgradeability importance
```

These weights can be adjusted to prioritize different aspects of NFT trust and permanence.