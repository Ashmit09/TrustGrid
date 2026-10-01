"""
TrustGrid — XGBoost Training Script (spec §9, §24-O)

Target: label = 1 (reliable future behavior), 0 = unreliable
Split:  70% train / 15% val / 15% test  — CHRONOLOGICAL (no leakage)
        (rows are sorted by meaningful_event_count as a proxy for time)

Outputs to TrustGrid/ml/models/:
    buyer_xgb_model.json
    seller_xgb_model.json
    buyer_feature_cols.json
    seller_feature_cols.json
    buyer_eval_report.txt
    seller_eval_report.txt

Usage:
    cd TrustGrid && source .venv/bin/activate
    PYTHONPATH=backend python ml/training/train.py
"""
import sys, os, json
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, classification_report,
)
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset")
MODEL_DIR   = os.path.join(os.path.dirname(__file__), "..", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# Features used for ML (spec §9 recommended features)
BUYER_FEATURE_COLS = [
    "decayed_completion_rate",
    "decayed_problematic_return_rate",
    "decayed_payment_success_rate",
    "decayed_cancellation_rate",
    "engagement_quality",
    "total_orders",
    "cancelled_orders",
    "total_payments",
    "failed_payments",
    "total_returns",
    "problematic_returns",
    "meaningful_event_count",
    "recent_orders_30d",
    "recent_cancels_30d",
    "account_age_days",
]

SELLER_FEATURE_COLS = [
    "decayed_fulfillment_rate",
    "decayed_late_delivery_rate",
    "avg_rating_decayed",
    "decayed_resolution_rate",
    "platform_reliability",
    "total_fulfilled",
    "total_cancelled_seller",
    "total_delivered",
    "total_late",
    "total_reviews_received",
    "total_returns_received",
    "total_resolved",
    "total_products_listed",
    "meaningful_event_count",
    "recent_deliveries_30d",
    "recent_late_30d",
    "account_age_days",
]


def chronological_split(df: pd.DataFrame, target: str, feature_cols: list):
    """
    Sort by meaningful_event_count (proxy for accumulated history) and split
    70/15/15 chronologically to prevent future-data leakage.
    """
    df_sorted = df.sort_values("meaningful_event_count").reset_index(drop=True)
    n = len(df_sorted)
    train_end = int(n * 0.70)
    val_end   = int(n * 0.85)

    X = df_sorted[feature_cols].values
    y = df_sorted[target].values

    X_train, y_train = X[:train_end], y[:train_end]
    X_val,   y_val   = X[train_end:val_end], y[train_end:val_end]
    X_test,  y_test  = X[val_end:], y[val_end:]
    return X_train, y_train, X_val, y_val, X_test, y_test


def evaluate(model, X, y, label="Test") -> str:
    preds = model.predict(X)
    proba = model.predict_proba(X)[:, 1]
    p = precision_score(y, preds, zero_division=0)
    r = recall_score(y, preds, zero_division=0)
    f = f1_score(y, preds, zero_division=0)
    auc = roc_auc_score(y, proba) if len(np.unique(y)) > 1 else float("nan")
    cm = confusion_matrix(y, preds)
    report = (
        f"\n{'='*50}\n{label}\n{'='*50}\n"
        f"  Precision : {p:.4f}\n"
        f"  Recall    : {r:.4f}\n"
        f"  F1        : {f:.4f}\n"
        f"  ROC-AUC   : {auc:.4f}\n"
        f"  Confusion :\n{cm}\n"
        f"\n{classification_report(y, preds, zero_division=0)}"
    )
    return report


def train_role(role: str):
    csv_path = os.path.join(DATASET_DIR, f"{role}_features.csv")
    df = pd.read_csv(csv_path)
    feature_cols = BUYER_FEATURE_COLS if role == "buyer" else SELLER_FEATURE_COLS

    # Validate no NaN in features
    df[feature_cols] = df[feature_cols].fillna(0.0)

    X_train, y_train, X_val, y_val, X_test, y_test = chronological_split(
        df, "label", feature_cols
    )
    print(f"\n[{role.upper()}] split: train={len(y_train)} val={len(y_val)} test={len(y_test)}")

    # ── XGBoost ────────────────────────────────────────────────────────────
    xgb_model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    xgb_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # ── Logistic Regression baseline ────────────────────────────────────────
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s   = scaler.transform(X_val)
    X_test_s  = scaler.transform(X_test)

    lr_model = LogisticRegression(max_iter=1000, random_state=42)
    lr_model.fit(X_train_s, y_train)

    # ── Evaluation report ──────────────────────────────────────────────────
    report_lines = [f"TrustGrid ML Evaluation — {role.upper()}\n"]
    report_lines.append(evaluate(xgb_model, X_test, y_test, label="XGBoost — Test Set"))
    report_lines.append(evaluate(lr_model,  X_test_s, y_test, label="Logistic Regression Baseline — Test Set"))

    # Feature importance
    importance = dict(zip(feature_cols, xgb_model.feature_importances_))
    top = sorted(importance.items(), key=lambda x: -x[1])[:10]
    report_lines.append("\nTop 10 XGBoost Feature Importances:\n")
    for feat, imp in top:
        report_lines.append(f"  {feat:45s}: {imp:.4f}")

    report_text = "\n".join(report_lines)
    print(report_text)

    # ── Save artifacts ─────────────────────────────────────────────────────
    model_path = os.path.join(MODEL_DIR, f"{role}_xgb_model.json")
    xgb_model.save_model(model_path)
    print(f"\nModel saved to {model_path}")

    col_path = os.path.join(MODEL_DIR, f"{role}_feature_cols.json")
    with open(col_path, "w") as f:
        json.dump(feature_cols, f)
    print(f"Feature columns saved to {col_path}")

    report_path = os.path.join(MODEL_DIR, f"{role}_eval_report.txt")
    with open(report_path, "w") as f:
        f.write(report_text)
    print(f"Evaluation report saved to {report_path}")

    return xgb_model, feature_cols


if __name__ == "__main__":
    print("Training buyer model …")
    buyer_model, buyer_cols = train_role("buyer")
    print("\nTraining seller model …")
    seller_model, seller_cols = train_role("seller")
    print("\n✓ Training complete.")
