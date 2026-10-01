# TrustGrid

A dynamic, ML-assisted trust and privilege engine for a two-sided e-commerce marketplace.

## Quick Start

### Backend

```bash
cd TrustGrid

# 1. Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# 4. Start the API (requires PostgreSQL running)
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### ML Pipeline

```bash
# Generate synthetic dataset
PYTHONPATH=backend python ml/dataset/generate.py

# Train XGBoost models
PYTHONPATH=backend python ml/training/train.py
```

### Frontend

```bash
cd frontend/ecommerce-demo
npm install
npm run dev   # → http://localhost:5173
```

### Tests

```bash
cd TrustGrid
source .venv/bin/activate
PYTHONPATH=backend pytest backend/tests/ -v
```

## Architecture

```
React + Vite (Frontend)
    ↓ REST
FastAPI (Backend)
    ↓
Feature Engine → Time Decay → Dimension Scorer → Rule Score
                                                ↓
                                          XGBoost ML
                                                ↓
                                        Trust Engine
                                (blend, smooth, clamp 0-1000)
                                                ↓
                                   Tier → Privileges → Explanation
                                                ↓
                                          PostgreSQL
```

## Key Formulas (Frozen)

| Formula | Value |
|---------|-------|
| Decay | `w = e^(−λt)`, λ = ln(2)/90 ≈ 0.007701 |
| RuleScore | `0.25D1 + 0.25D2 + 0.20D3 + 0.15D4 + 0.15D5` |
| CombinedScore | `(1−β)·RuleScore + β·MLScore` |
| Smoothing | `(1−α)·PreviousScore + α·CombinedScore` |
| TrustScore | `clamp(round(new100 × 10), 0, 1000)` |

| Confidence | Events | β | α |
|-----------|--------|---|---|
| LOW | 0–5 | 0.0 | 0.2 |
| MEDIUM | 6–30 | 0.3 | 0.5 |
| HIGH | 31+ | 0.5 | 0.8 |

## Tier Boundaries

| Score | Tier |
|-------|------|
| 0–399 | RESTRICTED |
| 400–599 | STANDARD |
| 600–799 | TRUSTED |
| 800–1000 | ELITE |

## Test Results

- Time Decay: **24/24 pass**
- Dimension Scorer: **17/17 pass**
- Trust Core (confidence, tier, blending, smoothing, privileges): **38/38 pass**
- Integration + Security + ML: **16/16 pass**
- **Total: 95/95 tests pass**
