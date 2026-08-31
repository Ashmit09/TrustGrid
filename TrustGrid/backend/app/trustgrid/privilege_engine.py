"""
TrustGrid Privilege Engine.

Determines which benefits a user has access to based on:
  - Trust Score
  - Confidence level
  - Trust Tier

Design principles
-----------------
• A new user starts at 700 / LOW confidence / TRUSTED tier.
  They receive BASIC benefits only — not full Trusted/Elite benefits —
  because there is no behavioral evidence yet.

• Privilege eligibility requires BOTH a sufficient score AND
  sufficient confidence.  This prevents brand-new accounts from
  getting maximum privileges immediately.

• All privilege logic lives here.  Frontend/API layers should never
  hard-code benefit rules.

BUYER BENEFITS
--------------
COD_AVAILABLE        : Score ≥ 600 AND confidence ≥ MEDIUM
                       OR Score ≥ 750 (any confidence)
EXCLUSIVE_VOUCHER    : Score ≥ 650 AND confidence ≥ MEDIUM
FREE_DELIVERY        : Score ≥ 700 AND confidence ≥ MEDIUM
PRIORITY_SUPPORT     : Score ≥ 800 AND confidence ≥ HIGH

SELLER BENEFITS
---------------
SEARCH_VISIBILITY    : Score ≥ 600 AND confidence ≥ MEDIUM
TRUSTED_BADGE        : Score ≥ 700 AND confidence ≥ MEDIUM
REDUCED_PLATFORM_FEE : Score ≥ 750 AND confidence ≥ HIGH
PROMOTIONAL_CREDITS  : Score ≥ 800 AND confidence ≥ HIGH
"""
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.models.trust import TrustScore, Privilege, ConfidenceLevel, TrustTier
from app.models.user import UserRole


# ── Privilege definitions ─────────────────────────────────────────────────────

_BUYER_PRIVILEGES: List[Dict[str, Any]] = [
    {
        "name":       "COD_AVAILABLE",
        "label":      "Cash on Delivery",
        "description":"Pay on delivery for your orders.",
        "min_score":  600,
        "min_conf":   ConfidenceLevel.MEDIUM,
        "alt_score":  750,   # unlocked at this score regardless of confidence
        "alt_conf":   None,
    },
    {
        "name":       "EXCLUSIVE_VOUCHER",
        "label":      "₹150 Exclusive Voucher",
        "description":"₹150 discount voucher on your next order.",
        "min_score":  650,
        "min_conf":   ConfidenceLevel.MEDIUM,
        "alt_score":  None,
        "alt_conf":   None,
    },
    {
        "name":       "FREE_DELIVERY",
        "label":      "Free Delivery",
        "description":"Free delivery on all orders.",
        "min_score":  700,
        "min_conf":   ConfidenceLevel.MEDIUM,
        "alt_score":  None,
        "alt_conf":   None,
    },
    {
        "name":       "PRIORITY_SUPPORT",
        "label":      "Priority Support",
        "description":"Skip the queue — get priority customer support.",
        "min_score":  800,
        "min_conf":   ConfidenceLevel.HIGH,
        "alt_score":  None,
        "alt_conf":   None,
    },
]

_SELLER_PRIVILEGES: List[Dict[str, Any]] = [
    {
        "name":       "SEARCH_VISIBILITY",
        "label":      "Search Visibility Boost",
        "description":"Your products appear higher in search results.",
        "min_score":  600,
        "min_conf":   ConfidenceLevel.MEDIUM,
        "alt_score":  None,
        "alt_conf":   None,
    },
    {
        "name":       "TRUSTED_BADGE",
        "label":      "Trusted Seller Badge",
        "description":"A Trusted Seller badge displayed on your storefront.",
        "min_score":  700,
        "min_conf":   ConfidenceLevel.MEDIUM,
        "alt_score":  None,
        "alt_conf":   None,
    },
    {
        "name":       "REDUCED_PLATFORM_FEE",
        "label":      "1% Lower Platform Fee",
        "description":"Reduced platform commission on your sales.",
        "min_score":  750,
        "min_conf":   ConfidenceLevel.HIGH,
        "alt_score":  None,
        "alt_conf":   None,
    },
    {
        "name":       "PROMOTIONAL_CREDITS",
        "label":      "₹500 Promotional Credits",
        "description":"₹500 in promotional credits for boosting your listings.",
        "min_score":  800,
        "min_conf":   ConfidenceLevel.HIGH,
        "alt_score":  None,
        "alt_conf":   None,
    },
]

_CONF_RANK: Dict[str, int] = {
    ConfidenceLevel.LOW:    0,
    ConfidenceLevel.MEDIUM: 1,
    ConfidenceLevel.HIGH:   2,
}


# ── Public API ────────────────────────────────────────────────────────────────

def recalculate_privileges(
    db: Session,
    user_id: str,
    role: UserRole,
    trust_score: int,
    confidence: ConfidenceLevel,
) -> List[Privilege]:
    """
    Recompute and persist all privilege rows for the user.

    Returns the full list of Privilege rows (active + inactive).
    """
    definitions = _BUYER_PRIVILEGES if role == UserRole.buyer else _SELLER_PRIVILEGES
    conf_rank   = _CONF_RANK[confidence]

    results: List[Privilege] = []

    for defn in definitions:
        is_active, reason = _evaluate(defn, trust_score, conf_rank)

        # Upsert privilege row
        row = (
            db.query(Privilege)
            .filter(Privilege.user_id == user_id, Privilege.privilege_name == defn["name"])
            .first()
        )
        if row is None:
            row = Privilege(user_id=user_id, privilege_name=defn["name"])
            db.add(row)

        row.status = "active" if is_active else "inactive"
        row.reason = reason
        results.append(row)

    db.commit()
    for r in results:
        db.refresh(r)

    return results


def get_active_privilege_names(
    db: Session,
    user_id: str,
) -> List[str]:
    """Return a list of privilege name strings that are currently active."""
    return [
        p.privilege_name
        for p in db.query(Privilege)
        .filter(Privilege.user_id == user_id, Privilege.status == "active")
        .all()
    ]


def get_all_privilege_details(role: UserRole) -> List[Dict[str, Any]]:
    """Return the full privilege definition list for a role (for UI rendering)."""
    return _BUYER_PRIVILEGES if role == UserRole.buyer else _SELLER_PRIVILEGES


# ── Helpers ───────────────────────────────────────────────────────────────────

def _evaluate(
    defn: Dict[str, Any],
    score: int,
    conf_rank: int,
) -> tuple:
    """
    Return (is_active: bool, reason: str) for a single privilege definition.
    """
    min_conf_rank = _CONF_RANK.get(defn["min_conf"], 0)

    # Primary path
    if score >= defn["min_score"] and conf_rank >= min_conf_rank:
        return True, "Unlocked based on Trust Score and confidence level."

    # Alternate path (score-only unlock, if defined)
    if defn.get("alt_score") and score >= defn["alt_score"]:
        return True, "Unlocked based on high Trust Score."

    # Not unlocked — give an informative reason
    if score < defn["min_score"]:
        needed = defn["min_score"] - score
        return False, f"Requires Trust Score ≥ {defn['min_score']} (need +{needed} more)."

    return False, f"Requires {defn['min_conf']} confidence level."
