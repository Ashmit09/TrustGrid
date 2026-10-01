"""
TrustGrid — Unit Tests: Time Decay Engine (spec §24-A, §24-B partial)

Run with:
    cd TrustGrid && source .venv/bin/activate
    PYTHONPATH=backend pytest backend/tests/test_time_decay.py -v
"""
import math
import pytest
from datetime import datetime, timezone, timedelta

# Set PYTHONPATH to backend before importing
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.time_decay import decay_weight, event_age_days, decayed_rate, decayed_average
from app.core.constants import DECAY_LAMBDA


# ── decay_weight ─────────────────────────────────────────────────────────────

class TestDecayWeight:
    def test_age_0_is_1(self):
        assert decay_weight(0) == pytest.approx(1.0, abs=1e-6)

    def test_age_90_is_half(self):
        """90-day half-life must produce exactly 0.5."""
        assert decay_weight(90) == pytest.approx(0.5, abs=1e-6)

    def test_age_180_is_quarter(self):
        assert decay_weight(180) == pytest.approx(0.25, abs=1e-4)

    def test_age_270_is_eighth(self):
        assert decay_weight(270) == pytest.approx(0.125, abs=1e-4)

    def test_age_7_approx(self):
        """spec table: 7 days ≈ 0.947"""
        assert decay_weight(7) == pytest.approx(0.947, abs=0.002)

    def test_age_30_approx(self):
        """spec table: 30 days ≈ 0.794"""
        assert decay_weight(30) == pytest.approx(0.794, abs=0.002)

    def test_age_60_approx(self):
        """spec table: 60 days ≈ 0.630"""
        assert decay_weight(60) == pytest.approx(0.630, abs=0.002)

    def test_strictly_decreasing(self):
        """10 < 30 < 90 < 180 — weights must be strictly decreasing."""
        ages = [10, 30, 90, 180]
        weights = [decay_weight(a) for a in ages]
        for i in range(len(weights) - 1):
            assert weights[i] > weights[i + 1], \
                f"weight({ages[i]}) should be > weight({ages[i+1]})"

    def test_negative_age_clamped_to_1(self):
        """Future events are clamped to age 0, so weight = 1."""
        assert decay_weight(-10) == pytest.approx(1.0, abs=1e-6)

    def test_lambda_value(self):
        """λ = ln(2)/90"""
        expected = math.log(2) / 90
        assert DECAY_LAMBDA == pytest.approx(expected, rel=1e-6)


# ── event_age_days ────────────────────────────────────────────────────────────

class TestEventAgeDays:
    def test_same_time_is_zero(self):
        now = datetime.now(timezone.utc)
        assert event_age_days(now, now) == pytest.approx(0.0, abs=1e-6)

    def test_one_day(self):
        ref = datetime.now(timezone.utc)
        event = ref - timedelta(days=1)
        assert event_age_days(event, ref) == pytest.approx(1.0, abs=1e-4)

    def test_90_days(self):
        ref = datetime.now(timezone.utc)
        event = ref - timedelta(days=90)
        assert event_age_days(event, ref) == pytest.approx(90.0, abs=0.01)

    def test_future_event_returns_zero(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=5)
        assert event_age_days(future, now) == 0.0

    def test_naive_datetimes_treated_as_utc(self):
        ref = datetime(2024, 1, 31, 12, 0, 0)   # naive
        event = datetime(2024, 1, 1, 12, 0, 0)  # naive, 30 days earlier
        age = event_age_days(event, ref)
        assert age == pytest.approx(30.0, abs=0.01)


# ── decayed_rate ──────────────────────────────────────────────────────────────

class TestDecayedRate:
    def test_all_positive_returns_near_1(self):
        events = [(5, 1), (10, 1), (20, 1), (50, 1)]
        assert decayed_rate(events) == pytest.approx(1.0, abs=1e-6)

    def test_all_negative_returns_0(self):
        events = [(5, 0), (10, 0), (20, 0)]
        assert decayed_rate(events) == pytest.approx(0.0, abs=1e-6)

    def test_empty_returns_default(self):
        assert decayed_rate([]) == pytest.approx(0.5, abs=1e-6)
        assert decayed_rate([], default_if_empty=0.7) == pytest.approx(0.7, abs=1e-6)

    def test_result_within_0_1(self):
        events = [(1, 1), (10, 0), (30, 1), (90, 0), (180, 1)]
        rate = decayed_rate(events)
        assert 0.0 <= rate <= 1.0

    def test_spec_worked_example(self):
        """
        Spec §7 worked example:
            5-day completed  (positive)  → w=0.962
            10-day completed (positive)  → w=0.926
            20-day cancelled (negative)  → w=0.857
            120-day completed(positive)  → w=0.397
        Expected rate = (0.962+0.926+0.397) / (0.962+0.926+0.857+0.397)
                      = 2.285 / 3.142 ≈ 0.727
        """
        events = [(5, 1), (10, 1), (20, 0), (120, 1)]
        rate = decayed_rate(events)
        assert rate == pytest.approx(0.727, abs=0.005)

    def test_recent_events_outweigh_old(self):
        """A recent negative must pull rate down more than an old positive pulls it up."""
        # Scenario A: old cancellation + recent success → should be better than B
        # Scenario B: old success + recent cancellation → worse assessment
        scenario_a = [(100, 0), (1, 1)]   # 100-day cancel, 1-day success
        scenario_b = [(100, 1), (1, 0)]   # 100-day success, 1-day cancel
        rate_a = decayed_rate(scenario_a)
        rate_b = decayed_rate(scenario_b)
        assert rate_a > rate_b, \
            "Scenario A (recent success) must score higher than Scenario B (recent cancel)"


# ── decayed_average ────────────────────────────────────────────────────────────

class TestDecayedAverage:
    def test_empty_returns_default(self):
        assert decayed_average([]) == pytest.approx(0.0, abs=1e-6)
        assert decayed_average([], default_if_empty=3.0) == pytest.approx(3.0, abs=1e-6)

    def test_uniform_values(self):
        """When all values are equal, the average should equal that value."""
        events = [(5, 4.0), (10, 4.0), (90, 4.0)]
        assert decayed_average(events) == pytest.approx(4.0, abs=1e-6)

    def test_recent_value_dominates(self):
        """A recent high rating should pull the average up compared to old low rating."""
        recent_high = [(2, 5.0), (200, 1.0)]
        recent_low  = [(2, 1.0), (200, 5.0)]
        assert decayed_average(recent_high) > decayed_average(recent_low)
