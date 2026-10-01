"""
TrustGrid — Tier Service (spec §13)

Score → Tier mapping (frozen):
    0–399   RESTRICTED
    400–599 STANDARD
    600–799 TRUSTED
    800–1000 ELITE
"""
from app.core.constants import TIER_BOUNDARIES


def get_tier(trust_score: int) -> str:
    """
    Map a 0–1000 TrustScore to a tier name.

    Parameters
    ----------
    trust_score : integer in [0, 1000]

    Returns
    -------
    'RESTRICTED' | 'STANDARD' | 'TRUSTED' | 'ELITE'
    """
    for tier_name, (low, high) in TIER_BOUNDARIES.items():
        if low <= trust_score <= high:
            return tier_name
    # Edge: clamp extremes (should not happen with correct inputs)
    return "RESTRICTED" if trust_score < 0 else "ELITE"
