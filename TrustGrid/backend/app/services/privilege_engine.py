"""
TrustGrid — Privilege Engine (spec §14)

Privileges = f(TrustScore, Confidence, Tier)

Buyer privileges per tier:
    RESTRICTED  : standard_delivery, basic_support      (COD may be restricted)
    STANDARD    : cod, standard_delivery, basic_support
    TRUSTED     : cod, voucher_100, free_delivery, priority_support
    ELITE       : cod, voucher_150, free_delivery, priority_support

Seller privileges per tier:
    RESTRICTED  : basic_seller_account, limited_visibility, standard_platform_fee
    STANDARD    : standard_visibility, basic_seller_support
    TRUSTED     : trusted_seller_badge, search_visibility_boost, priority_support
    ELITE       : trusted_seller_badge, strong_visibility_boost, lower_platform_fee,
                  promo_credit_500, priority_support

Confidence gate:
    ELITE + LOW confidence → limited Elite benefits (no voucher/credit).
"""
from typing import List


_BUYER_PRIVILEGES = {
    "RESTRICTED": ["STANDARD_DELIVERY", "BASIC_SUPPORT"],
    "STANDARD":   ["COD", "STANDARD_DELIVERY", "BASIC_SUPPORT"],
    "TRUSTED":    ["COD", "VOUCHER_100", "FREE_DELIVERY", "PRIORITY_SUPPORT"],
    "ELITE":      ["COD", "VOUCHER_150", "FREE_DELIVERY", "PRIORITY_SUPPORT"],
}

_SELLER_PRIVILEGES = {
    "RESTRICTED": ["BASIC_SELLER_ACCOUNT", "LIMITED_VISIBILITY", "STANDARD_PLATFORM_FEE"],
    "STANDARD":   ["STANDARD_VISIBILITY", "BASIC_SELLER_SUPPORT"],
    "TRUSTED":    ["TRUSTED_SELLER_BADGE", "SEARCH_VISIBILITY_BOOST", "PRIORITY_SUPPORT"],
    "ELITE":      ["TRUSTED_SELLER_BADGE", "STRONG_VISIBILITY_BOOST",
                   "LOWER_PLATFORM_FEE", "PROMO_CREDIT_500", "PRIORITY_SUPPORT"],
}

# Privileges removed from ELITE when confidence is LOW (insufficient evidence gate)
_ELITE_LOW_CONFIDENCE_EXCLUSIONS_BUYER  = {"VOUCHER_150"}
_ELITE_LOW_CONFIDENCE_EXCLUSIONS_SELLER = {"PROMO_CREDIT_500", "LOWER_PLATFORM_FEE"}


def get_privileges(trust_score: int, confidence: str, tier: str, role: str) -> List[str]:
    """
    Return the list of active privilege strings for a user.

    Parameters
    ----------
    trust_score : int 0–1000
    confidence  : 'LOW' | 'MEDIUM' | 'HIGH'
    tier        : 'RESTRICTED' | 'STANDARD' | 'TRUSTED' | 'ELITE'
    role        : 'buyer' | 'seller'

    Returns
    -------
    List of uppercase privilege name strings.
    """
    table = _BUYER_PRIVILEGES if role == "buyer" else _SELLER_PRIVILEGES
    base = list(table.get(tier, []))

    # Confidence gate for ELITE tier
    if tier == "ELITE" and confidence == "LOW":
        exclusions = (
            _ELITE_LOW_CONFIDENCE_EXCLUSIONS_BUYER
            if role == "buyer"
            else _ELITE_LOW_CONFIDENCE_EXCLUSIONS_SELLER
        )
        base = [p for p in base if p not in exclusions]

    return base
