import time
from datetime import datetime
from pathlib import Path
import pytest

from astronomy_lightrag.token_tracker import (
    TokenTracker,
    get_window_bounds,
    QUOTA_PER_WINDOW,
    SOFT_LIMIT_PER_WINDOW,
    LIMIT_RATIO
)

def test_get_window_bounds_clock_alignment():
    # 02:30 -> window 00:00 - 05:00
    t1 = datetime(2026, 10, 6, 2, 30, 0).timestamp()
    start1, end1 = get_window_bounds(t1)
    assert datetime.fromtimestamp(start1).hour == 0
    assert datetime.fromtimestamp(end1).hour == 5

    # 07:15 -> window 05:00 - 10:00
    t2 = datetime(2026, 10, 6, 7, 15, 0).timestamp()
    start2, end2 = get_window_bounds(t2)
    assert datetime.fromtimestamp(start2).hour == 5
    assert datetime.fromtimestamp(end2).hour == 10

    # 13:45 -> window 10:00 - 15:00
    t3 = datetime(2026, 10, 6, 13, 45, 0).timestamp()
    start3, end3 = get_window_bounds(t3)
    assert datetime.fromtimestamp(start3).hour == 10
    assert datetime.fromtimestamp(end3).hour == 15

    # 17:00 -> window 15:00 - 20:00
    t4 = datetime(2026, 10, 6, 17, 0, 0).timestamp()
    start4, end4 = get_window_bounds(t4)
    assert datetime.fromtimestamp(start4).hour == 15
    assert datetime.fromtimestamp(end4).hour == 20

    # 22:30 -> window 20:00 - 00:00 (next day)
    t5 = datetime(2026, 10, 6, 22, 30, 0).timestamp()
    start5, end5 = get_window_bounds(t5)
    assert datetime.fromtimestamp(start5).hour == 20
    assert datetime.fromtimestamp(end5).hour == 0
    assert datetime.fromtimestamp(end5).day == 7

def test_token_tracker_limits_and_pause(tmp_path):
    state_file = tmp_path / "token_state.json"
    tracker = TokenTracker(
        state_file=state_file,
        quota_per_window=1000,
        limit_ratio=0.90
    )

    assert not tracker.is_limit_reached()

    # Add 800 tokens (< 900)
    ok = tracker.add_usage(800)
    assert ok is True
    assert not tracker.is_limit_reached()

    # Add 150 tokens (total 950 >= 900)
    ok = tracker.add_usage({"prompt_tokens": 100, "completion_tokens": 50})
    assert ok is False
    assert tracker.is_limit_reached()

    summary = tracker.usage_summary()
    assert summary["window_tokens"] == 950
    assert summary["window_limit_reached"] is True
    assert summary["window_pct"] == 95.0

    # Reset
    tracker.reset_window()
    assert not tracker.is_limit_reached()
    assert tracker.usage_summary()["window_tokens"] == 0

def test_token_tracker_mark_limit(tmp_path):
    state_file = tmp_path / "token_state.json"
    tracker = TokenTracker(
        state_file=state_file,
        quota_per_window=1000,
        limit_ratio=0.90
    )

    tracker.mark_limit_reached()
    assert tracker.is_limit_reached()
    assert tracker.usage_summary()["window_tokens"] >= 900
