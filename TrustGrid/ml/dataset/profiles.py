"""
Behavioral profile definitions for synthetic dataset generation.

Each profile is a dict of parameter distributions that control how that
user-type behaves across marketplace events.

Design principles
-----------------
• Profiles reflect realistic marketplace user archetypes.
• Parameters are RATES (0–1), not counts.
  Actual event counts are generated separately based on activity level.
• Recent events matter more (time decay) — the dataset generator
  back-dates older events to simulate real temporal spread.
• Infrequent buyers are not penalised — low activity with high reliability
  should still produce a good Trust Score.

Profile parameter keys
----------------------
  order_completion_prob  : P(placed order gets completed, not cancelled/abandoned)
  payment_success_prob   : P(payment succeeds)
  cancellation_rate      : fraction of placed orders that buyer cancels
  return_rate            : fraction of completed orders that get returned
  referral_prob          : P(makes at least one referral per 20-event window)
  review_prob            : P(leaves review after completing order)
  activity_level         : LOW / MEDIUM / HIGH — controls total event count
  label                  : 0 (unreliable) or 1 (reliable) — ML target
"""

# ── BUYER PROFILES ────────────────────────────────────────────────────────────

BUYER_PROFILES = [
    {
        "name": "reliable_buyer",
        "weight": 0.30,           # 30% of synthetic buyers
        "order_completion_prob": 0.95,
        "payment_success_prob":  0.97,
        "cancellation_rate":     0.05,
        "return_rate":           0.04,
        "referral_prob":         0.30,
        "review_prob":           0.60,
        "activity_level":        "MEDIUM",
        "label": 1,
    },
    {
        "name": "occasional_reliable_buyer",
        "weight": 0.20,
        "order_completion_prob": 0.93,
        "payment_success_prob":  0.95,
        "cancellation_rate":     0.07,
        "return_rate":           0.05,
        "referral_prob":         0.10,
        "review_prob":           0.30,
        "activity_level":        "LOW",   # buys infrequently — still reliable
        "label": 1,
    },
    {
        "name": "frequent_returner",
        "weight": 0.12,
        "order_completion_prob": 0.85,
        "payment_success_prob":  0.92,
        "cancellation_rate":     0.10,
        "return_rate":           0.40,    # high return rate
        "referral_prob":         0.05,
        "review_prob":           0.20,
        "activity_level":        "MEDIUM",
        "label": 0,
    },
    {
        "name": "frequent_canceller",
        "weight": 0.12,
        "order_completion_prob": 0.50,
        "payment_success_prob":  0.88,
        "cancellation_rate":     0.50,    # cancels half of orders
        "return_rate":           0.08,
        "referral_prob":         0.05,
        "review_prob":           0.10,
        "activity_level":        "MEDIUM",
        "label": 0,
    },
    {
        "name": "poor_payment_behaviour",
        "weight": 0.10,
        "order_completion_prob": 0.70,
        "payment_success_prob":  0.55,    # frequent payment failures
        "cancellation_rate":     0.20,
        "return_rate":           0.10,
        "referral_prob":         0.02,
        "review_prob":           0.10,
        "activity_level":        "MEDIUM",
        "label": 0,
    },
    {
        "name": "mixed_behaviour",
        "weight": 0.16,
        "order_completion_prob": 0.78,
        "payment_success_prob":  0.82,
        "cancellation_rate":     0.22,
        "return_rate":           0.18,
        "referral_prob":         0.15,
        "review_prob":           0.25,
        "activity_level":        "MEDIUM",
        "label": 0,                       # borderline — not reliably good
    },
]

# ── SELLER PROFILES ───────────────────────────────────────────────────────────

SELLER_PROFILES = [
    {
        "name": "excellent_seller",
        "weight": 0.20,
        "fulfillment_rate":         0.98,
        "on_time_delivery_prob":    0.96,
        "avg_rating":               4.8,
        "rating_std":               0.3,
        "seller_cancellation_rate": 0.02,
        "return_response_rate":     0.97,
        "products_listed_range":    (5, 20),
        "activity_level":           "HIGH",
        "label": 1,
    },
    {
        "name": "reliable_seller",
        "weight": 0.25,
        "fulfillment_rate":         0.93,
        "on_time_delivery_prob":    0.88,
        "avg_rating":               4.2,
        "rating_std":               0.5,
        "seller_cancellation_rate": 0.07,
        "return_response_rate":     0.90,
        "products_listed_range":    (3, 10),
        "activity_level":           "MEDIUM",
        "label": 1,
    },
    {
        "name": "slow_seller",
        "weight": 0.15,
        "fulfillment_rate":         0.82,
        "on_time_delivery_prob":    0.55,    # frequently late
        "avg_rating":               3.5,
        "rating_std":               0.8,
        "seller_cancellation_rate": 0.10,
        "return_response_rate":     0.75,
        "products_listed_range":    (2, 8),
        "activity_level":           "MEDIUM",
        "label": 0,
    },
    {
        "name": "high_cancellation_seller",
        "weight": 0.15,
        "fulfillment_rate":         0.60,
        "on_time_delivery_prob":    0.70,
        "avg_rating":               3.0,
        "rating_std":               1.0,
        "seller_cancellation_rate": 0.40,    # cancels many orders
        "return_response_rate":     0.65,
        "products_listed_range":    (2, 6),
        "activity_level":           "MEDIUM",
        "label": 0,
    },
    {
        "name": "poor_return_handling_seller",
        "weight": 0.10,
        "fulfillment_rate":         0.88,
        "on_time_delivery_prob":    0.80,
        "avg_rating":               3.2,
        "rating_std":               0.9,
        "seller_cancellation_rate": 0.08,
        "return_response_rate":     0.30,    # rarely handles returns
        "products_listed_range":    (3, 8),
        "activity_level":           "MEDIUM",
        "label": 0,
    },
    {
        "name": "mixed_seller",
        "weight": 0.15,
        "fulfillment_rate":         0.78,
        "on_time_delivery_prob":    0.72,
        "avg_rating":               3.8,
        "rating_std":               0.7,
        "seller_cancellation_rate": 0.15,
        "return_response_rate":     0.70,
        "products_listed_range":    (2, 7),
        "activity_level":           "MEDIUM",
        "label": 0,
    },
]

# ── Activity level → approximate event count range ────────────────────────────

ACTIVITY_LEVELS = {
    "LOW":    (5,  25),    # 5–25 total events
    "MEDIUM": (20, 80),    # 20–80 total events
    "HIGH":   (60, 150),   # 60–150 total events
}
