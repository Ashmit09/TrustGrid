"""
Train / Validation / Test split for TrustGrid ML pipeline.

Split strategy: chronological by decayed_event_weight (proxy for recency).
Users with more recent activity are placed in the validation and test sets.
This mirrors the real-world scenario of training on historical behaviour
and predicting future reliability.

Split ratios
------------
  Train      : 70%
  Validation : 15%
  Test       : 15%

Anti-leakage note
-----------------
The feature vectors are computed ONLY from event data available BEFORE
the prediction horizon. The label is a profile-level ground truth that
is NOT derived from the feature values (no target leakage).
"""
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


# ── Buyer feature columns used by the model ──────────────────────────────────

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

# ── Seller feature columns used by the model ─────────────────────────────────

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

LABEL_COL = "label"


def load_and_split_buyers(
    features_csv: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
           pd.Series,    pd.Series,    pd.Series]:
    """
    Load buyer features CSV and return chronological train/val/test splits.

    Returns
    -------
    X_train, X_val, X_test, y_train, y_val, y_test
    """
    df = pd.read_csv(features_csv)
    return _split(df, BUYER_FEATURE_COLS)


def load_and_split_sellers(
    features_csv: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
           pd.Series,    pd.Series,    pd.Series]:
    """
    Load seller features CSV and return chronological train/val/test splits.
    """
    df = pd.read_csv(features_csv)
    return _split(df, SELLER_FEATURE_COLS)


def _split(
    df: pd.DataFrame,
    feature_cols: list,
    val_size: float = 0.15,
    test_size: float = 0.15,
    random_state: int = 42,
) -> Tuple:
    """
    Chronological split:
      - Sort by decayed_event_weight ascending (lower weight = older activity).
      - First 70% → train, next 15% → val, final 15% → test.

    This ensures the model is evaluated on users with more recent activity.
    """
    # Sort so that users with heavier recent evidence are at the end
    df_sorted = df.sort_values("decayed_event_weight", ascending=True).reset_index(drop=True)

    n           = len(df_sorted)
    n_test      = max(1, int(n * test_size))
    n_val       = max(1, int(n * val_size))
    n_train     = n - n_val - n_test

    train_df = df_sorted.iloc[:n_train]
    val_df   = df_sorted.iloc[n_train:n_train + n_val]
    test_df  = df_sorted.iloc[n_train + n_val:]

    # Select only model-input columns
    available_cols = [c for c in feature_cols if c in df_sorted.columns]

    X_train = train_df[available_cols].copy()
    X_val   = val_df  [available_cols].copy()
    X_test  = test_df [available_cols].copy()

    y_train = train_df[LABEL_COL].copy()
    y_val   = val_df  [LABEL_COL].copy()
    y_test  = test_df [LABEL_COL].copy()

    return X_train, X_val, X_test, y_train, y_val, y_test


def print_split_summary(
    X_train: pd.DataFrame,
    X_val:   pd.DataFrame,
    X_test:  pd.DataFrame,
    y_train: pd.Series,
    y_val:   pd.Series,
    y_test:  pd.Series,
    name:    str = "",
) -> None:
    """Print a brief summary of the split."""
    total = len(X_train) + len(X_val) + len(X_test)
    print(f"\n{name} Split Summary")
    print("-" * 40)
    print(f"  Total    : {total:,}")
    print(f"  Train    : {len(X_train):,}  ({100*len(X_train)/total:.1f}%)"
          f"  pos={y_train.sum():,}  neg={(~y_train.astype(bool)).sum():,}")
    print(f"  Val      : {len(X_val):,}   ({100*len(X_val)/total:.1f}%)"
          f"  pos={y_val.sum():,}    neg={(~y_val.astype(bool)).sum():,}")
    print(f"  Test     : {len(X_test):,}   ({100*len(X_test)/total:.1f}%)"
          f"  pos={y_test.sum():,}   neg={(~y_test.astype(bool)).sum():,}")
    print(f"  Features : {X_train.shape[1]}")
