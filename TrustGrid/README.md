# TrustGrid

> **A Dynamic Trust Engine for E-Commerce Marketplaces**  
> *Turning Marketplace Behaviour into Trust.*

TrustGrid is an academic prototype of a dynamic, ML-assisted trust scoring and privilege engine for two-sided e-commerce marketplaces. It evaluates the behaviour of buyers and sellers and produces a transparent **Trust Score (0–1000)** backed by a **Confidence level (LOW/MEDIUM/HIGH)**, which together drive marketplace privileges.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Getting Started](#4-getting-started)
5. [Project Structure](#5-project-structure)
6. [Trust Score Methodology](#6-trust-score-methodology)
7. [ML Methodology](#7-ml-methodology)
8. [API Reference](#8-api-reference)
9. [Database Schema](#9-database-schema)
10. [Running Tests](#10-running-tests)
11. [Demo Scenarios](#11-demo-scenarios)
12. [Limitations & Future Scope](#12-limitations--future-scope)

---

## 1. Project Overview

### What TrustGrid Is

TrustGrid is **not** an e-commerce website. The primary product is a **Trust-as-a-Service prototype** — a scoring engine that sits behind a simple demo marketplace.

The demo marketplace exists only to generate the events that TrustGrid analyses.

### Core Outputs

| Output | Range | Meaning |
|---|---|---|
| **Trust Score** | 0–1000 | Composite behavioural reliability score |
| **Confidence** | LOW / MEDIUM / HIGH | How much evidence backs the score |
| **Tier** | RESTRICTED / STANDARD / TRUSTED / ELITE | Score bucket determining privilege level |
| **Benefits** | Per-tier list | Marketplace privileges unlocked |

### Key Design Principles

- **Recent behaviour matters more than old behaviour** — 90-day exponential half-life decay.
- **Reliability over frequency** — an infrequent buyer with perfect behaviour scores high.
- **Fair returns** — a single legitimate return is not penalised.
- **Evidence-gated privileges** — new users start at 700 but cannot unlock high-value benefits until evidence (confidence) is sufficient.
- **Explainability first** — every score change is explained in plain English.

---

## 2. Architecture

```
┌─────────────────────────────┐
│     DEMO E-COMMERCE SITE    │
│  Buyer / Seller UI (React)  │
└────────────┬────────────────┘
             │ REST API (/api)
             ▼
┌─────────────────────────────┐
│       FASTAPI BACKEND       │
│  Auth · Products · Orders   │
│  TrustGrid API              │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│        EVENT SERVICE        │
│  Records marketplace events │
│  with timestamps            │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│       FEATURE ENGINE        │
│  Aggregates events          │
│  Applies time decay         │
│  Produces feature vector    │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│          ML MODEL           │
│  XGBoost (pre-trained)      │
│  P(reliable) ∈ [0,1]        │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│        TRUST ENGINE         │
│  Dimension scores           │
│  ML blend · Smoothing       │
│  0–1000 Trust Score         │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│      PRIVILEGE ENGINE       │
│  Score + Confidence = Tier  │
│  Unlock / lock benefits     │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│         POSTGRESQL          │
│  Users · Events · Scores    │
│  Privileges · History       │
└─────────────────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, React Router v6, Axios, Recharts |
| **Backend** | Python 3.9, FastAPI, Pydantic v2, SQLAlchemy 2 |
| **Database** | PostgreSQL (SQLite for tests) |
| **Auth** | JWT (python-jose), bcrypt (passlib) |
| **ML** | XGBoost 2, scikit-learn, pandas, NumPy, joblib |
| **Tests** | pytest, pytest-env, httpx |

---

## 4. Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL 14+

### Backend Setup

```bash
cd TrustGrid/backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: set DATABASE_URL, SECRET_KEY

# Start the API server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend Setup

```bash
cd TrustGrid/frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### Database Setup

```bash
# Create the database (PostgreSQL must be running)
createdb trustgrid

# Tables are auto-created on first backend startup via SQLAlchemy create_all

# Populate with demo data
cd TrustGrid
python database/seed/seed.py
```

### Train the ML Models (optional — pre-trained models are included)

```bash
cd TrustGrid
python ml/run_pipeline.py
# Generates synthetic data, trains buyer and seller XGBoost models,
# saves to ml/models/buyer_model.joblib and seller_model.joblib
```

### Demo Credentials (after seeding)

| Role | Email | Password | Notes |
|---|---|---|---|
| Buyer | alice@demo.com | Demo1234! | High score, ELITE tier |
| Buyer | bob@demo.com | Demo1234! | Moderate score |
| Buyer | charlie@demo.com | Demo1234! | Low score (high cancellations) |
| Buyer | diana@demo.com | Demo1234! | New user, 700/LOW |
| Seller | seller1@demo.com | Demo1234! | Excellent seller |
| Seller | seller2@demo.com | Demo1234! | Average seller |
| Admin | admin@trustgrid.com | Demo1234! | Full admin access |

---

## 5. Project Structure

```
TrustGrid/
├── frontend/                    React + Vite frontend
│   └── src/
│       ├── components/          Reusable UI components
│       │   ├── common/          Navbar, ProtectedRoute, LoadingSpinner
│       │   └── trust/           TrustScoreGauge, DimensionBar
│       ├── pages/               Page components
│       │   ├── public/          Home, About, Login, Register
│       │   ├── buyer/           Dashboard, Products, Orders, TrustGrid, Profile
│       │   ├── seller/          Dashboard, Products, Orders, TrustGrid, Profile
│       │   └── admin/           AdminDashboard
│       ├── services/            API service wrappers
│       ├── hooks/               useAuth
│       ├── utils/               helpers.js (timeAgo, formatINR, etc.)
│       └── styles/              globals.css (CSS variables + design system)
│
├── backend/
│   └── app/
│       ├── main.py              FastAPI app entry point
│       ├── api/                 Route handlers (auth, products, orders, trust, admin)
│       ├── models/              SQLAlchemy ORM models
│       ├── schemas/             Pydantic request/response schemas
│       ├── services/            Business logic (user, order, trust, referral)
│       ├── core/                Config, security (JWT/bcrypt), dependencies
│       ├── db/                  Session management
│       └── trustgrid/           ← CORE ENGINE
│           ├── event_types.py   EventType enum (19 event types)
│           ├── event_service.py Record events + batch processing
│           ├── feature_engine.py Time-decayed feature computation
│           ├── trust_engine.py  Dimension scoring + weighted formula
│           ├── confidence_service.py Evidence-based confidence (LOW/MEDIUM/HIGH)
│           ├── privilege_engine.py  Benefit unlock/lock logic
│           ├── ml_service.py        XGBoost model inference wrapper
│           ├── explanation_service.py Human-readable score explanations
│           └── (event_types.py defines MEANINGFUL_EVENTS, NEGATIVE_EVENTS)
│
├── ml/
│   ├── run_pipeline.py          Master: generate → train → evaluate
│   ├── dataset/                 Synthetic data generation (6 buyer + 6 seller profiles)
│   ├── preprocessing/           Chronological train/val/test split
│   ├── training/                XGBoost training scripts
│   ├── evaluation/              Metrics: F1, ROC-AUC, confusion matrix
│   └── models/                  Saved .joblib model files
│
├── database/
│   └── seed/seed.py             Demo data seeder
│
└── docs/
    └── METHODOLOGY.md           Detailed methodology documentation
```

---

## 6. Trust Score Methodology

### Score Range and Tiers

| Tier | Score Range | Meaning |
|---|---|---|
| RESTRICTED | 0–399 | Significant reliability concerns |
| STANDARD | 400–599 | Developing track record |
| TRUSTED | 600–799 | Reliable marketplace participant |
| ELITE | 800–1000 | Exceptional reliability |

### New User Initial State

Every newly registered user starts at:

```
Trust Score: 700 / 1000
Confidence:  LOW
Tier:        TRUSTED
```

The initial score of 700 reflects a **neutral benefit of the doubt**. However, `LOW` confidence means high-value benefits are not granted until sufficient behavioural evidence accumulates.

### Buyer Dimensions (5 dimensions, weighted)

| Dimension | Weight | Measures |
|---|---|---|
| Order Reliability | 25% | Order completion rate (completed / placed) |
| Return Behaviour | 25% | Return rate — generous curve, normal returns not penalised |
| Payment Reliability | 20% | Payment success rate |
| Cancellation Behaviour | 15% | Cancellation rate |
| Platform Engagement | 15% | Referrals + reviews (only positive signals) |

**Critical design rules:**
- Low purchase frequency does **not** lower the score.
- A return rate ≤ 10% receives a perfect score on that dimension.
- Only abnormally high return rates (>30%) are penalised meaningfully.

### Seller Dimensions (5 dimensions, weighted)

| Dimension | Weight | Measures |
|---|---|---|
| Order Fulfillment | 25% | fulfilled / (fulfilled + seller_cancelled) |
| Delivery Performance | 25% | Low late-delivery rate → high score |
| Customer Satisfaction | 20% | Average star rating (new sellers: neutral 70) |
| Return & Dispute Handling | 15% | Return response rate |
| Platform Reliability | 15% | Products listed (positive signal) |

### Trust Score Formula

```
RawScore = 0.25×D1 + 0.25×D2 + 0.20×D3 + 0.15×D4 + 0.15×D5
TrustScore = clamp(round(10 × RawScore), 0, 1000)
```

Each dimension `Di` is in [0, 100], so `RawScore` ∈ [0, 100] and `TrustScore` ∈ [0, 1000].

### Time Decay

All behavioral features are weighted using exponential decay with a **90-day half-life**:

```
w(age) = exp(−λ × age_days)
λ = ln(2) / 90 ≈ 0.00770

w(0 days)   ≈ 1.000
w(30 days)  ≈ 0.794
w(90 days)  ≈ 0.500   ← half-life
w(180 days) ≈ 0.250
w(270 days) ≈ 0.125
```

This is implemented in [`feature_engine.py`](backend/app/trustgrid/feature_engine.py) and applied to every event before aggregation.

### Score Smoothing

To prevent wild swings after single events:

```
new_score = α × model_score + (1 − α) × previous_score
```

`α` (alpha) depends on confidence:
- LOW → α = 0.20 (model contributes 20%, history dominates)
- MEDIUM → α = 0.50 (balanced blend)
- HIGH → α = 0.80 (model's assessment strongly reflected)

### ML Blending

The XGBoost model provides `P(reliable)` ∈ [0, 1], mapped to [20, 100] scale:

```
ml_raw = 20 + P(reliable) × 80
```

Blended with the rule-based raw score:

```
β = 0.0 if evidence_weight < 1   (new user: pure rule-based)
β = 0.3 if evidence_weight 1–10  (early evidence: gentle ML influence)
β = 0.5 if evidence_weight > 10  (sufficient evidence: equal blend)

final_raw = β × ml_raw + (1 − β) × rule_raw
```

For sellers with no ratings yet, ML is bypassed entirely (rule-based only) to avoid the model treating "no rating" as "bad rating".

### Confidence Logic

| Level | Condition |
|---|---|
| LOW | 0–5 meaningful completed transactions |
| MEDIUM | 6–30 meaningful completed transactions |
| HIGH | 31+ meaningful completed transactions |

"Meaningful" events are completions, payments, deliveries — not mere placements.  
A soft age boost applies for accounts ≥30 days old with ≥4 events.

---

## 7. ML Methodology

### Model Choice: XGBoost

XGBoost is selected because it excels at:
- **Tabular behavioral data** — transaction-level aggregated features
- **Non-linear feature interactions** — e.g., high cancellation rate combined with low completion rate
- **Mixed numerical features** — rates, counts, weighted sums
- **Interpretability** — feature importance readily available
- **Relatively small datasets** — performs well on 1,000–10,000 samples

### Synthetic Dataset

Since no real private marketplace data is available, a synthetic dataset is generated using behaviorally realistic user profiles:

**Buyer profiles:** Reliable, Occasional-Reliable, Frequent-Returner, Frequent-Canceller, Poor-Payment, Mixed  
**Seller profiles:** Excellent, Reliable, Slow, High-Cancellation, Poor-Return-Handling, Mixed

Generated size: ~3,000 buyer feature vectors, ~1,500 seller feature vectors.

### Target Variable

The model predicts **future reliability**: whether a user's most recent transaction window is "reliable" (1) or "unreliable" (0), defined by:

```
reliable = 1 if recent_completion_rate ≥ 0.70 AND recent_cancellation_rate ≤ 0.30 AND recent_return_rate ≤ 0.20
```

Features use only historical behaviour; target uses recent behaviour — no data leakage.

### Train/Validation/Test Split

Chronological split (preserving temporal order):

```
Training:   70% (earliest records)
Validation: 15% (middle period)
Test:       15% (most recent)
```

### Evaluation Results

| Metric | Buyer Model | Seller Model |
|---|---|---|
| F1 Score | 0.9855 | 0.9977 |
| ROC-AUC | 0.9981 | 1.0000 |

Note: These high scores reflect the nature of synthetic data with clear behavioral patterns. Real-world performance would differ.

### Data Leakage Prevention

All features used for prediction are computed from **past events only**. The target variable is derived from the **most recent** transaction window, which is excluded from the feature computation window. This mirrors real-world deployment: predict future reliability from historical behaviour.

---

## 8. API Reference

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | None | Register buyer/seller |
| POST | `/auth/login` | None | Login, receive JWT |
| GET | `/auth/me` | JWT | Current user profile |

### Marketplace

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/products` | JWT | List products |
| POST | `/products` | Seller JWT | Create product |
| GET | `/products/{id}` | JWT | Get product detail |
| POST | `/orders` | Buyer JWT | Place order (simulated payment) |
| GET | `/orders` | JWT | List orders for current user |
| POST | `/orders/{id}/cancel` | JWT | Cancel order |
| POST | `/orders/{id}/ship` | Seller JWT | Mark order shipped |
| POST | `/orders/{id}/complete` | Buyer JWT | Confirm receipt |
| POST | `/orders/{id}/return` | Buyer JWT | Request return |
| POST | `/orders/{id}/review` | Buyer JWT | Submit review |

### TrustGrid

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/trust/me` | JWT | Current user's full trust profile |
| GET | `/trust/{user_id}` | JWT (own) | Trust profile by ID |
| GET | `/trust/{user_id}/history` | JWT (own) | Score change history |
| GET | `/trust/{user_id}/breakdown` | JWT (own) | Per-dimension scores + recommendations |
| GET | `/trust/{user_id}/benefits` | JWT (own) | Active/inactive privileges |
| GET | `/trust/{user_id}/explain` | JWT (own) | Human-readable explanation |
| POST | `/trust/referral` | Buyer JWT | Claim referral reward |

### Admin

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/admin/analytics` | Admin JWT | Platform-wide analytics |
| GET | `/admin/users` | Admin JWT | User list with trust data |
| GET | `/admin/trust-distribution` | Admin JWT | Score histogram (10 buckets) |

### Trust Profile Response Example

```json
{
  "user_id": "BUY-10024",
  "trust_score": 824,
  "confidence": "HIGH",
  "tier": "ELITE",
  "breakdown": {
    "order_reliability": 92.0,
    "return_behaviour": 81.0,
    "payment_reliability": 95.0,
    "cancellation_behaviour": 84.0,
    "platform_engagement": 88.0
  },
  "recent_changes": [
    { "score_change": 18, "reason": "Order successfully completed.", "created_at": "..." }
  ],
  "benefits": ["COD_AVAILABLE", "EXCLUSIVE_VOUCHER", "FREE_DELIVERY", "PRIORITY_SUPPORT"]
}
```

---

## 9. Database Schema

### Core Tables

**`users`** — registered accounts  
`id`, `user_id` (BUY-/SEL- prefix), `name`, `email`, `password_hash`, `role`, `created_at`

**`trust_scores`** — current trust state  
`id`, `user_id` (FK), `trust_score`, `confidence`, `tier`, `dim_scores` (JSON), `last_updated`

**`trust_events`** — immutable event log  
`id`, `event_id`, `user_id` (FK), `event_type`, `reference_id`, `metadata_` (JSON), `impact_summary`, `created_at`

**`behavior_features`** — materialized feature vector (recalculated on each event)  
`id`, `user_id` (FK), `total_orders`, `order_completion_rate`, `return_rate`, `payment_success_rate`, `cancellation_rate`, `fulfillment_rate`, `late_delivery_rate`, `avg_rating_received`, `decayed_event_weight`, *(+ all other feature columns)*

**`score_history`** — score change audit trail  
`id`, `user_id` (FK), `old_score`, `new_score`, `score_change`, `reason`, `event_type`, `created_at`

**`privileges`** — benefit unlock status  
`id`, `user_id` (FK), `privilege_name`, `status` (active/inactive), `reason`, `updated_at`

**Marketplace tables:** `products`, `orders`, `payments`, `returns`, `reviews`, `referrals`

---

## 10. Running Tests

```bash
cd TrustGrid/backend
source .venv/bin/activate

# Run all 230 tests
pytest -v

# Run a specific phase
pytest tests/test_phase16_full_suite.py -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

**Test categories:**
- Phase 2: Authentication + user ID generation (28 tests)
- Phase 3: Marketplace order lifecycle (27 tests)
- Phase 4: Event system (26 tests)
- Phase 5: Feature engine + time decay (29 tests)
- Phase 6: Trust engine + confidence + privileges (57 tests)
- Phase 16: End-to-end scenarios + ML + admin + authorization (63 tests)

All tests use an isolated SQLite in-memory/file database — no PostgreSQL required.

---

## 11. Demo Scenarios

### Scenario 1 — New Buyer
1. Register with role=buyer
2. Observe: `trust_score=700`, `confidence=LOW`, `tier=TRUSTED`
3. Visit TrustGrid Dashboard — benefits are locked (insufficient confidence)

### Scenario 2 — Good Buyer Behaviour
1. Login as `alice@demo.com`
2. Observe high score, HIGH confidence, ELITE tier
3. Browse Products → Buy Now → Score updates
4. TrustGrid Dashboard shows: "Your recent successful activity has improved your score."

### Scenario 3 — Negative Behaviour
1. Login as `charlie@demo.com`
2. Observe lower score due to cancellation history
3. See score breakdown — Cancellation Behaviour dimension is lower
4. Score history explains each change

### Scenario 4 — Seller Lifecycle
1. Login as `seller1@demo.com`
2. View Seller TrustGrid Dashboard — ELITE tier, all benefits active
3. Observe: "Trusted Seller" badge is unlocked
4. Go to Orders — Ship an order — score updates

### Scenario 5 — Time Decay
1. Login as `bob@demo.com` (has back-dated historical orders)
2. Observe: older orders contribute less to dimension scores than recent ones
3. TrustGrid Explanation shows: "Recent activity has a greater influence on your Trust Score."

### Scenario 6 — Admin Analytics
1. Login as `admin@trustgrid.com`
2. Navigate to `/admin`
3. View: buyer/seller counts, average scores, tier distributions, confidence distribution, recent changes

---

## 12. Limitations & Future Scope

### Current Limitations

- **Synthetic data**: The ML model is trained entirely on synthetic data. Performance on real-world marketplace data would likely differ.
- **No real payments**: Payments are simulated with a fixed 95% success rate.
- **No anomaly detection**: Sudden account takeovers or rapid behavioral changes are not flagged.
- **No cross-platform reputation**: Trust Score is isolated to this marketplace.
- **Prototype scale**: Not designed for high-concurrency production use.
- **Bias in synthetic data**: The behavioral profiles in the training data reflect manually defined patterns, which may not capture the full range of real human behavior.

### Future Enhancements

- **Anomaly detection**: Isolation Forest or LSTM-based drift detection for sudden behavioral changes
- **Advanced fraud detection**: Graph-based analysis of user interaction networks
- **Real-time streaming**: Kafka/event streaming for high-volume deployments
- **Deep learning**: Sequence modeling (LSTM/Transformer) for temporal behavioral patterns
- **Cross-platform reputation**: Allow trust scores to transfer across partner marketplaces
- **Model retraining pipeline**: Automated retraining as new behavioral data accumulates
- **Advanced fairness auditing**: Ensure no demographic bias in scoring
- **A/B testing of privilege policies**: Experiment with different benefit thresholds
- **Seller reputation for international deliveries**: Different decay rates for cross-border orders

---

## Academic Positioning

TrustGrid is presented as a **prototype dynamic trust assessment engine**, not a production fraud-detection system. Its academic contribution lies in the **integration** of:

1. Multi-dimensional behavioral scoring
2. Exponential time decay (CIBIL-style temporal weighting)
3. ML-based reliability estimation (XGBoost)
4. Confidence-gated privilege allocation
5. Explainable score changes in user-facing language

This integration is positioned against traditional marketplace reputation mechanisms (static ratings, review counts, feedback scores) which lack temporal sensitivity and behavioral depth.

---

*TrustGrid — Academic prototype. Not a production product.*
