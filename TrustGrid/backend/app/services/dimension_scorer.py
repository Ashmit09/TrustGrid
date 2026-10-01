"""
TrustGrid — Dimension Scorer

Converts a feature dict into five 0–100 dimension scores for a given role.

Buyer dimensions (spec §5):
    D1 order_reliability      = 100 × decayed_completion_rate
    D2 return_behaviour       = 100 × (1 − decayed_problematic_return_rate)
    D3 payment_reliability    = 100 × decayed_payment_success_rate
    D4 cancellation_behaviour = 100 × (1 − decayed_cancellation_rate)
    D5 platform_engagement    = 100 × engagement_quality

Seller dimensions (spec §6):
    D1 order_fulfillment        = 100 × decayed_fulfillment_rate
    D2 delivery_performance     = 100 × (1 − decayed_late_delivery_rate)
    D3 customer_satisfaction    = 100 × (avg_rating_decayed − 1) / 4
    D4 return_dispute_handling  = 100 × decayed_resolution_rate
    D5 platform_reliability     = 100 × platform_reliability

Every dimension is clamped to [0, 100].
"""
from typing import Dict

from app.core.constants import BUYER_WEIGHTS, SELLER_WEIGHTS


def _clamp(value: float) -> float:
    """Clamp a dimension to [0, 100]."""
    return max(0.0, min(100.0, value))


# ── Buyer ─────────────────────────────────────────────────────────────────────

def buyer_dimensions(features: Dict) -> Dict[str, float]:
    """
    Return a dict of five buyer dimension scores, each in [0, 100].
    `features` is the output of feature_engine.build_buyer_features().
    """
    d1 = _clamp(100.0 * features["decayed_completion_rate"])
    d2 = _clamp(100.0 * (1.0 - features["decayed_problematic_return_rate"]))
    d3 = _clamp(100.0 * features["decayed_payment_success_rate"])
    d4 = _clamp(100.0 * (1.0 - features["decayed_cancellation_rate"]))
    d5 = _clamp(100.0 * features["engagement_quality"])

    return {
        "order_reliability":      round(d1, 4),
        "return_behaviour":       round(d2, 4),
        "payment_reliability":    round(d3, 4),
        "cancellation_behaviour": round(d4, 4),
        "platform_engagement":    round(d5, 4),
    }


# ── Seller ────────────────────────────────────────────────────────────────────

def seller_dimensions(features: Dict) -> Dict[str, float]:
    """
    Return a dict of five seller dimension scores, each in [0, 100].
    `features` is the output of feature_engine.build_seller_features().

    For customer_satisfaction:
        1 star → 0, 3 stars → 50, 5 stars → 100
        D3 = 100 × (avg_rating − 1) / 4
    """
    d1 = _clamp(100.0 * features["decayed_fulfillment_rate"])
    d2 = _clamp(100.0 * (1.0 - features["decayed_late_delivery_rate"]))

    avg_rating = features["avg_rating_decayed"]          # 1.0 – 5.0
    d3 = _clamp(100.0 * (avg_rating - 1.0) / 4.0)       # spec §6 formula

    d4 = _clamp(100.0 * features["decayed_resolution_rate"])
    d5 = _clamp(100.0 * features["platform_reliability"])

    return {
        "order_fulfillment":       round(d1, 4),
        "delivery_performance":    round(d2, 4),
        "customer_satisfaction":   round(d3, 4),
        "return_dispute_handling": round(d4, 4),
        "platform_reliability":    round(d5, 4),
    }


# ── RuleScore ─────────────────────────────────────────────────────────────────

def compute_rule_score(dimensions: Dict[str, float], role: str) -> float:
    """
    Compute the weighted RuleScore from five dimensions.

    RuleScore = w1·D1 + w2·D2 + w3·D3 + w4·D4 + w5·D5   (0–100)

    Weights are frozen in constants.BUYER_WEIGHTS / SELLER_WEIGHTS.
    """
    weights = BUYER_WEIGHTS if role == "buyer" else SELLER_WEIGHTS
    score = sum(weights[dim] * dimensions[dim] for dim in weights)
    return max(0.0, min(100.0, score))


# ── Dispatcher ────────────────────────────────────────────────────────────────

def calculate_dimensions(features: Dict, role: str) -> Dict[str, float]:
    """Return five dimension scores for the given role."""
    if role == "buyer":
        return buyer_dimensions(features)
    elif role == "seller":
        return seller_dimensions(features)
    else:
        raise ValueError(f"Unknown role: {role!r}")
