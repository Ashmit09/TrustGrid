# TrustGrid — Technical Methodology

## 1. Abstract

TrustGrid is a prototype dynamic trust assessment engine for two-sided e-commerce marketplaces. It moves beyond static star ratings by combining multi-dimensional behavioural scoring, exponential time decay, XGBoost-based reliability prediction, evidence-gated confidence levels, and human-readable score explanations into a unified scoring pipeline. This document describes the technical methodology in detail.

---

## 2. Problem Statement

Existing marketplace reputation systems primarily rely on:
- **Aggregate star ratings** — static averages that treat a 5-star review from 2 years ago identically to one from yesterday.
- **Review counts** — easily manipulated, slow to reflect recent behavioural change.
- **Transaction history totals** — reward volume over reliability.

These mechanisms do not address:
- Temporal sensitivity (recent behaviour should matter more).
- Confidence in scores (a score from 2 transactions is very different from a score from 200 transactions).
- Explainability (users cannot see *why* their score changed).
- Bidirectional scoring (both buyers *and* sellers should be evaluated).

---

## 3. Objectives

1. Design a quantitative trust score (0–1000) based on observed marketplace behaviour.
2. Implement exponential time decay so recent events dominate older ones.
3. Use machine learning (XGBoost) to estimate behavioural reliability from aggregated features.
4. Produce a Confidence level (LOW/MEDIUM/HIGH) that reflects evidence quality.
5. Gate marketplace privileges on both score and confidence.
6. Explain score changes to users in plain language.
7. Demonstrate the complete pipeline through a functional prototype.

---

## 4. System Architecture

The TrustGrid pipeline processes marketplace events as follows:

```
Marketplace Action (e.g., order placed)
    │
    ▼
Event Service
  - Validates action
  - Records TrustEvent row (immutable, timestamped)
  - Commits event to database
    │
    ▼
Feature Engine
  - Queries all events for the affected user
  - Applies exponential time decay to each event
  - Aggregates decayed events into a 24-field feature vector
  - Persists feature vector to behavior_features table
    │
    ▼
ML Service (XGBoost)
  - Loads pre-trained buyer or seller model
  - Runs inference on feature vector
  - Returns P(reliable) ∈ [0, 1]
    │
    ▼
Trust Engine
  - Computes 5 dimension scores (0–100 each)
  - Blends ML probability with rule-based scores (β-weighted)
  - Applies weighted formula: TrustScore = 10 × (Σ wᵢ × Dᵢ)
  - Applies score smoothing: new = α × model + (1−α) × old
  - Clamps result to [0, 1000]
  - Persists updated TrustScore + ScoreHistory entry
    │
    ▼
Confidence Service
  - Counts meaningful behavioral events
  - Returns LOW / MEDIUM / HIGH
    │
    ▼
Privilege Engine
  - Evaluates score + confidence against benefit thresholds
  - Updates active/inactive status for all privileges
    │
    ▼
Explanation Service
  - Identifies strongest and weakest dimensions
  - Generates plain-English driving factors
  - Produces improvement recommendations
```

Only the user associated with the triggering event has their features and score recalculated. Other users are unaffected.

---

## 5. Functional Requirements

### 5.1 Users
- Register as buyer or seller
- Receive a unique user_id (BUY-10001 / SEL-20001 format)
- Authenticate via JWT
- View their TrustGrid dashboard

### 5.2 Marketplace
- List and browse products
- Place orders with simulated payment (95% success rate)
- Cancel, ship, complete, return, and review orders
- Refer other users

### 5.3 TrustGrid Engine
- Record 19 distinct event types
- Calculate behavioural features with time decay
- Run XGBoost model inference
- Compute 5-dimension weighted trust score
- Calculate confidence level from evidence count
- Determine tier and unlock/lock privileges
- Store complete score history
- Return human-readable explanations

### 5.4 Admin
- View aggregate platform analytics
- See tier distributions for buyers and sellers
- Monitor confidence distribution
- Inspect recent score changes

---

## 6. Non-Functional Requirements

| Requirement | Approach |
|---|---|
| Security | Bcrypt password hashing, JWT auth, HTTPS-ready |
| Privacy | No sensitive financial data stored; simulated payments only |
| Isolation | Only affected user's score is recalculated per event |
| Testability | 230 automated tests, SQLite for test isolation |
| Explainability | Every score change has a human-readable reason |
| Fairness | No demographic attributes used in scoring |
| Correctness | Score clamped to [0, 1000], tier boundaries deterministic |

---

## 7. Database Design

### Entity-Relationship Summary

```
users  ──< trust_events
users  ──  trust_scores
users  ──< score_history
users  ──< privileges
users  ──< behavior_features
users  ──< products (sellers)
users  ──< orders (buyers)
orders ──< payments
orders ──< returns
orders ──< reviews
users  ──< referrals
```

### Key Design Decisions

**Immutable event log**: `trust_events` is append-only. Events are never deleted or modified. This allows complete audit trails and retrospective feature recalculation.

**Materialized feature vector**: Rather than recalculating features from raw events on every score request, features are persisted in `behavior_features` after each event. This makes reads fast.

**Score history**: Every score change is recorded in `score_history` with the triggering event type and a human-readable reason string.

**JSON dimension scores**: The `trust_scores.dim_scores` column stores per-dimension values as JSON, avoiding a second query for breakdowns.

---

## 8. API Design

All endpoints are REST, returning JSON. Authentication uses `Authorization: Bearer <JWT>` headers.

Endpoint naming follows the pattern:
- `/auth/*` — Authentication
- `/products/*` — Product catalog
- `/orders/*` — Order lifecycle
- `/trust/*` — TrustGrid scoring
- `/admin/*` — Administrative analytics

Error responses follow HTTP conventions (400/401/403/404/409/500) with `{"detail": "..."}` bodies. No internal error details are exposed to clients.

---

## 9. Trust Score Methodology

### 9.1 Dimensions and Weights

**Buyer (5 dimensions):**

| # | Dimension | Weight | Formula |
|---|---|---|---|
| D1 | Order Reliability | 25% | _rate_to_score(completion_rate) |
| D2 | Return Behaviour | 25% | Generous piecewise curve on return_rate |
| D3 | Payment Reliability | 20% | _rate_to_score(payment_success_rate) |
| D4 | Cancellation Behaviour | 15% | Piecewise on cancellation_rate |
| D5 | Platform Engagement | 15% | 60 + min(40, referrals×8) + min(40, reviews×4) |

**Seller (5 dimensions):**

| # | Dimension | Weight | Formula |
|---|---|---|---|
| D1 | Order Fulfillment | 25% | _rate_to_score(fulfillment_rate) |
| D2 | Delivery Performance | 25% | Piecewise on late_delivery_rate |
| D3 | Customer Satisfaction | 20% | 20 + (avg_rating−1)/4 × 80 (neutral 70 if no ratings) |
| D4 | Return & Dispute Handling | 15% | _rate_to_score(return_response_rate) |
| D5 | Platform Reliability | 15% | 60 + min(40, products_listed×5) |

`_rate_to_score(r) = max(20, min(100, 20 + r×80))`

This linear mapping ensures a minimum dimension score of 20 (prevents zero scores) and a maximum of 100.

### 9.2 Return Behaviour — Non-Penalising Design

The return curve is intentionally generous:
```
return_rate ≤ 0.10  → D2 = 100  (normal returns, full score)
return_rate ≤ 0.30  → D2 = 100 − (rr − 0.10)/0.20 × 40  (80–100)
return_rate  > 0.30  → D2 = max(20, 60 − (rr − 0.30)/0.70 × 40)  (20–60)
```

A buyer who returns 1 in 10 orders does not have their score harmed. Only buyers with systematically high return rates (>30%) see meaningful impact.

### 9.3 Infrequent Buyer Protection

Purchase frequency is explicitly excluded as a feature. The only rate-based features measure *reliability of action when taken*. A buyer who makes 1 purchase per year with 100% completion receives the same dimension scores as a daily buyer with equal rates.

### 9.4 Time Decay Implementation

```python
_HALF_LIFE_DAYS = 90.0
_LAMBDA = math.log(2) / _HALF_LIFE_DAYS   # ≈ 0.007702

def decay_weight(event_time: datetime, now: datetime) -> float:
    age_days = max(0.0, (now - event_time).total_seconds() / 86_400)
    return math.exp(-_LAMBDA * age_days)
```

Decay is applied per-event during feature aggregation. The `decayed_event_weight` field in the feature vector represents the total sum of all event decay weights — used as evidence volume for blending and confidence.

### 9.5 Score Smoothing

Alpha values by confidence:
```python
_ALPHA = {
    ConfidenceLevel.LOW:    0.20,
    ConfidenceLevel.MEDIUM: 0.50,
    ConfidenceLevel.HIGH:   0.80,
}
```

For a new user with LOW confidence, after their first order:
- model_score might be 750
- old_score = 700
- smoothed = 0.20 × 750 + 0.80 × 700 = 150 + 560 = **710**

This prevents a single event from causing a large jump.

### 9.6 New User Handling

New users receive 700/LOW at registration. Their `BehaviorFeatures` row is initialised with neutral defaults (all rates = 1.0, all counts = 0). The ML model gets β = 0 for evidence_weight < 1, so it does not affect the initial 700 score.

---

## 10. ML Methodology

### 10.1 Feature Vector (11 buyer features, 12 seller features)

**Buyer features:**
- `order_completion_rate` — decayed-weighted completions / placements
- `return_rate` — decayed returns / completions
- `payment_success_rate` — decayed successes / attempts
- `cancellation_rate` — decayed cancellations / placements
- `referral_count` — integer count (permanent)
- `review_count` — integer count (permanent)
- `total_orders`, `completed_orders`, `total_cancellations`, `total_returns`
- `decayed_event_weight` — total sum of all decay weights (evidence volume)

**Seller features:**
- `fulfillment_rate`, `late_delivery_rate`, `avg_rating_received`
- `return_response_rate`, `products_listed`
- `fulfilled_orders`, `seller_cancellations`, `on_time_deliveries`
- `late_deliveries`, `return_requests_received`, `returns_responded`
- `decayed_event_weight`

### 10.2 Synthetic Data Generation

Behavioral profiles define the probability distributions for event generation:

```python
# Example: Reliable Buyer profile
"order_completion_rate":   Normal(mean=0.95, std=0.03)
"payment_success_rate":    Normal(mean=0.97, std=0.02)
"cancellation_rate":       Normal(mean=0.04, std=0.02)
"return_rate":             Normal(mean=0.03, std=0.01)
```

For each generated user (300–1000 users per profile), historical event sequences are simulated. Timestamps span 6–18 months, with realistic temporal clustering.

### 10.3 Target Construction

```python
def build_target(user_events, cutoff_date):
    recent = [e for e in user_events if e.date >= cutoff_date]
    if not recent:
        return None  # exclude users with no recent events
    
    recent_completion_rate = recent_completed / recent_placed
    recent_cancellation_rate = recent_cancelled / recent_placed
    recent_return_rate = recent_returns / max(1, recent_completed)
    
    reliable = (
        recent_completion_rate >= 0.70 and
        recent_cancellation_rate <= 0.30 and
        recent_return_rate <= 0.20
    )
    return 1 if reliable else 0
```

Features are computed from all events *before* the cutoff date; the target uses events *after* — preventing data leakage.

### 10.4 Model Training

```python
xgb.XGBClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
)
```

Hyperparameters were set based on the dataset scale (3,000 samples) and the nature of the problem (tabular, moderate feature count, no deep non-linearity expected).

### 10.5 Model Persistence and Loading

Models are saved with `joblib.dump()` to `ml/models/buyer_model.joblib` and `seller_model.joblib`. The backend loads them lazily on first inference call via a singleton pattern:

```python
_buyer_model  = None
_models_loaded = False

def _load_models():
    global _buyer_model, _models_loaded
    if _models_loaded:
        return
    if _BUYER_MODEL_PATH.exists():
        _buyer_model = joblib.load(_BUYER_MODEL_PATH)
    _models_loaded = True
```

If models are missing (e.g., first run before training), the backend gracefully falls back to rule-based scoring.

---

## 11. Explainability

Users never see raw ML probability values. The `explanation_service.py` module:

1. Examines the feature vector for significant signals:
   - `order_completion_rate` > 0.9 → "Strong order completion history"
   - `cancellation_rate` > 0.2 → "Recent cancellation rate is affecting your score"
2. Identifies the strongest and weakest dimensions from `dim_scores`.
3. Generates rule-based recommendations based on the weakest dimension.
4. Returns: `driving_factors`, `strongest_dimensions`, `weakest_dimensions`, `recommendations`, `time_decay_note`.

The `time_decay_note` always reads:
> "Recent activity has a greater influence on your Trust Score than older activity. This score reflects a 90-day half-life decay of your behavioural history."

---

## 12. Confidence Methodology

Confidence is deterministic, not probabilistic:

```python
def calculate_confidence(db, user_id, account_created_at):
    meaningful_count = db.query(TrustEvent).filter(
        TrustEvent.user_id == user_id,
        TrustEvent.event_type.in_(MEANINGFUL_EVENTS)
    ).count()
    
    if meaningful_count >= 31:
        return ConfidenceLevel.HIGH
    if meaningful_count >= 6:
        return ConfidenceLevel.MEDIUM
    
    # Soft boost for older accounts with some evidence
    if account_age_days >= 30 and meaningful_count >= 4:
        return ConfidenceLevel.MEDIUM
    
    return ConfidenceLevel.LOW
```

MEANINGFUL_EVENTS = {ORDER_COMPLETED, ORDER_DELIVERED, PAYMENT_SUCCESS, RETURN_RESOLVED, REFERRAL_COMPLETED}

---

## 13. Privilege Engine

Benefits are centralized in `privilege_engine.py`. Each benefit has threshold rules:

**Buyer benefits:**

| Benefit | Primary Condition | Alternative |
|---|---|---|
| COD_AVAILABLE | score ≥ 600 AND confidence ≥ MEDIUM | score ≥ 750 |
| EXCLUSIVE_VOUCHER | score ≥ 700 AND confidence ≥ MEDIUM | — |
| FREE_DELIVERY | score ≥ 800 AND confidence ≥ HIGH | — |
| PRIORITY_SUPPORT | score ≥ 800 AND confidence ≥ HIGH | — |

**Seller benefits:**

| Benefit | Condition |
|---|---|
| SEARCH_VISIBILITY | score ≥ 700 AND confidence ≥ MEDIUM |
| TRUSTED_BADGE | score ≥ 700 AND confidence ≥ MEDIUM |
| REDUCED_PLATFORM_FEE | score ≥ 800 AND confidence ≥ HIGH |
| PROMOTIONAL_CREDITS | score ≥ 800 AND confidence ≥ HIGH |

A new user at 700/LOW receives **no active benefits** — they must build evidence to unlock even basic benefits. This prevents brand-new accounts from accessing privilege-gated features.

---

## 14. Testing Strategy

### Test Categories

1. **Unit tests** — individual functions (decay_weight, _clamp, score_to_tier, etc.)
2. **Integration tests** — service layer calling DB (create_user, place_order, etc.)
3. **API tests** — HTTP-level tests using FastAPI's TestClient
4. **Scenario tests** — end-to-end flows (new buyer, good behaviour, negative behaviour, etc.)
5. **Boundary tests** — score never < 0, never > 1000; confidence monotonic

### Test Isolation

All tests use SQLite (file-based per test function) via a fixture that swaps the global SQLAlchemy engine. PostgreSQL is only required for production. Tests run without any external dependencies.

### Key Test Cases

```python
# New user
assert user.trust_score == 700
assert user.confidence == ConfidenceLevel.LOW

# Score never exceeds bounds
assert 0 <= trust_score <= 1000

# Time decay working
recent_weight > old_weight

# Infrequent buyer not penalised
assert dimension_scores_for_perfect_1_order == all_100

# Confidence escalates deterministically
LOW → MEDIUM at 6+ meaningful events
MEDIUM → HIGH at 31+ meaningful events
```

---

## 15. Results and Evaluation

### ML Performance

| Metric | Buyer Model | Seller Model |
|---|---|---|
| Precision | 0.9863 | 0.9977 |
| Recall | 0.9847 | 0.9977 |
| F1 Score | 0.9855 | 0.9977 |
| ROC-AUC | 0.9981 | 1.0000 |

These metrics reflect synthetic data with well-separated behavioral profiles. Real-world data would show lower but still meaningful predictive performance.

### System Tests

- 230 automated tests, all passing
- Average test run: ~62 seconds
- Coverage: core TrustGrid modules fully covered

---

## 16. Limitations

1. **Synthetic training data** — the XGBoost model may not generalise to real-world behavioral distributions.
2. **No real payment processing** — payment events are simulated.
3. **No anomaly detection** — the system does not flag sudden behavioural shifts.
4. **Simplified privilege rules** — real marketplaces would have more nuanced benefit criteria.
5. **No model fairness audit** — demographic impact has not been tested.
6. **Single-marketplace scope** — trust does not transfer across platforms.
7. **SQLite for tests** — some PostgreSQL-specific features (e.g., JSONB operators) are not tested.

---

## 17. Future Scope

| Enhancement | Rationale |
|---|---|
| Anomaly detection (Isolation Forest) | Detect sudden changes suggesting account takeover |
| LSTM/Transformer sequence model | Model temporal order of events, not just aggregates |
| Graph-based trust network | Detect collusion rings and fake referral chains |
| Kafka event streaming | Real-time scoring at marketplace scale |
| Model retraining pipeline | Keep model current as user behaviour evolves |
| SHAP explainability | Feature importance visible in admin dashboard |
| Fairness auditing | Ensure scores do not proxy for demographic attributes |
| Cross-platform reputation | Allow trust to transfer between partner platforms |

---

## 18. Conclusion

TrustGrid demonstrates that a meaningful, dynamic trust score can be constructed from observable marketplace behaviour using:

- A well-designed event taxonomy (19 event types)
- Time-decayed feature aggregation (90-day half-life)
- A supervised ML model for reliability estimation (XGBoost, F1=0.9855)
- Multi-dimensional weighted scoring with explicit formulas
- Evidence-gated confidence and privilege allocation
- Plain-language explainability for end users

The result is a prototype that presents trust not as a simple star average, but as a dynamic, evidence-backed, behaviorally-grounded assessment — with every component traceable, testable, and explainable.

---

*TrustGrid — Academic prototype. Not for production deployment.*
