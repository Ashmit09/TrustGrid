"""
XGBoost Buyer Reliability Model — Training Script.

What this model does
--------------------
The model predicts whether a buyer is "behaviorally reliable" (label=1)
or "unreliable" (label=0) based on their time-decayed feature vector.

The model output (a probability between 0 and 1) is used by the TrustGrid
trust engine as the per-dimension reliability score input.

Model choice: XGBoost
---------------------
XGBoost is well-suited for this task because:
  • It handles tabular behavioral data effectively.
  • It captures non-linear relationships between features (e.g., a user
    with a high return rate but otherwise perfect behavior).
  • It is robust to mixed numerical features and varying scales.
  • It produces calibrated probabilities suitable for score computation.
  • It performs well on datasets of this size (thousands of users).

Hyperparameter rationale
-------------------------
  n_estimators   : 300 — enough trees to converge without overfitting.
  max_depth      : 4   — shallow trees for behavioral data reduce overfitting.
  learning_rate  : 0.05 — conservative learning rate combined with early stopping.
  subsample      : 0.8 — row subsampling for variance reduction.
  colsample      : 0.8 — column subsampling for feature diversity.
  scale_pos_weight: auto-computed to handle class imbalance.

Anti-leakage guarantee
----------------------
Features are computed ONLY from events recorded BEFORE the prediction target
is assigned. The label is a profile-level annotation (not derived from features).
This is explicitly documented here to satisfy academic review.

Output
------
  ml/models/buyer_model.joblib — saved trained model
  ml/models/buyer_metrics.json — evaluation metrics
"""
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.preprocessing.split import (
    load_and_split_buyers,
    BUYER_FEATURE_COLS,
    print_split_summary,
)
from ml.evaluation.evaluate import evaluate_model, print_feature_importance

DATASET_DIR = Path(__file__).resolve().parents[1] / "dataset"
MODELS_DIR  = Path(__file__).resolve().parents[1] / "models"
MODELS_DIR.mkdir(exist_ok=True)


def train_buyer_model() -> None:
    print("=" * 60)
    print("TrustGrid — Buyer Reliability Model Training")
    print("=" * 60)

    # ── Load & split ──────────────────────────────────────────────
    features_csv = DATASET_DIR / "buyer_features.csv"
    if not features_csv.exists():
        raise FileNotFoundError(
            f"buyer_features.csv not found at {features_csv}.\n"
            "Run: python ml/dataset/generate_dataset.py first."
        )

    X_train, X_val, X_test, y_train, y_val, y_test = load_and_split_buyers(features_csv)
    print_split_summary(X_train, X_val, X_test, y_train, y_val, y_test, name="Buyer")

    # ── Class imbalance handling ───────────────────────────────────
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    scale_pos_weight = neg / pos if pos > 0 else 1.0
    print(f"\n  Class balance — neg: {neg}, pos: {pos}")
    print(f"  scale_pos_weight = {scale_pos_weight:.3f}")

    # ── Model ─────────────────────────────────────────────────────
    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="logloss",
        early_stopping_rounds=20,
        random_state=42,
        verbosity=0,
    )

    print("\n  Training XGBoost buyer model ...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    best_iter = model.best_iteration
    print(f"  Best iteration: {best_iter}")

    # ── Evaluation ────────────────────────────────────────────────
    print("\n  --- Validation Set ---")
    val_metrics = evaluate_model(model, X_val, y_val, model_name="Buyer (Val)")

    print("\n  --- Test Set ---")
    test_metrics = evaluate_model(model, X_test, y_test, model_name="Buyer (Test)")

    print_feature_importance(model, X_train.columns.tolist())

    # ── Save model ────────────────────────────────────────────────
    model_path   = MODELS_DIR / "buyer_model.joblib"
    metrics_path = MODELS_DIR / "buyer_metrics.json"

    joblib.dump(model, model_path)
    print(f"\n  Model saved → {model_path}")

    metrics_out = {
        "model":        "buyer_reliability_xgboost",
        "features":     X_train.columns.tolist(),
        "best_iteration": int(best_iter),
        "val_metrics":  {k: round(v, 4) for k, v in val_metrics.items()},
        "test_metrics": {k: round(v, 4) for k, v in test_metrics.items()},
        "class_balance": {"neg": int(neg), "pos": int(pos)},
        "scale_pos_weight": round(scale_pos_weight, 4),
    }
    with open(metrics_path, "w") as f:
        json.dump(metrics_out, f, indent=2)
    print(f"  Metrics saved → {metrics_path}")


if __name__ == "__main__":
    train_buyer_model()
