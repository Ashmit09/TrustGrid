"""
TrustGrid — Explanation Service (spec §28 STEP 15)

Generates a human-readable explanation for a trust score change.
Identifies the weakest dimension and the main contributing factors.
"""
from typing import Dict, List, Optional


def generate_explanation(
    *,
    role: str,
    dimensions: Dict[str, float],
    rule_score: float,
    ml_score: Optional[float],
    combined_score: float,
    confidence: str,
    old_score: int,
    new_score: int,
) -> Dict:
    """
    Build a structured explanation dict.

    Returns
    -------
    {
        "summary": str,                  # short one-liner
        "positive_factors": [str, ...],  # dimension names that scored well
        "negative_factors": [str, ...],  # dimension names that scored poorly
        "weakest_dimension": str,        # lowest-scoring dimension
        "improvement_tip":  str,         # how to improve the weakest dimension
        "score_change": int,
        "confidence_note": str,
    }
    """
    change = new_score - old_score
    direction = "increased" if change > 0 else ("decreased" if change < 0 else "unchanged")

    sorted_dims = sorted(dimensions.items(), key=lambda x: x[1])
    weakest_name, weakest_val = sorted_dims[0]
    strongest_name, strongest_val = sorted_dims[-1]

    positive_factors = [k for k, v in dimensions.items() if v >= 70.0]
    negative_factors = [k for k, v in dimensions.items() if v < 50.0]

    improvement_tips = {
        # Buyer
        "order_reliability":      "Complete more orders without cancellations.",
        "return_behaviour":       "Avoid problematic or repeated returns.",
        "payment_reliability":    "Ensure payments succeed on the first attempt.",
        "cancellation_behaviour": "Reduce order cancellations.",
        "platform_engagement":    "Submit helpful reviews or refer new users.",
        # Seller
        "order_fulfillment":       "Fulfill orders promptly and avoid cancellations.",
        "delivery_performance":    "Ship orders on time to improve delivery score.",
        "customer_satisfaction":   "Aim for higher customer ratings.",
        "return_dispute_handling": "Resolve return requests quickly and fairly.",
        "platform_reliability":    "List more products and maintain policy compliance.",
    }
    tip = improvement_tips.get(weakest_name, "Keep improving your marketplace behavior.")

    confidence_note = {
        "LOW":    "Score has LOW confidence — more activity is needed for a reliable assessment.",
        "MEDIUM": "Score has MEDIUM confidence based on growing evidence.",
        "HIGH":   "Score has HIGH confidence based on substantial evidence history.",
    }.get(confidence, "")

    summary = (
        f"Trust score {direction} by {abs(change)} points "
        f"(from {old_score} to {new_score}). "
        f"Weakest area: {weakest_name.replace('_', ' ')} ({weakest_val:.0f}/100)."
    )

    return {
        "summary":           summary,
        "positive_factors":  positive_factors,
        "negative_factors":  negative_factors,
        "weakest_dimension": weakest_name,
        "improvement_tip":   tip,
        "score_change":      change,
        "confidence_note":   confidence_note,
    }
