import time
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from astronomy_lightrag.token_tracker import TokenTracker

@pytest.fixture
def test_tracker(tmp_path):
    state_file = tmp_path / "token_state.json"
    tracker = TokenTracker(state_file=state_file, quota_per_window=100_000, limit_ratio=0.9)
    return tracker

@pytest.mark.asyncio
async def test_probe_api_availability_success_and_failure(test_tracker, monkeypatch):
    """Verifies that probe_api_availability detects API status correctly."""
    monkeypatch.setenv("LLM_API_KEY", "MOCK_KEY")
    
    # 1. Success case (200)
    mock_resp_200 = MagicMock(status_code=200)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp_200
        assert await test_tracker.probe_api_availability() is True

    # 2. Failure case (402)
    mock_resp_402 = MagicMock(status_code=402)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp_402
        assert await test_tracker.probe_api_availability() is False

@pytest.mark.asyncio
async def test_wait_if_limit_reached_resumes_early_on_probe(test_tracker):
    """Verifies that when probe succeeds, wait_if_limit_reached breaks out early."""
    # Force limit reached
    test_tracker._window_tokens = 95_000
    assert test_tracker.is_limit_reached() is True

    # Mock probe to return True immediately on first check
    with patch.object(test_tracker, "probe_api_availability", new_callable=AsyncMock) as mock_probe, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_probe.return_value = True

        # Run wait with a small heartbeat
        await test_tracker.wait_if_limit_reached(heartbeat_interval=1, enable_probe=True)

        # Verified: probe was called and window was reset early!
        assert mock_probe.called
        assert test_tracker._window_tokens == 0
        assert test_tracker.is_limit_reached() is False
