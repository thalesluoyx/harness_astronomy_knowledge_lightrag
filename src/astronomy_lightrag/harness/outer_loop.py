"""
outer_loop.py
5-Hour Clock-Aligned Outer Loop Scheduler for Ingestion Orchestration.

Aligns with MiniMax official 5-hour fixed window boundaries:
00:00, 05:00, 10:00, 15:00, 20:00 daily.

Functions:
1. Calculates exact countdown seconds until next window reset.
2. Detects near-boundary conditions (within last 10 minutes) to avoid launching heavy jobs.
3. Automatically sleeps and resumes pipeline across natural day boundaries.
4. Integrates with TokenTracker 90% threshold for self-healing quota management.
"""
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Coroutine, Any, Optional

logger = logging.getLogger("astronomy_lightrag.harness.outer_loop")

# Fixed 5-hour clock reset hours
RESET_HOURS = [0, 5, 10, 15, 20]


def get_next_window_reset_time(now: Optional[datetime] = None) -> datetime:
    """
    Calculates the exact next clock reset datetime (00:00, 05:00, 10:00, 15:00, 20:00).
    """
    if now is None:
        now = datetime.now()

    current_hour = now.hour

    # Find the next hour in RESET_HOURS today
    next_hour = None
    for h in RESET_HOURS:
        if h > current_hour:
            next_hour = h
            break

    if next_hour is not None:
        return now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    else:
        # Rolls over to 00:00 tomorrow
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=RESET_HOURS[0], minute=0, second=0, microsecond=0)


def get_seconds_until_next_reset(now: Optional[datetime] = None) -> float:
    """Returns the number of seconds until the next 5-hour window reset."""
    if now is None:
        now = datetime.now()
    target = get_next_window_reset_time(now)
    delta = (target - now).total_seconds()
    return max(0.0, delta)


def is_near_window_boundary(threshold_minutes: int = 10, now: Optional[datetime] = None) -> bool:
    """
    Returns True if current time is within `threshold_minutes` before a window reset.
    Useful for graceful shutdown of long-running extractions.
    """
    secs = get_seconds_until_next_reset(now)
    return secs <= (threshold_minutes * 60)


async def sleep_until_next_window(buffer_seconds: int = 15):
    """
    Asynchronously sleeps until the next fixed 5-hour window boundary plus a small buffer.
    """
    now = datetime.now()
    reset_time = get_next_window_reset_time(now)
    secs = get_seconds_until_next_reset(now) + buffer_seconds
    hours = secs / 3600.0

    logger.warning(
        f"⏳ [OuterLoop Scheduler] Entering scheduled rest until next 5h window at "
        f"{reset_time.strftime('%H:%M:%S')}. Sleeping for {secs:.0f}s ({hours:.2f} hours)..."
    )

    # Sleep in 60s increments to allow logging and interrupt handling
    rem = secs
    while rem > 0:
        sleep_chunk = min(rem, 60.0)
        await asyncio.sleep(sleep_chunk)
        rem -= sleep_chunk
        if int(rem) % 600 == 0 and rem > 0:
            logger.info(f"⏳ [OuterLoop] Sleep countdown: {rem/60.0:.0f} minutes remaining...")

    logger.info("🌅 [OuterLoop Scheduler] New 5-hour window opened! Resuming orchestration pipeline...")


if __name__ == "__main__":
    now = datetime.now()
    next_reset = get_next_window_reset_time(now)
    secs = get_seconds_until_next_reset(now)
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Next 5h reset: {next_reset.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Countdown: {secs:.1f}s ({secs/3600:.2f} hours)")
    print(f"Near boundary (<10m): {is_near_window_boundary()}")
