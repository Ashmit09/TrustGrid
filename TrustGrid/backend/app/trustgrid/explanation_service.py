"""
TrustGrid Explanation Service.

Translates raw event types and feature changes into plain-English
explanations that are shown in the UI.

Design principle: users should NEVER see ML jargon or internal field names.
They should see friendly, actionable statements like:
  "Your recent order completions are contributing positively to your score."
  "Your recent cancellations are affecting your Trust Score."

The service is deliberately rule-based (not ML) for explainability.
"""
from typing import List, Optional, Dict

from app.trustgrid.event_types import EventType


# ── Event → human label ───────────────────────────────────────────────────────

_EVENT_LABELS: Dict[str, str] = {
    EventType.ORDER_COMPLETED.value:         "Successful order completion",
    EventType.ORDER_CANCELLED.value:         "Order cancellation",
    EventType.PAYMENT_SUCCESS.value:         "Successful payment",
    EventType.PAYMENT_FAILED.value:          "Failed payment",
    EventType.RETURN_REQUESTED.value:        "Return request",
    EventType.RETURN_COMPLETED.value:        "Return resolved",
    EventType.REVIEW_SUBMITTED.value:        "Review submitted",
    EventType.REFERRAL_COMPLETED.value:      "Successful referral",
    EventType.ORDER_FULFILLED.value:         "Order shipped on time",
    EventType.ORDER_DELIVERED.value:         "Order delivered",
    EventType.ORDER_LATE.value:              "Late delivery",
    EventType.SELLER_CANCELLED.value:        "Seller-initiated cancellation",
    EventType.RETURN_REQUEST_RECEIVED.value: "Return request received",
    EventType.RETURN_RESOLVED.value:         "Return resolved for customer",
    EventType.RETURN_REJECTED.value:         "Return request rejected",
    EventType.REVIEW_RECEIVED.value:         "Customer review received",
    EventType.PRODUCT_LISTED.value:          "New product listed",
    EventType.REFERRAL_MADE.value:           "Referral sent",
    EventType.ORDER_PLACED.value:            "Order placed",
}


def label_for_event(event_type: str) -> str:
    """Return a plain-English label for an event type."""
    return _EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())


# ── Recommendation rules ──────────────────────────────────────────────────────

def get_buyer_recommendations(dim_scores: Dict[str, float]) -> List[str]:
    """
    Return a short list of improvement tips based on the weakest buyer dimension.
    Never uses harsh language — always framed as positive actions.
    """
    tips: List[str] = []

    order_rel = dim_scores.get("order_reliability",      100.0)
    return_beh = dim_scores.get("return_behaviour",       100.0)
    payment_rel = dim_scores.get("payment_reliability",   100.0)
    cancel_beh = dim_scores.get("cancellation_behaviour", 100.0)
    engagement = dim_scores.get("platform_engagement",    100.0)

    if payment_rel < 70:
        tips.append("Ensure your payment method is up to date before placing orders.")
    if cancel_beh < 70:
        tips.append("Reducing unnecessary cancellations will strengthen your Trust Score.")
    if order_rel < 70:
        tips.append("Completing orders consistently builds a stronger Trust Score.")
    if return_beh < 70:
        tips.append("A high return rate can lower your score — only return when necessary.")
    if engagement < 70:
        tips.append("Leaving honest reviews and referring friends can improve your engagement score.")

    if not tips:
        tips.append("Keep up your excellent behaviour to maintain your Trust Score!")

    return tips[:3]   # limit to top 3


def get_seller_recommendations(dim_scores: Dict[str, float]) -> List[str]:
    """
    Return improvement tips for sellers based on the weakest dimension.
    """
    tips: List[str] = []

    fulfillment  = dim_scores.get("order_fulfillment",       100.0)
    delivery     = dim_scores.get("delivery_performance",    100.0)
    satisfaction = dim_scores.get("customer_satisfaction",   100.0)
    returns_hdl  = dim_scores.get("return_dispute_handling", 100.0)
    reliability  = dim_scores.get("platform_reliability",    100.0)

    if delivery < 70:
        tips.append("Improving on-time delivery is the fastest way to raise your score.")
    if fulfillment < 70:
        tips.append("Avoid cancelling buyer orders — fulfillment rate is a core score driver.")
    if satisfaction < 70:
        tips.append("Higher product ratings significantly improve your Trust Score.")
    if returns_hdl < 70:
        tips.append("Respond to return requests promptly to improve your dispute handling score.")
    if reliability < 70:
        tips.append("Keeping your product listings accurate and up to date helps platform reliability.")

    if not tips:
        tips.append("Excellent performance! Maintain consistency to stay in the Elite tier.")

    return tips[:3]


# ── Score-change natural language ─────────────────────────────────────────────

def describe_score_change(
    score_change: int,
    event_type: Optional[str],
    custom_reason: Optional[str] = None,
) -> str:
    """
    Produce a brief natural-language description of a score change event.
    """
    if custom_reason:
        return custom_reason

    if not event_type:
        return "Trust Score updated based on recent activity."

    label = label_for_event(event_type)
    direction = "positively" if score_change >= 0 else "negatively"
    return f"{label} has affected your Trust Score {direction}."
