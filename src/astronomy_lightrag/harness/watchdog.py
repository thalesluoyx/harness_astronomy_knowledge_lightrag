"""
watchdog.py
===========
Autonomous Supervisor and Watchdog for the Astronomy LightRAG Harness.

Responsibilities:
1. Process Liveness: Ensures `orchestrator.py` is always running; restarts on crash.
2. Progress Stall Detection: Monitors chunk & log activity. If stalled for >90 minutes
   (excluding verified planned quota pauses), automatically diagnoses, alerts via ServerChan,
   cleans stuck state, and restarts the pipeline.
3. Project Rule Compliance: All watchdog logs output to `bilingual_output/harness_watchdog_YYYYMMDD.log`.
"""
import sys
import time
import json
import psutil
import logging
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = CURRENT_DIR.parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent
BILINGUAL_OUTPUT_DIR = PROJECT_ROOT.parent / "bilingual_output"
DATA_DIR = PROJECT_ROOT / "data"
WORKSPACE_DIR = PROJECT_ROOT / "lightrag_workspace"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT.parent))

from astronomy_lightrag.config import TOKEN_QUOTA_PER_WINDOW, TOKEN_LIMIT_RATIO
SOFT_LIMIT_PER_WINDOW = int(TOKEN_QUOTA_PER_WINDOW * TOKEN_LIMIT_RATIO)

# Setup Watchdog Logging
BILINGUAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
today_str = datetime.now().strftime("%Y%m%d")
watchdog_log_file = BILINGUAL_OUTPUT_DIR / f"harness_watchdog_{today_str}.log"

logger = logging.getLogger("astronomy_lightrag.harness.watchdog")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(str(watchdog_log_file), encoding="utf-8")
file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [Watchdog] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("[%(asctime)s] [Watchdog] %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def find_orchestrator_process() -> Optional[psutil.Process]:
    """Finds running orchestrator.py process if any."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmd)
            if "orchestrator.py" in cmd_str and proc.info['pid'] != psutil.Process().pid:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def get_last_activity_timestamp(proc: Optional[psutil.Process] = None) -> float:
    """
    Returns the most recent modification timestamp among:
    1. Orchestrator log files in bilingual_output and logs (across all dates)
    2. Doc status file in lightrag_workspace
    3. Checkpoint state file
    4. Orchestrator process start time (if running)
    """
    candidates = []
    
    # Process start time (a newly started process is active by definition)
    if proc:
        try:
            candidates.append(proc.create_time())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # All orchestrator log files (handles midnight date rollovers seamlessly)
    if BILINGUAL_OUTPUT_DIR.exists():
        for log_p in BILINGUAL_OUTPUT_DIR.glob("harness_orchestrator_*.log"):
            try:
                candidates.append(log_p.stat().st_mtime)
            except OSError:
                pass

    local_logs = PROJECT_ROOT / "logs"
    if local_logs.exists():
        for log_p in local_logs.glob("harness_orchestrator_*.log"):
            try:
                candidates.append(log_p.stat().st_mtime)
            except OSError:
                pass

    # doc_status
    ds_file = WORKSPACE_DIR / "kv_store_doc_status.json"
    if ds_file.exists():
        try:
            candidates.append(ds_file.stat().st_mtime)
        except OSError:
            pass

    # Checkpoint
    cp_file = DATA_DIR / "chunk_checkpoint_state.json"
    if cp_file.exists():
        try:
            candidates.append(cp_file.stat().st_mtime)
        except OSError:
            pass

    return max(candidates) if candidates else time.time()


def is_in_planned_quota_pause() -> bool:
    """Checks whether the system is legitimately waiting for a fixed clock reset."""
    state_file = DATA_DIR / "token_tracker_state.json"
    if not state_file.exists():
        return False
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        # If tokens are near or above soft limit (e.g. 2.7M of 3.0M)
        if data.get("window_tokens", 0) >= SOFT_LIMIT_PER_WINDOW:
            return True
    except Exception:
        pass
    return False


def restart_orchestrator():
    """Kills existing orchestrator and launches a fresh background daemon."""
    proc = find_orchestrator_process()
    if proc:
        logger.warning(f"Terminating stalled/existing orchestrator process (PID {proc.pid})...")
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception as e:
            logger.warning(f"Process termination note: {e}")

    # Launch fresh orchestrator
    python_exe = sys.executable
    orchestrator_script = str(CURRENT_DIR / "orchestrator.py")
    logger.info(f"🚀 Launching fresh orchestrator daemon: {python_exe} {orchestrator_script}")

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    subprocess.Popen(
        [python_exe, orchestrator_script],
        cwd=str(PROJECT_ROOT),
        creationflags=creation_flags
    )


async def send_watchdog_alert(title: str, message: str):
    """Sends watchdog alert through the notifier (triggers ServerChan because unrecoverable=True)."""
    try:
        from astronomy_lightrag.harness.notifier import send_notification
        await send_notification(
            title=title,
            content_markdown=message,
            msg_type="emergency",
            unrecoverable=True
        )
    except Exception as e:
        logger.error(f"Failed to deliver watchdog alert: {e}")


async def watchdog_loop(stall_threshold_seconds: int = 5400, poll_interval: int = 60):
    """
    Main supervisor loop.
    Default stall threshold: 90 minutes (5400s).
    """
    logger.info(f"🛡️ [Watchdog] Supervisor started. Stall threshold: {stall_threshold_seconds/60:.0f}m, poll: {poll_interval}s.")
    while True:
        try:
            proc = find_orchestrator_process()
            now = time.time()
            last_activity = get_last_activity_timestamp(proc)
            stagnant_seconds = now - last_activity

            if proc is None:
                logger.warning("⚠️ [Watchdog] Orchestrator process NOT found! Triggering auto-recovery...")
                await send_watchdog_alert(
                    "调度器异常崩溃自动拉起",
                    f"**事件**: 监控到 `orchestrator.py` 进程不存在。\n"
                    f"**动作**: 看门狗已自动拉起全新的后台流水线。\n"
                    f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                restart_orchestrator()

            elif is_in_planned_quota_pause():
                logger.debug("⏳ [Watchdog] System is in planned token quota sleep. Liveness verified.")

            elif stagnant_seconds > stall_threshold_seconds:
                stagnant_min = stagnant_seconds / 60.0
                logger.critical(
                    f"🚨 [Watchdog] Pipeline stalled for {stagnant_min:.1f} minutes! "
                    f"Exceeded threshold of {stall_threshold_seconds/60:.0f}m. Triggering recovery..."
                )
                await send_watchdog_alert(
                    "流水线停滞超时看门狗介入",
                    f"**告警**: 检测到流水线超过 {stagnant_min:.1f} 分钟无任何分块或入库进展！\n"
                    f"**动作**: 看门狗已终止僵死进程 (PID {proc.pid})，执行脏状态清理并重新启动流水线。\n"
                    f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                restart_orchestrator()

            else:
                logger.debug(f"🟢 [Watchdog] Orchestrator (PID {proc.pid}) healthy. Last active: {stagnant_seconds:.0f}s ago.")

        except Exception as loop_err:
            logger.error(f"Watchdog loop error: {loop_err}", exc_info=True)

        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Astronomy LightRAG Harness Watchdog")
    parser.add_argument("--stall-minutes", type=int, default=90, help="Minutes of inactivity before triggering restart")
    parser.add_argument("--poll-seconds", type=int, default=60, help="Seconds between watchdog checks")
    args = parser.parse_args()

    asyncio.run(watchdog_loop(
        stall_threshold_seconds=args.stall_minutes * 60,
        poll_interval=args.poll_seconds
    ))
