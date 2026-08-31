"""
XGBoost Seller Reliability Model — Training Script.

What this model does
--------------------
The model predicts whether a seller is "behaviorally reliable" (label=1)
or "unreliable" (label=0) based on their time-decayed feature vector.

The model output (a probability between 0 and 1) is used by the TrustGrid
trust engine as input for per-dimension reliability scores.

See train_buyer.py for model choice rationale and anti-leakage guarantees.

Output
------
  ml/models/seller_model.joblib — saved trained model
  ml/models/seller_metrics.json — evaluation metrics
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.preprocessing.split import (
    load_and_split_sellers,
    SELLER_FEATURE_COLS,
    print_split_summary,
)
from ml.evaluation.evaluate import evaluate_model, print_feature_importance

DATASET_DIR = Path(__file__).resolve().parents[1] / "dataset"
MODELS_DIR  = Path(__file__).resolve().parents[1] / "models"
MODELS_DIR.mkdir(exist_ok=True)


def train_seller_model() -> None:
    print("=" * 60)
    print("TrustGrid — Seller Reliability Model Training")
    print("=" * 60)

    # ── Load & split ──────────────────────────────────────────────
    features_csv = DATASET_DIR / "seller_features.csv"
    if not features_csv.exists():
        raise FileNotFoundError(
            f"seller_features.csv not found at {features_csv}.\n"
            "Run: python ml/dataset/generate_dataset.py first."
        )

    X_train, X_val, X_test, y_train, y_val, y_test = load_and_split_sellers(features_csv)
    print_split_summary(X_train, X_val, X_test, y_train, y_val, y_test, name="Seller")

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

    print("\n  Training XGBoost seller model ...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    best_iter = model.best_iteration
    print(f"  Best iteration: {best_iter}")

    # ── Evaluation ────────────────────────────────────────────────
    print("\n  --- Validation Set ---")
    val_metrics = evaluate_model(model, X_val, y_val, model_name="Seller (Val)")

    print("\n  --- Test Set ---")
    test_metrics = evaluate_model(model, X_test, y_test, model_name="Seller (Test)")

    print_feature_importance(model, X_train.columns.tolist())

    # ── Save model ────────────────────────────────────────────────
    model_path   = MODELS_DIR / "seller_model.joblib"
    metrics_path = MODELS_DIR / "seller_metrics.json"

    joblib.dump(model, model_path)
    print(f"\n  Model saved → {model_path}")

    metrics_out = {
        "model":        "seller_reliability_xgboost",
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
    train_seller_model()
