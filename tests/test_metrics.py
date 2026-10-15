"""Unit tests for metric helpers, taxonomy and segmentation logic (no workbook needed)."""
import math

import numpy as np
import pandas as pd
import pytest

from analysis import config
from analysis.pipeline.s07_segmentation import assign_segments
from analysis.utils.metrics import minmax_log, pct, robust_z, safe_div, tukey_upper_fence
from analysis.utils.returns import compute_return_flags


def test_pct_and_safe_div():
    assert pct(1, 4) == 25.0
    assert math.isnan(pct(1, 0))
    assert math.isnan(safe_div(3, 0))
    assert pct(1, 3, 2) == 33.33


def test_tukey_fence():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8])
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    assert tukey_upper_fence(s, 3) == pytest.approx(q3 + 3 * (q3 - q1))


def test_minmax_log_bounds_and_monotonic():
    s = pd.Series([0, 1, 2, 5, 10, 1000])
    t = minmax_log(s)
    assert t.min() == 0 and t.max() == pytest.approx(1)
    assert t.is_monotonic_increasing


def test_robust_z_constant_series():
    assert (robust_z(pd.Series([3, 3, 3])) == 0).all()


def test_taxonomy_covers_meaningful_definition():
    assert set(config.MEANINGFUL_EVENTS) == {
        "ad_completed", "captcha_completed", "daily_reward_claimed", "follow_task_completed", "mining_activity",
        "mission_completed", "referral_created", "referral_shared", "spin_completed", "streak_claimed", "tap_completed"}
    # system-awarded / negative events are excluded
    for ev in ("badge_earned", "level_up", "streak_broken", "mining_stopped"):
        assert ev not in config.MEANINGFUL_EVENTS
    assert len(config.FEATURES) == 15
    assert set(config.FEATURE_AREA) == set(config.FEATURES)


def test_segments_are_mutually_exclusive_and_ordered():
    days = pd.Series([0, 1, 2, 4, 5, 9, 10, 30, 3])
    breadth = pd.Series([0, 3, 2, 2, 2, 9, 1, 11, 8])
    seg = assign_segments(days, breadth, med=5, p75=10, breadth=8)
    assert list(seg) == ["No Recorded Activity", "One-Time Users", "Occasional Users", "Occasional Users",
                         "Returning Users", "Multi-Feature Users", "High-Frequency Users", "High-Frequency Users",
                         "Multi-Feature Users"]


def test_return_flags_censoring_and_windows():
    end = pd.Timestamp("2026-01-31 23:00")
    users = pd.DataFrame({"user_id": ["a", "b", "c"],
                          "first_active_date": pd.to_datetime(["2026-01-01", "2026-01-01", "2026-01-28"])})
    ud = pd.DataFrame({"user_id": ["a", "a", "b", "c", "c"],
                       "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-10", "2026-01-28", "2026-01-29"])})
    rf = compute_return_flags(users, ud, end)
    assert rf.loc["a", "D1_return"] == 1 and rf.loc["b", "D1_return"] == 0
    assert rf.loc["b", "D14_return"] == 1 and rf.loc["a", "D14_return"] == 0
    assert rf.loc["c", "D1_return"] == 1
    assert np.isnan(rf.loc["c", "D7_return"])  # window not fully observable -> censored, not a failure
    assert not rf.loc["c", "D7_eligible"]
