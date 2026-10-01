"""
TrustGrid — Frozen Constants
All values are specified in the build specification and must not be changed
without explicit user instruction.
"""
import math

# ── Time Decay ────────────────────────────────────────────────────────────────
DECAY_HALF_LIFE_DAYS: int = 90
DECAY_LAMBDA: float = math.log(2) / DECAY_HALF_LIFE_DAYS  # ≈ 0.007701

# ── Cold Start ────────────────────────────────────────────────────────────────
INITIAL_TRUST_SCORE: int = 700  # 0–1000 scale
INITIAL_TRUST_SCORE_100: float = 70.0  # internal 0–100 scale

# ── Buyer Dimension Weights ───────────────────────────────────────────────────
BUYER_WEIGHTS: dict[str, float] = {
    "order_reliability":      0.25,
    "return_behaviour":       0.25,
    "payment_reliability":    0.20,
    "cancellation_behaviour": 0.15,
    "platform_engagement":    0.15,
}

# ── Seller Dimension Weights ──────────────────────────────────────────────────
SELLER_WEIGHTS: dict[str, float] = {
    "order_fulfillment":        0.25,
    "delivery_performance":     0.25,
    "customer_satisfaction":    0.20,
    "return_dispute_handling":  0.15,
    "platform_reliability":     0.15,
}

# ── ML Blending (β) ───────────────────────────────────────────────────────────
ML_BETA: dict[str, float] = {
    "LOW":    0.0,
    "MEDIUM": 0.3,
    "HIGH":   0.5,
}

# ── Smoothing (α) ─────────────────────────────────────────────────────────────
SMOOTHING_ALPHA: dict[str, float] = {
    "LOW":    0.2,
    "MEDIUM": 0.5,
    "HIGH":   0.8,
}

# ── Confidence Thresholds ─────────────────────────────────────────────────────
LOW_MAX_EVENTS: int = 5      # 0–5  → LOW
MEDIUM_MAX_EVENTS: int = 30  # 6–30 → MEDIUM
                              # 31+  → HIGH

# ── Tier Boundaries ───────────────────────────────────────────────────────────
TIER_BOUNDARIES: dict[str, tuple[int, int]] = {
    "RESTRICTED": (0,   399),
    "STANDARD":   (400, 599),
    "TRUSTED":    (600, 799),
    "ELITE":      (800, 1000),
}

# ── Buyer Events ──────────────────────────────────────────────────────────────
BUYER_EVENT_TYPES: list[str] = [
    "ORDER_PLACED",
    "ORDER_COMPLETED",
    "ORDER_CANCELLED",
    "PAYMENT_SUCCESS",
    "PAYMENT_FAILED",
    "RETURN_REQUESTED",
    "RETURN_COMPLETED",
    "REVIEW_SUBMITTED",
    "REFERRAL_COMPLETED",
]

# ── Seller Events ─────────────────────────────────────────────────────────────
SELLER_EVENT_TYPES: list[str] = [
    "ORDER_ACCEPTED",
    "ORDER_FULFILLED",
    "ORDER_SHIPPED",
    "ORDER_DELIVERED",
    "ORDER_LATE",
    "SELLER_CANCELLED",
    "RETURN_REQUEST_RECEIVED",
    "RETURN_RESOLVED",
    "REVIEW_RECEIVED",
    "PRODUCT_LISTED",
]

# ── Valid User Roles ──────────────────────────────────────────────────────────
ROLES: list[str] = ["buyer", "seller", "admin"]

# ── User ID Prefixes ──────────────────────────────────────────────────────────
BUYER_ID_PREFIX: str = "BUY"
SELLER_ID_PREFIX: str = "SEL"
ADMIN_ID_PREFIX: str = "ADM"
BUYER_ID_START: int = 10001
SELLER_ID_START: int = 20001
ADMIN_ID_START: int = 30001
