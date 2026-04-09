# 📋 Custom LLM Pricing Package Implementation Plan

## Overview

This plan outlines the implementation of a **standalone Python package** for LLM pricing with:

- ✅ **Provider Tiers** (Free, Pro, Enterprise, etc.)
- ✅ **Model-Based Rate Limiters** (different limits per model per tier)
- ✅ **Tiered Pricing** (context-based pricing like Claude Sonnet 4.5)
- ✅ **Data Versions** (snapshots stored in package's `data_versions/` folder)
- ✅ **Simple API** (calculate, list, add - no CLI)

---

## 📁 Plan Documents

| Document | Description |
|----------|-------------|
| [PHASE_1_DATA_MODELS.md](./PHASE_1_DATA_MODELS.md) | Pydantic data models with rate limiter structure |
| [PHASE_2_STORAGE.md](./PHASE_2_STORAGE.md) | Local storage + data versions (snapshots) |
| [PHASE_3_REPOSITORY.md](./PHASE_3_REPOSITORY.md) | Simplified data access layer |
| [PHASE_4_PRICING_ENGINE.md](./PHASE_4_PRICING_ENGINE.md) | Price calculation with tiered pricing |
| [PHASE_5_SNAPSHOT.md](./PHASE_5_SNAPSHOT.md) | Snapshot management |
| [PHASE_6_PUBLIC_API.md](./PHASE_6_PUBLIC_API.md) | Main API class (LLMPricing) |
| [PROGRESS_CHECKLIST.md](./PROGRESS_CHECKLIST.md) | Detailed progress tracking |

---

## 🎯 Key Design Decisions

### 1. Standalone Package (Separate Repository)

This package lives in its **own Git repository**, not inside genai-prices:

```
llm_pricing/                    # Root of standalone repo
├── llm_pricing/                # Package source
│   ├── __init__.py
│   ├── models/
│   ├── storage/
│   └── ...
├── data_versions/              # Snapshots (shipped with package)
│   ├── 2025-11-30_120000.json  # Snapshot files
│   └── 2025-11-29_090000.json
├── pyproject.toml
├── README.md
└── tests/
```

### 2. Data Versions (Snapshots in Package)

**No external imports** - data is bundled with the package:

```
data_versions/
├── 2025-11-30_120000.json    # Latest (auto-loaded on init)
├── 2025-11-29_090000.json
└── 2025-11-28_180000.json
```

- On init: automatically load the **latest** data version file
- `store_snapshot()`: saves current local data to a new snapshot file
- Snapshots are **committed to git** and shipped with the package

### 3. Rate Limiters are Model-Based (Not Provider-Based)

```
Provider: Anthropic
├── Tier: Free
│   └── (no rate limiters at provider level)
└── Tier: Pro
    └── (no rate limiters at provider level)

Model: Claude Sonnet 4.5
├── Provider: Anthropic
└── Rate Limiters:
    ├── Tier "free":
    │   ├── RPM: 10
    │   └── TPM: 1,000,000
    └── Tier "pro":
        ├── RPM: 50
        └── TPM: 5,000,000
```

### 2. Rate Limiter Types

| Type | Description | Example |
|------|-------------|---------|
| `RPM` | Requests per minute | 60 |
| `TPM` | Tokens per minute (total) | 100,000 |
| `TPD` | Tokens per day | 1,000,000 |
| `ITPM` | Input tokens per minute | 80,000 |
| `OTPM` | Output tokens per minute | 20,000 |

### 3. Tiered Pricing (Like Claude Sonnet 4.5)

From `anthropic.yml`:
```yaml
prices:
  input_mtok:
    base: 3            # $3 per 1M tokens for first 200K
    tiers:
      - start: 200000  # After 200K tokens
        price: 6       # $6 per 1M tokens
```

**Calculation:** For 300K input tokens:
- First 200K tokens: 200,000 × $3 / 1M = $0.60
- Remaining 100K tokens: 100,000 × $6 / 1M = $0.60
- **Total: $1.20**

---

## 🏗️ Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                        Public API Layer                             │
│   LLMPricing (main entry point)                                    │
│   Methods: calculate, list_providers, list_models,                 │
│            add_provider, add_model, store_snapshot                 │
└────────────────────────────────────────────────────────────────────┘
        │                          │
        ↓                          ↓
┌─────────────────────┐  ┌─────────────────────────────────────────┐
│   Pricing Engine    │  │          Data Manager                    │
│   - calculate_price │  │   - add_provider()                       │
│   - tiered pricing  │  │   - add_model()                          │
│   - cache tokens    │  │   - store_snapshot()                     │
└─────────────────────┘  └─────────────────────────────────────────┘
        │                          │
        └──────────┬───────────────┘
                   ↓
┌────────────────────────────────────────────────────────────────────┐
│                     Repository Layer                                │
│   PricingRepository (data access, caching, queries)                │
└────────────────────────────────────────────────────────────────────┘
                   │
                   ↓
┌────────────────────────────────────────────────────────────────────┐
│                      Storage Layer                                  │
│   LocalStorage: ~/.llm_pricing/data.json (user's local data)       │
│   DataVersions: package/data_versions/*.json (bundled snapshots)   │
└────────────────────────────────────────────────────────────────────┘
```

### Storage Concept

```
User's Machine                    Package (Git Repo)
───────────────                   ──────────────────
~/.llm_pricing/                   llm_pricing/data_versions/
└── data.json  ←──── load ────── └── 2025-11-30_120000.json (latest)
    (working copy)                   (bundled snapshot)
         │
         └──── store_snapshot() ───→ Creates new snapshot file
                                     in data_versions/
```

---

## 📊 Data Model Overview

```
PricingDatabase
├── version: str
├── last_sync: datetime
├── providers: Dict[str, Provider]
│   └── Provider
│       ├── provider_id: str
│       ├── name: str
│       ├── tiers: Dict[str, ProviderTier]
│       │   └── ProviderTier
│       │       ├── tier_id: str
│       │       └── name: str (no rate limiters here!)
│       └── models: Dict[str, ModelInfo]
│           └── ModelInfo
│               ├── model_id: str
│               ├── pricing: Dict[str, ModelPrice]
│               │   └── ModelPrice (supports tiered pricing)
│               │       ├── input_mtok: TieredPrice | Decimal
│               │       ├── output_mtok: TieredPrice | Decimal
│               │       └── ...
│               └── rate_limiters: Dict[str, ModelRateLimits]  ← Per tier!
│                   └── ModelRateLimits
│                       ├── rpm: int
│                       ├── tpm: int
│                       ├── tpd: int
│                       ├── itpm: int
│                       └── otpm: int
└── metadata: Dict[str, str]
```

---

## 📅 Implementation Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| Phase 1 | 2-3 days | Data Models (Pydantic types with tiered pricing) |
| Phase 2 | 1-2 days | Storage Layer (Local + Data Versions) |
| Phase 3 | 1-2 days | Repository Pattern (data access) |
| Phase 4 | 2-3 days | Pricing Engine (tiered pricing calculation) |
| Phase 5 | 1-2 days | Data Manager (CRUD, snapshot) |
| Phase 6 | 1-2 days | Public API (simplified) |
| **Total** | **8-14 days** | Full implementation |

---

## 🎓 Key Concepts to Implement

### 1. Data Versions (Bundled Snapshots)

```python
# On initialization - auto-load latest snapshot
pricing = LLMPricing()  # Loads latest from data_versions/

# Store current local data as new snapshot
pricing.store_snapshot()  # Creates data_versions/2025-11-30_143022.json
```

### 2. Tiered Pricing (Like Claude Sonnet 4.5)

```python
# Simple price
input_mtok: Decimal("3.00")

# Tiered price
input_mtok: TieredPrice(
    base=Decimal("3.00"),
    tiers=[
        PriceTier(start=200_000, price=Decimal("6.00"))
    ]
)
```

### 3. Model-Based Rate Limiters

```python
model = ModelInfo(
    model_id="claude-sonnet-4-5",
    rate_limiters={
        "free": ModelRateLimits(rpm=10, tpm=1_000_000),
        "pro": ModelRateLimits(rpm=50, tpm=5_000_000),
        "enterprise": ModelRateLimits(rpm=1000, tpm=50_000_000)
    }
)
```

---

## 📁 Package Structure (Standalone Repository)

```
llm_pricing/                        # Git repository root
├── llm_pricing/                    # Python package
│   ├── __init__.py                 # LLMPricing class, public API
│   ├── models/                     # Pydantic data models
│   │   ├── __init__.py
│   │   ├── provider.py
│   │   ├── model.py
│   │   ├── pricing.py
│   │   └── rate_limit.py
│   ├── storage/                    # Storage layer
│   │   ├── __init__.py
│   │   ├── local_storage.py
│   │   └── data_versions.py
│   ├── repositories/               # Data access
│   │   └── ...
│   ├── engine/                     # Pricing calculations
│   │   └── ...
│   └── manager/                    # Data management
│       └── ...
├── data_versions/                  # Bundled snapshots (git tracked)
│   ├── 2025-11-30_120000.json
│   └── ...
├── tests/
├── pyproject.toml
└── README.md
```

---

## 🔑 Simplified API

Only these methods are needed:

```python
from llm_pricing import LLMPricing, TokenUsage

pricing = LLMPricing()

# 1. Calculate cost
usage = TokenUsage(input_tokens=5000, output_tokens=1500)
cost = pricing.calculate(
    provider="anthropic",
    model="claude-sonnet-4-20250514",
    usage=usage,
    tier="pro",
)

# 2. List providers (with all their data)
providers = pricing.list_providers()
# Returns: [Provider(id, name, tiers, models=[Model(pricing, rate_limits)])]

# 3. List models (with all their data)
models = pricing.list_models(provider="anthropic")
# Returns: [Model(id, name, pricing, rate_limits)]

# 4. Add provider
pricing.add_provider(id="custom", name="Custom Provider", tiers=["free"])

# 5. Add model
pricing.add_model(
    provider="custom",
    id="my-model",
    pricing={"input": 1.0, "output": 2.0},
    rate_limits={"free": {"RPM": 60, "TPM": 100000}},
)

# 6. Store snapshot (saves local data to data_versions/)
pricing.store_snapshot()
```

---

## ✅ Success Criteria

- [ ] Data versions folder with bundled snapshots
- [ ] Auto-load latest snapshot on init
- [ ] Supports tiered pricing (Claude Sonnet 4.5 style)
- [ ] Supports model-based rate limiters per tier
- [ ] Local storage for user modifications
- [ ] Calculate prices with tiered pricing support
- [ ] Simple API (6 methods only)
- [ ] `store_snapshot()` saves to data_versions/
- [ ] Unit tests with good coverage
- [ ] Documentation with examples

---

## 🚀 Getting Started

Start with **[PHASE_1_DATA_MODELS.md](./PHASE_1_DATA_MODELS.md)** to understand the data structure, then follow phases in order.

Track your progress in **[PROGRESS_CHECKLIST.md](./PROGRESS_CHECKLIST.md)**.
