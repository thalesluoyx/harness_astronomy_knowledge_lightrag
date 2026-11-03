"""
notifier.py
Multi-Channel Alert & Milestone Notification Manager for Astronomy Harness.

Supports:
1. WeChat Work (企业微信机器人 Webhook)
2. ServerChan (Server酱) / PushPlus (pushplus 推送加)
3. Custom HTTP Webhook endpoints
4. Safe fallback to Python logging when no webhook is configured.
"""
import os
import httpx
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

logger = logging.getLogger("astronomy_lightrag.harness.notifier")


async def send_notification(
    title: str,
    content_markdown: str,
    msg_type: str = "info", # "info", "warning", "success", "error", "emergency"
    *,
    unrecoverable: bool = False
) -> bool:
    """
    Sends a formatted notification to configured alert channels.
    - WeChat: Primary channel for all progress, milestones, warnings, and errors.
    - ServerChan: STRICTLY reserved for unrecoverable failures (quarantine, fatal stalls)
      where the system cannot self-heal.
    """
    prefix = {
        "info": "ℹ️",
        "warning": "⚠️",
        "success": "🎉",
        "error": "❌",
        "emergency": "🚨"
    }.get(msg_type, "📢")

    full_title = f"{prefix} {title}"
    logger.info(f"[Notification] {full_title}\n{content_markdown}")

    sent = False

    # 1. Primary WeChat channel via openclaw / bilingual_common
    try:
        import sys
        sys_path_root = str(Path(__file__).resolve().parent.parent.parent.parent)
        if sys_path_root not in sys.path:
            sys.path.insert(0, sys_path_root)
        from bilingual_common.notifier import notify as bc_notify
        wechat_text = f"{full_title}\n\n{content_markdown}"
        if await bc_notify(wechat_text):
            sent = True
    except Exception as e:
        logger.debug(f"bilingual_common notify skipped or error: {e}")

    # 2. WeChat Work Bot Webhook (if explicitly configured)
    wechat_webhook = os.getenv("WECHAT_WEBHOOK_URL", "")
    if wechat_webhook:
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {full_title}\n\n{content_markdown}\n\n> 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(wechat_webhook, json=payload)
                if resp.status_code == 200:
                    sent = True
        except Exception as e:
            logger.warning(f"Failed to post to WeChat Webhook: {e}")

    # 3. ServerChan (Server酱推送微信) - ONLY for unrecoverable failures
    is_fatal = unrecoverable or msg_type == "emergency"
    serverchan_key = os.getenv("SERVERCHAN_KEY") or os.getenv("SERVERCHAN_SENDKEY") or ""
    if serverchan_key and is_fatal:
        try:
            url = f"https://sctapi.ftqq.com/{serverchan_key}.send"
            payload = {
                "title": f"🚨 [Harness紧急告警] {title}",
                "desp": f"### ⚠️ 系统无法自动修复，需要人工介入！\n\n{content_markdown}\n\n> 触发时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data=payload)
                if resp.status_code == 200:
                    sent = True
                    logger.info("Critical alert successfully delivered via ServerChan fallback.")
                else:
                    logger.warning(f"ServerChan returned HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Failed to post to ServerChan: {e}")

    return sent


async def notify_quarantined_book(
    book_id: str,
    book_title: str,
    error_msg: str,
    attempts: int = 3
):
    """
    Sends an unrecoverable failure alert (both WeChat and ServerChan)
    when a book exhausts all retries and is moved to the quarantine queue.
    """
    md = (
        f"**故障书籍**: `[{book_id}]` {book_title}\n"
        f"**失败重试**: 已连续重试 {attempts} 次，均未通过\n"
        f"**错误详情**: {error_msg}\n"
        f"**系统动作**: 🚫 该书籍已移入隔离区 (`quarantine_books.json`)，流水线已挂起保护，未静默跳过。\n"
        f"**请人类工程师介入检查**。"
    )
    await send_notification(
        f"书籍入库受阻已隔离: [{book_id}]",
        md,
        msg_type="emergency",
        unrecoverable=True
    )


async def notify_milestone(
    book_index: int = 0,
    total_books: int = 0,
    book_title: str = "",
    chunks_count: int = 0,
    total_tokens: int = 0,
    elapsed_time_str: str = "",
    quality_score: str = "20/20 (无污染)",
    *,
    book_id: str = "",
    global_completed: Optional[int] = None,
    total_corpus: Optional[int] = None,
    batch_index: Optional[int] = None,
    batch_total: Optional[int] = None,
    window_pct: Optional[float] = None
):
    """
    Sends an accurate, comprehensive book ingestion milestone notification.
    Clearly distinguishes global corpus progress from current batch cruise progress.
    """
    g_done = global_completed if global_completed is not None else book_index
    g_total = total_corpus if total_corpus is not None else total_books
    g_pct = (g_done / max(1, g_total)) * 100

    b_idx = batch_index if batch_index is not None else book_index
    b_tot = batch_total if batch_total is not None else total_books

    token_m = total_tokens / 1_000_000
    monthly_budget_pct = (total_tokens / 600_000_000) * 100

    id_prefix = f"[{book_id}] " if book_id else ""
    title_str = f"书籍入库里程碑: {id_prefix}({g_done}/{g_total})"

    lines = [
        f"**当前完成**: {id_prefix}{book_title}",
        f"**全库总进度**: **{g_done} / {g_total} 本 ({g_pct:.1f}%)**",
    ]
    if batch_index is not None or (b_tot != g_total and b_tot > 0):
        lines.append(f"**本批次巡航**: 第 {b_idx} / {b_tot} 本")

    lines.extend([
        f"**本批处理分块**: {chunks_count:,} chunks",
        f"**图谱自检**: 清洁度 {quality_score} (已入库抽样池)",
        f"**累计已耗 Token**: **{token_m:.2f}M** / 600M ({monthly_budget_pct:.1f}%)",
    ])
    if window_pct is not None:
        lines.append(f"**当前 5h 窗口**: 已用 {window_pct:.1f}%")
    lines.append(f"**总运行时长**: {elapsed_time_str}")

    md = "\n".join(lines)
    await send_notification(title_str, md, msg_type="success")


async def notify_quota_pause(
    current_tokens: int,
    quota_limit: int,
    next_reset_time: str,
    sleep_hours: float
):
    """Sends a quota exhaustion sleep notification."""
    md = (
        f"**当前 5h 消耗**: {current_tokens:,} / {quota_limit:,} tokens (达到 90% 阈值)\n"
        f"**计划唤醒时间**: {next_reset_time}\n"
        f"**休眠时长**: 约 {sleep_hours:.2f} 小时\n"
        f"系统已进入安全挂起状态，将在窗口重置后全自动恢复流水线。"
    )
    await send_notification("5小时 Token 额度保护挂起", md, msg_type="warning")
