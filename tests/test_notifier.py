import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from astronomy_lightrag.harness.notifier import send_notification, notify_quarantined_book

@pytest.mark.asyncio
async def test_normal_milestone_does_not_call_serverchan(monkeypatch):
    """Verifies normal info/success notifications NEVER call ServerChan."""
    monkeypatch.setenv("SERVERCHAN_KEY", "MOCK_KEY_123")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Normal milestone (unrecoverable=False)
        result = await send_notification("Test Milestone", "Content", msg_type="success", unrecoverable=False)
        # ServerChan URL should NOT have been called
        serverchan_calls = [
            call for call in mock_post.call_args_list 
            if "ftqq.com" in str(call)
        ]
        assert len(serverchan_calls) == 0, "ServerChan must NOT be called for normal milestones"

@pytest.mark.asyncio
async def test_unrecoverable_error_calls_serverchan(monkeypatch):
    """Verifies that unrecoverable errors DO trigger ServerChan."""
    monkeypatch.setenv("SERVERCHAN_KEY", "MOCK_KEY_123")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"code":0,"message":"success"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        
        # Unrecoverable error
        await notify_quarantined_book("book_056", "Test Book", "Fatal database error", attempts=3)
        
        serverchan_calls = [
            call for call in mock_post.call_args_list 
            if "ftqq.com" in str(call)
        ]
        assert len(serverchan_calls) == 1, "ServerChan MUST be called for unrecoverable quarantined errors"
        # Verify content includes title and warning
        args, kwargs = serverchan_calls[0]
        assert "SCT353592T20S34FfavVzI15xiQWjcabtl" in args[0] or "MOCK_KEY_123" in args[0]
        assert "book_056" in kwargs["data"]["desp"]
