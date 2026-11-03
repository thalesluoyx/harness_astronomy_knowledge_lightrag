import time
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from astronomy_lightrag.harness.watchdog import (
    find_orchestrator_process,
    get_last_activity_timestamp,
    is_in_planned_quota_pause,
    watchdog_loop
)

def test_is_in_planned_quota_pause_detection(tmp_path, monkeypatch):
    """Verifies that watchdog correctly identifies planned 90% quota pause."""
    state_file = tmp_path / "token_tracker_state.json"
    monkeypatch.setattr("astronomy_lightrag.harness.watchdog.DATA_DIR", tmp_path)

    # 1. Under limit (no pause)
    state_file.write_text('{"window_tokens": 1000000}', encoding="utf-8")
    assert is_in_planned_quota_pause() is False

    # 2. Reached 90% soft limit (in pause)
    from astronomy_lightrag.token_tracker import SOFT_LIMIT_PER_WINDOW
    state_file.write_text(f'{{"window_tokens": {SOFT_LIMIT_PER_WINDOW + 100}}}', encoding="utf-8")
    assert is_in_planned_quota_pause() is True

@pytest.mark.asyncio
async def test_watchdog_restarts_when_orchestrator_process_missing():
    """Verifies that watchdog detects dead orchestrator and calls restart + alert."""
    with patch("astronomy_lightrag.harness.watchdog.find_orchestrator_process", return_value=None), \
         patch("astronomy_lightrag.harness.watchdog.send_watchdog_alert", new_callable=AsyncMock) as mock_alert, \
         patch("astronomy_lightrag.harness.watchdog.restart_orchestrator") as mock_restart, \
         patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        
        try:
            await watchdog_loop(stall_threshold_seconds=60, poll_interval=1)
        except asyncio.CancelledError:
            pass

        assert mock_alert.called, "Watchdog should alert when orchestrator dies"
        assert mock_restart.called, "Watchdog should restart when orchestrator dies"

@pytest.mark.asyncio
async def test_watchdog_triggers_on_stalled_progress():
    """Verifies that watchdog detects progress stall > threshold and restarts."""
    mock_proc = MagicMock(pid=12345)
    # Stalled activity 2 hours ago (7200 seconds)
    stalled_time = time.time() - 7200

    with patch("astronomy_lightrag.harness.watchdog.find_orchestrator_process", return_value=mock_proc), \
         patch("astronomy_lightrag.harness.watchdog.get_last_activity_timestamp", return_value=stalled_time), \
         patch("astronomy_lightrag.harness.watchdog.is_in_planned_quota_pause", return_value=False), \
         patch("astronomy_lightrag.harness.watchdog.send_watchdog_alert", new_callable=AsyncMock) as mock_alert, \
         patch("astronomy_lightrag.harness.watchdog.restart_orchestrator") as mock_restart, \
         patch("asyncio.sleep", side_effect=asyncio.CancelledError):

        try:
            # Stall threshold is 90 min (5400s)
            await watchdog_loop(stall_threshold_seconds=5400, poll_interval=1)
        except asyncio.CancelledError:
            pass

        assert mock_alert.called, "Watchdog should alert on progress stall > 90m"
        assert mock_restart.called, "Watchdog should kill & restart stalled process"
