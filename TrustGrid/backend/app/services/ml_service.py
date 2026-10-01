"""
TrustGrid — ML Service (spec §9, §14)

Loads the trained XGBoost models and provides a single predict() function.
The function returns P(reliable future behavior) in [0, 1].

The ML service NEVER returns the final 0–1000 Trust Score directly.
It provides only a probability that is blended by the Trust Engine.
"""
import json
import os
from typing import Dict, Optional

import numpy as np
import xgboost as xgb

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "models")

# Lazy-loaded model cache
_models: Dict[str, xgb.XGBClassifier] = {}
_feature_cols: Dict[str, list] = {}


def _load(role: str) -> Optional[xgb.XGBClassifier]:
    """Load (or return cached) XGBoost model for the given role."""
    global _models, _feature_cols
    if role in _models:
        return _models[role]

    model_path = os.path.join(_MODEL_DIR, f"{role}_xgb_model.json")
    cols_path  = os.path.join(_MODEL_DIR, f"{role}_feature_cols.json")

    if not os.path.exists(model_path) or not os.path.exists(cols_path):
        return None

    try:
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        with open(cols_path) as f:
            cols = json.load(f)
        _models[role]       = model
        _feature_cols[role] = cols
        return model
    except Exception:
        return None


def predict(features: Dict, role: str) -> Optional[float]:
    """
    Predict P(reliable future behavior) for the given feature dict.

    Returns
    -------
    float in [0.0, 1.0]  — probability of reliable behavior
    None                  — if model is unavailable or prediction fails
    """
    model = _load(role)
    if model is None:
        return None

    cols = _feature_cols.get(role, [])
    if not cols:
        return None

    # Build feature vector; fill missing keys with 0 (safe default)
    row = np.array([[features.get(c, 0.0) for c in cols]], dtype=np.float32)

    # Guard: reject NaN (spec §24-O)
    if np.isnan(row).any():
        row = np.nan_to_num(row, nan=0.0)

    try:
        prob = float(model.predict_proba(row)[0, 1])
        # Clamp to [0, 1]
        return max(0.0, min(1.0, prob))
    except Exception:
        return None


def is_model_available(role: str) -> bool:
    """Return True if the model file exists and loads successfully."""
    return _load(role) is not None
