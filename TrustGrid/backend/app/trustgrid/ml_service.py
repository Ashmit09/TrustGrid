"""
TrustGrid ML Inference Service.

Loads the pre-trained XGBoost models once at startup and provides
a clean interface for the trust engine to get ML-based reliability scores.

Design
------
• Models are trained offline (ml/run_pipeline.py) and saved as .joblib files.
• This service loads them at startup — never retrained after individual events.
• The model outputs a probability P(reliable=1) ∈ [0, 1].
• The trust engine maps this probability to a dimension reliability score.

The ML model output is used as a MODIFIER to the rule-based dimension scores,
not as a complete replacement.  This hybrid approach gives us:
  - The interpretability of rule-based dimension scoring
  - The non-linear pattern recognition of XGBoost

Fallback
--------
If the model file is not found (e.g., first run before training),
the service returns None and the trust engine uses the rule-based scores only.
"""
import logging
from pathlib import Path
from typing import Optional, Dict

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Model paths ───────────────────────────────────────────────────────────────

_ML_DIR        = Path(__file__).resolve().parents[3] / "ml" / "models"
_BUYER_MODEL_PATH  = _ML_DIR / "buyer_model.joblib"
_SELLER_MODEL_PATH = _ML_DIR / "seller_model.joblib"

# ── Feature column order must match training exactly ─────────────────────────

BUYER_FEATURE_COLS = [
    "order_completion_rate",
    "return_rate",
    "payment_success_rate",
    "cancellation_rate",
    "referral_count",
    "review_count",
    "total_orders",
    "completed_orders",
    "total_cancellations",
    "total_returns",
    "decayed_event_weight",
]

SELLER_FEATURE_COLS = [
    "fulfillment_rate",
    "late_delivery_rate",
    "avg_rating_received",
    "return_response_rate",
    "products_listed",
    "fulfilled_orders",
    "seller_cancellations",
    "on_time_deliveries",
    "late_deliveries",
    "return_requests_received",
    "returns_responded",
    "decayed_event_weight",
]


# ── Lazy-loaded model singletons ─────────────────────────────────────────────

_buyer_model  = None
_seller_model = None
_models_loaded = False


def _load_models() -> None:
    """Load models from disk once. Silently skips if files don't exist."""
    global _buyer_model, _seller_model, _models_loaded
    if _models_loaded:
        return

    if _BUYER_MODEL_PATH.exists():
        try:
            _buyer_model = joblib.load(_BUYER_MODEL_PATH)
            logger.info(f"Buyer ML model loaded from {_BUYER_MODEL_PATH}")
        except Exception as e:
            logger.warning(f"Failed to load buyer model: {e}")

    if _SELLER_MODEL_PATH.exists():
        try:
            _seller_model = joblib.load(_SELLER_MODEL_PATH)
            logger.info(f"Seller ML model loaded from {_SELLER_MODEL_PATH}")
        except Exception as e:
            logger.warning(f"Failed to load seller model: {e}")

    _models_loaded = True


def get_buyer_reliability_score(features: dict) -> Optional[float]:
    """
    Run the buyer XGBoost model on the feature vector.

    Returns
    -------
    float ∈ [0, 1] : P(reliable=1) — higher means more reliable behaviour.
    None           : if model is not available.
    """
    _load_models()
    if _buyer_model is None:
        return None

    try:
        # Build feature vector in the exact column order used during training
        row = {col: features.get(col, _buyer_defaults().get(col, 0.0))
               for col in BUYER_FEATURE_COLS}
        X = pd.DataFrame([row])
        prob = float(_buyer_model.predict_proba(X)[0, 1])
        return max(0.0, min(1.0, prob))
    except Exception as e:
        logger.warning(f"Buyer ML inference failed: {e}")
        return None


def get_seller_reliability_score(features: dict) -> Optional[float]:
    """
    Run the seller XGBoost model on the feature vector.

    Returns
    -------
    float ∈ [0, 1] : P(reliable=1) — higher means more reliable behaviour.
    None           : if model is not available.
    """
    _load_models()
    if _seller_model is None:
        return None

    try:
        defaults = _seller_defaults()
        row = {col: features.get(col, defaults.get(col, 0.0))
               for col in SELLER_FEATURE_COLS}
        # avg_rating_received == 0.0 means "no ratings yet", not "bad rating".
        # Pass 3.5 (mid-scale neutral) so the model is not misled.
        if row["avg_rating_received"] == 0.0:
            row["avg_rating_received"] = 3.5
        X = pd.DataFrame([row])
        prob = float(_seller_model.predict_proba(X)[0, 1])
        return max(0.0, min(1.0, prob))
    except Exception as e:
        logger.warning(f"Seller ML inference failed: {e}")
        return None


def models_available() -> dict:
    """Return which models are loaded (useful for /health checks)."""
    _load_models()
    return {
        "buyer_model":  _buyer_model  is not None,
        "seller_model": _seller_model is not None,
    }


# ── Neutral defaults for missing feature keys ─────────────────────────────────

def _buyer_defaults() -> dict:
    return {
        "order_completion_rate": 1.0,
        "return_rate":           0.0,
        "payment_success_rate":  1.0,
        "cancellation_rate":     0.0,
        "referral_count":        0.0,
        "review_count":          0.0,
        "total_orders":          0.0,
        "completed_orders":      0.0,
        "total_cancellations":   0.0,
        "total_returns":         0.0,
        "decayed_event_weight":  0.0,
    }


def _seller_defaults() -> dict:
    return {
        "fulfillment_rate":          1.0,
        "late_delivery_rate":        0.0,
        "avg_rating_received":       0.0,
        "return_response_rate":      1.0,
        "products_listed":           0.0,
        "fulfilled_orders":          0.0,
        "seller_cancellations":      0.0,
        "on_time_deliveries":        0.0,
        "late_deliveries":           0.0,
        "return_requests_received":  0.0,
        "returns_responded":         0.0,
        "decayed_event_weight":      0.0,
    }
