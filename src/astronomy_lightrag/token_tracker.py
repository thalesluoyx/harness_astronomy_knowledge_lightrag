"""
token_tracker.py
================
5-hour rate-limit window aligned to daily clock hours:
00:00, 05:00, 10:00, 15:00, 20:00.

90% soft limit:
When token usage reaches 90% of the 5-hour quota, the pipeline pauses
and waits until the next window reset, preventing total token exhaustion.
"""
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
            if self._window_tokens < self.soft_limit:
                self._window_tokens = self.soft_limit
            self._save()

    def time_until_reset(self) -> int:
        """Seconds remaining until the next 5-hour clock reset."""
        with self._lock:
            now = time.time()
            _, end_ts = get_window_bounds(now)
            return max(0, int(end_ts - now))

    def reset_window(self):
        """Force reset the window counter to 0."""
        with self._lock:
            now = time.time()
            start_ts, _ = get_window_bounds(now)
            self._window_start = start_ts
            self._window_tokens = 0
            self._save()

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

    async def wait_if_limit_reached(self, heartbeat_interval: int = 60):
        """
        Asynchronously checks if 90% limit is reached. If so, pauses execution
        until the 5-hour window reset boundary + 15 seconds buffer.
        Periodically logs heartbeat status every `heartbeat_interval` seconds
        so logs never stay silent during the pause.
        """
        first_warn = True
        while self.is_limit_reached():
            summary = self.usage_summary()
            remaining_secs = summary["seconds_until_reset"]
            if remaining_secs <= 0:
                self.reset_window()
                break

            remaining_min = remaining_secs / 60
            remaining_hours = remaining_secs / 3600

            if first_warn:
                logger.warning("=" * 65)
                logger.warning(
                    f"⏸️ [TokenTracker] 90% Window Limit Reached! "
                    f"Usage: {summary['window_tokens']:,} / {summary['window_quota']:,} "
                    f"({summary['window_pct']:.1f}% >= {self.limit_ratio*100:.0f}%)"
                )
                logger.warning(
                    f"⏸️ Pausing pipeline until {summary['resume_time']} "
                    f"(remaining {remaining_min:.1f}m ≈ {remaining_hours:.2f}h to avoid token exhaustion)..."
                )
                logger.warning("=" * 65)
                first_warn = False
            else:
                logger.info(
                    f"⏳ [TokenTracker Heartbeat] Paused. Window: {summary['window_pct']:.1f}% "
                    f"({summary['window_tokens']:,}/{summary['window_quota']:,}), "
                    f"Resumes at {summary['resume_time']} (remaining: {remaining_min:.1f}m). "
                    f"Pipeline is alive and waiting."
                )

            step_sleep = min(heartbeat_interval, max(1, remaining_secs))
            await asyncio.sleep(step_sleep)

        if not first_warn:
            self.reset_window()
            logger.info("=" * 65)
            logger.info("▶️ [TokenTracker] 5-hour window reset! Resuming pipeline.")
            logger.info("=" * 65)


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
