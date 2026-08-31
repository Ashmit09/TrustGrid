"""
Shared evaluation utilities for TrustGrid XGBoost models.

Metrics reported
----------------
  Accuracy   — overall correctness (secondary, may be misleading on imbalance)
  Precision  — of predicted positives, how many were actually positive
  Recall     — of actual positives, how many were predicted positive
  F1         — harmonic mean of precision and recall (primary metric)
  ROC-AUC    — area under the ROC curve (primary metric for ranking quality)
  Confusion matrix

Note on metric priority
-----------------------
  For behavioural reliability prediction, Precision, Recall, F1, and ROC-AUC
  are more informative than raw Accuracy, especially if class imbalance exists.
  We report all five but emphasise F1 and ROC-AUC.
"""
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)


def evaluate_model(
    model,
    X_test:     pd.DataFrame,
    y_test:     pd.Series,
    model_name: str = "Model",
    threshold:  float = 0.5,
) -> dict:
    """
    Evaluate a trained classifier on the test set.

    Parameters
    ----------
    model      : trained sklearn-compatible classifier (must have predict_proba)
    X_test     : test feature matrix
    y_test     : true binary labels
    model_name : label for printout
    threshold  : decision threshold for converting probabilities to labels

    Returns
    -------
    metrics dict with keys: accuracy, precision, recall, f1, roc_auc
    """
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred       = (y_pred_proba >= threshold).astype(int)

    acc       = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall    = recall_score(y_test, y_pred, zero_division=0)
    f1        = f1_score(y_test, y_pred, zero_division=0)
    roc_auc   = roc_auc_score(y_test, y_pred_proba)
    cm        = confusion_matrix(y_test, y_pred)

    print(f"\n{'=' * 60}")
    print(f"  {model_name} — Evaluation Results (threshold={threshold})")
    print(f"{'=' * 60}")
    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {precision:.4f}  ← of predicted reliable, % actually reliable")
    print(f"  Recall    : {recall:.4f}  ← of actually reliable, % correctly identified")
    print(f"  F1 Score  : {f1:.4f}  ← primary metric")
    print(f"  ROC-AUC   : {roc_auc:.4f}  ← primary metric (ranking quality)")
    print(f"\n  Confusion Matrix:")
    print(f"              Predicted 0  Predicted 1")
    print(f"  Actual 0:     {cm[0][0]:>8d}    {cm[0][1]:>8d}")
    print(f"  Actual 1:     {cm[1][0]:>8d}    {cm[1][1]:>8d}")

    print(f"\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["unreliable", "reliable"]))

    return {
        "accuracy":  acc,
        "precision": precision,
        "recall":    recall,
        "f1":        f1,
        "roc_auc":   roc_auc,
    }


def print_feature_importance(model, feature_names: list, top_n: int = 15) -> None:
    """
    Print the top-N most important features by XGBoost's gain-based importance.
    """
    importances = model.feature_importances_
    fi_df = pd.DataFrame({
        "feature":    feature_names,
        "importance": importances,
    }).sort_values("importance", ascending=False).head(top_n)

    print(f"\n  Top {top_n} Feature Importances (by gain):")
    print(f"  {'Feature':<35} {'Importance':>10}")
    print(f"  {'-'*35} {'-'*10}")
    for _, row in fi_df.iterrows():
        print(f"  {row['feature']:<35} {row['importance']:>10.4f}")
