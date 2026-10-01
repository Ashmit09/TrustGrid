"""
TrustGrid — Confidence Service (spec §11)

Confidence describes how much evidence exists, NOT whether the user is good.

Thresholds (frozen):
    0–5  events → LOW
    6–30 events → MEDIUM
    31+  events → HIGH
"""
from app.core.constants import LOW_MAX_EVENTS, MEDIUM_MAX_EVENTS


def get_confidence(meaningful_event_count: int) -> str:
    """
    Map a meaningful event count to a confidence level.

    Parameters
    ----------
    meaningful_event_count : total number of evidence-producing events
                             (orders, payments, returns, reviews, referrals)

    Returns
    -------
    'LOW' | 'MEDIUM' | 'HIGH'
    """
    if meaningful_event_count <= LOW_MAX_EVENTS:
        return "LOW"
    elif meaningful_event_count <= MEDIUM_MAX_EVENTS:
        return "MEDIUM"
    else:
        return "HIGH"
