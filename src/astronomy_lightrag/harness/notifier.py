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
    msg_type: str = "info" # "info", "warning", "success", "error"
) -> bool:
    """
    Sends a formatted notification to all configured alert channels.
    Always logs the notification to the local logger.
    """
    prefix = {
        "info": "ℹ️",
        "warning": "⚠️",
        "success": "🎉",
        "error": "❌"
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

    # 3. ServerChan (Server酱推送微信)
    serverchan_key = os.getenv("SERVERCHAN_KEY") or os.getenv("SERVERCHAN_SENDKEY") or ""
    if serverchan_key:
        try:
            url = f"https://sctapi.ftqq.com/{serverchan_key}.send"
            payload = {"title": full_title, "desp": content_markdown}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data=payload)
                if resp.status_code == 200:
                    sent = True
                    logger.info("Notification successfully delivered via ServerChan to WeChat.")
        except Exception as e:
            logger.warning(f"Failed to post to ServerChan: {e}")

    # 4. PushPlus
    pushplus_token = os.getenv("PUSHPLUS_TOKEN", "")
    if pushplus_token:
        try:
            url = "http://www.pushplus.plus/send"
            payload = {
                "token": pushplus_token,
                "title": full_title,
                "content": content_markdown,
                "template": "markdown"
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload)
                sent = True
        except Exception as e:
            logger.warning(f"Failed to post to PushPlus: {e}")

    return sent


async def notify_milestone(
    book_index: int,
    total_books: int,
    book_title: str,
    chunks_count: int,
    total_tokens: int,
    elapsed_time_str: str
):
    """Sends a book ingestion milestone notification."""
    pct = (book_index / total_books) * 100
    md = (
        f"**进度**: 第 {book_index}/{total_books} 本 ({pct:.1f}%)\n"
        f"**当前完成**: {book_title}\n"
        f"**本批处理**: {chunks_count:,} chunks\n"
        f"**累计 Token**: {total_tokens:,} tokens\n"
        f"**总运行时长**: {elapsed_time_str}"
    )
    await send_notification(f"书籍摄取里程碑 ({book_index}/{total_books})", md, msg_type="success")


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
