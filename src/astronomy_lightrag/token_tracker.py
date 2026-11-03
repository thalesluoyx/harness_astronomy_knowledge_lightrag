"""
token_tracker.py
================
5-hour rate-limit window aligned to daily clock hours:
00:00, 05:00, 10:00, 15:00, 20:00.

90% soft limit:
When token usage reaches 90% of the 5-hour quota, the pipeline pauses
and waits until the next window reset, preventing total token exhaustion.
"""
import sys
import time
import json
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Dict, Any, Union

from .config import DATA_DIR, TOKEN_QUOTA_PER_WINDOW, TOKEN_LIMIT_RATIO

logger = logging.getLogger("astronomy_lightrag.token_tracker")

# Quota defaults (MiniMax 5-hour rate-limit window)
MONTHLY_QUOTA = 600_000_000         # 600M tokens / month
WINDOW_SECONDS = 5 * 3600           # 5-hour rate-limit window
QUOTA_PER_WINDOW = TOKEN_QUOTA_PER_WINDOW  # Configurable 5h quota (default 5.4M)
LIMIT_RATIO = TOKEN_LIMIT_RATIO            # 90% soft limit
SOFT_LIMIT_PER_WINDOW = int(QUOTA_PER_WINDOW * LIMIT_RATIO)  # e.g. 4,860,000 tokens

DEFAULT_STATE_FILE = DATA_DIR / "token_tracker_state.json"



def get_window_bounds(t: float) -> Tuple[float, float]:
    """
    Calculate the start and end timestamps of the current 5-hour quota window
    aligned to daily clock hours: 00:00, 05:00, 10:00, 15:00, 20:00.
    """
    dt = datetime.fromtimestamp(t)
    today_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    hour = dt.hour

    if 0 <= hour < 5:
        start_dt = today_start
        end_dt = today_start.replace(hour=5)
    elif 5 <= hour < 10:
        start_dt = today_start.replace(hour=5)
        end_dt = today_start.replace(hour=10)
    elif 10 <= hour < 15:
        start_dt = today_start.replace(hour=10)
        end_dt = today_start.replace(hour=15)
    elif 15 <= hour < 20:
        start_dt = today_start.replace(hour=15)
        end_dt = today_start.replace(hour=20)
    else:  # 20 <= hour < 24
        start_dt = today_start.replace(hour=20)
        end_dt = today_start + timedelta(days=1)

    return start_dt.timestamp(), end_dt.timestamp()


class TokenTracker:
    """
    Thread-safe token usage tracker with automatic 5h window management
    and 90% soft-limit pause mechanism.
    """

    def __init__(
        self,
        state_file: Path = DEFAULT_STATE_FILE,
        quota_per_window: int = QUOTA_PER_WINDOW,
        limit_ratio: float = LIMIT_RATIO
    ):
        self._lock = threading.RLock()
        self._state_file = state_file
        self.quota_per_window = quota_per_window
        self.limit_ratio = limit_ratio
        self.soft_limit = int(quota_per_window * limit_ratio)
        self._window_start = 0.0
        self._window_tokens = 0
        self._monthly_tokens = 0
        self._resume_event = None
        self._load()

    def add_usage(self, tokens: Union[int, Dict[str, Any]]) -> bool:
        """
        Records token usage. Accepts integer token count or dict from OpenAI usage.
        Returns True if under 90% soft limit, False if soft limit is reached.
        """
        if isinstance(tokens, dict):
            token_count = (
                tokens.get("total_tokens")
                or (tokens.get("prompt_tokens", 0) + tokens.get("completion_tokens", 0))
            )
        else:
            token_count = int(tokens)

        with self._lock:
            self._reset_if_window_expired()
            self._window_tokens += token_count
            self._monthly_tokens += token_count
            self._save()
            return self._window_tokens < self.soft_limit

    def is_limit_reached(self) -> bool:
        """Returns True if the 90% soft limit has been reached in current 5h window."""
        with self._lock:
            self._reset_if_window_expired()
            return self._window_tokens >= self.soft_limit

    def mark_limit_reached(self):
        """Manually mark the window limit as reached (e.g. if API returns 402)."""
        with self._lock:
            self._reset_if_window_expired()
            now = time.time()
            # If within 120s of window start and usage is tiny, avoid locking out the entire 5h window
            if (now - self._window_start) < 120 and self._window_tokens < 100_000:
                logger.warning(
                    "⚠️ [TokenTracker] mark_limit_reached requested within 120s of window start. "
                    "Skipping lock-out to prevent false 5h pause from clock skew."
                )
                return
            if self._window_tokens < self.soft_limit:
                self._window_tokens = self.soft_limit
            self._save()

    def time_until_reset(self, buffer_seconds: int = 15) -> int:
        """Seconds remaining until the next 5-hour clock reset (plus safety buffer)."""
        with self._lock:
            now = time.time()
            _, end_ts = get_window_bounds(now)
            return max(0, int(end_ts - now + buffer_seconds))

    def reset_window(self):
        """Force reset the window counter to 0."""
        with self._lock:
            now = time.time()
            start_ts, _ = get_window_bounds(now)
            self._window_start = start_ts
            self._window_tokens = 0
            self._save()

    def reset_window_if_expired(self):
        """Check if current 5-hour window has expired and reset tokens if needed."""
        with self._lock:
            self._reset_if_window_expired()

    def usage_summary(self) -> Dict[str, Any]:
        """Returns full snapshot of current window and monthly usage."""
        with self._lock:
            self._reset_if_window_expired()
            pct_window = (self._window_tokens / self.quota_per_window) * 100
            pct_monthly = (self._monthly_tokens / MONTHLY_QUOTA) * 100
            now = time.time()
            _, end_ts = get_window_bounds(now)
            resume_dt = datetime.fromtimestamp(end_ts)

            return {
                "window_tokens": self._window_tokens,
                "window_quota": self.quota_per_window,
                "window_soft_limit": self.soft_limit,
                "window_pct": round(pct_window, 2),
                "window_limit_reached": self._window_tokens >= self.soft_limit,
                "window_start": self._window_start,
                "seconds_until_reset": self.time_until_reset(),
                "resume_time": resume_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "monthly_tokens": self._monthly_tokens,
                "monthly_quota": MONTHLY_QUOTA,
                "monthly_pct": round(pct_monthly, 2),
            }

    async def probe_api_availability(self) -> bool:
        """
        Actively probes if the LLM API endpoint is available and accepting requests.
        Returns True if successful, False if rate-limited or unavailable.
        """
        try:
            import os
            import httpx
            api_key = os.getenv("LLM_API_KEY")
            base_url = os.getenv("LLM_BASE_URL", "https://api.minimaxi.com/v1")
            model = os.getenv("LLM_MODEL", "MiniMax-M3.1-Flash")
            reasoning_effort = os.getenv("LLM_REASONING_EFFORT", "low")
            if not api_key:
                return False

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "reasoning_effort": reasoning_effort
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                return resp.status_code == 200
        except Exception:
            return False

    async def wait_if_limit_reached(self, heartbeat_interval: int = 300, enable_probe: bool = True):
        """
        Asynchronously checks if 90% limit is reached. If so, pauses execution
        until the 5-hour window reset boundary + 15 seconds buffer.
        Uses an asyncio.Event so multiple concurrent coroutines don't wake up redundantly,
        and logs a single heartbeat every `heartbeat_interval` seconds (default 300s = 5m).
        Actively probes API recovery so transient rate limits resume in minutes rather than hours.
        """
        if not self.is_limit_reached():
            return

        with self._lock:
            if self._resume_event is None:
                self._resume_event = asyncio.Event()
                self._resume_event.set()

        # If another coroutine is already coordinating the pause, simply wait for resume (0% CPU)
        if not self._resume_event.is_set():
            await self._resume_event.wait()
            return

        # First coroutine to detect limit takes the coordinator role
        self._resume_event.clear()

        try:
            summary = self.usage_summary()
            rem_m = summary["seconds_until_reset"] / 60
            rem_h = summary["seconds_until_reset"] / 3600
            logger.warning("=" * 65)
            logger.warning(
                f"⏸️ [TokenTracker] 90% Window Limit Reached! "
                f"Usage: {summary['window_tokens']:,} / {summary['window_quota']:,} "
                f"({summary['window_pct']:.1f}% >= {self.limit_ratio*100:.0f}%)"
            )
            logger.warning(
                f"⏸️ Pausing pipeline until {summary['resume_time']} "
                f"(remaining {rem_m:.1f}m ≈ {rem_h:.2f}h to avoid token exhaustion)..."
            )
            logger.warning("=" * 65)

            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 | 0x00000040)
                except Exception:
                    pass

            probe_counter = 0
            while True:
                now = time.time()
                _, end_ts = get_window_bounds(now)
                if now >= (end_ts + 10.0):
                    break

                # Sleep in chunks of 5 minutes or remainder
                remaining_secs = max(1, int(end_ts - now + 15))
                sleep_chunk = min(heartbeat_interval, remaining_secs)
                await asyncio.sleep(sleep_chunk)

                now = time.time()
                if now >= (end_ts + 10.0):
                    break

                rem_min = (end_ts - now + 15) / 60
                logger.info(
                    f"⏳ [TokenTracker Heartbeat] Paused. Resumes at {summary['resume_time']} "
                    f"({rem_min:.0f} minutes remaining). Sleeping peacefully."
                )

                # Active Probe: test if cloud provider restored early or if 402 was transient
                probe_counter += 1
                if enable_probe and probe_counter >= 1:
                    is_online = await self.probe_api_availability()
                    if is_online:
                        logger.info("⚡ [TokenTracker Prober] API probe succeeded! Provider is accepting calls. Resuming pipeline early!")
                        break

            self.reset_window()
            logger.info("=" * 65)
            logger.info("▶️ [TokenTracker] Pipeline resumed! Proceeding with extraction.")
            logger.info("=" * 65)
        finally:
            self._resume_event.set()


    def _reset_if_window_expired(self):
        now = time.time()
        start_ts, _ = get_window_bounds(now)
        if abs(self._window_start - start_ts) > 1.0:
            self._window_start = start_ts
            self._window_tokens = 0
            self._save()

    def _load(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                self._window_start = data.get("window_start", time.time())
                self._window_tokens = data.get("window_tokens", 0)
                self._monthly_tokens = data.get("monthly_tokens", 0)
                self._reset_if_window_expired()
                return
            except Exception as e:
                logger.warning(f"Failed to read token state file: {e}")

        now = time.time()
        start_ts, _ = get_window_bounds(now)
        self._window_start = start_ts
        self._window_tokens = 0
        self._monthly_tokens = 0

    def _save(self):
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps({
                "window_start": self._window_start,
                "window_tokens": self._window_tokens,
                "monthly_tokens": self._monthly_tokens,
            }, indent=2),
            encoding="utf-8"
        )


_global_tracker = None

def get_token_tracker() -> TokenTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = TokenTracker()
    return _global_tracker
