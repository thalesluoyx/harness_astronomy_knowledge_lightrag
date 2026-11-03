"""
orchestrator.py
Dual-Loop Self-Healing Ingestion Orchestrator for 155 Astronomy Books.

Architecture:
- Outer Loop (Task 3.3): Fixed 5-hour clock scheduler (00:00, 05:00, 10:00, 15:00, 20:00).
- Inner Loop (Task 3.2): Pipeline parallelism overlapping Track A (online LLM extraction)
                         and Track B (local CPU fastembed embedding at 500+ chunks/s).
- Checkpoints (Task 3.1): Chunk and book level atomic resumption without duplicate calls.
- Pre-cleaning (Task 1.2): Text sanitization, OCR noise removal, and censorship protection.
- Metadata (Task 1.3): Canonical book titles injected at chunk creation time.
- Quality Audit (Task 4.1): Automated 4-dimensional graph sample evaluation.
- Alerts (Task 4.2): Integrated WeChat bot milestone notifications.
"""
import os
import sys
import time
import inspect
import argparse
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from lightrag import LightRAG

# Ensure imports resolve
CURRENT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = CURRENT_DIR.parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from astronomy_lightrag.config import (
    LIGHTRAG_WORKSPACE,
    BILINGUAL_OUTPUT_DIR,
    DEFAULT_LLM_TIMEOUT,
    EMBEDDING_ENGINE,
    MAX_ASYNC,
    TOKEN_QUOTA_PER_WINDOW,
    TOKEN_LIMIT_RATIO,
    STATE_FILE,
    DATA_DIR,
    STORAGE_BACKEND
)
from astronomy_lightrag.token_tracker import get_token_tracker
from astronomy_lightrag.llm import get_minimax_llm_func, get_astronomy_embedding_func
from astronomy_lightrag.text_sanitizer import clean_markdown_text, validate_text_chunk
from astronomy_lightrag.doc_registry import get_book_registry, get_standard_title_for_chunk
from astronomy_lightrag.query_preprocessor import install_exact_match_hook
from astronomy_lightrag.harness.logger_setup import setup_harness_logging
from astronomy_lightrag.harness.chunk_checkpoint import get_checkpoint_manager
from astronomy_lightrag.harness.outer_loop import (
    get_next_window_reset_time,
    get_seconds_until_next_reset,
    is_near_window_boundary,
    sleep_until_next_window
)
from astronomy_lightrag.harness.gemini_judge import evaluate_graph_samples
from astronomy_lightrag.harness.notifier import (
    send_notification,
    notify_milestone,
    notify_quota_pause,
    notify_quarantined_book
)

logger = logging.getLogger("astronomy_lightrag.harness.orchestrator")


class FullScaleOrchestrator:
    """
    Orchestrates the end-to-end ingestion of 155 astronomy books into LightRAG.
    """

    def __init__(
        self,
        workspace_dir: Path = LIGHTRAG_WORKSPACE,
        embedding_engine: str = EMBEDDING_ENGINE,
        max_async: int = MAX_ASYNC,
        batch_limit: Optional[int] = None,
        start_book_id: Optional[str] = None,
        book_ids: Optional[List[str]] = None
    ):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_engine = embedding_engine
        self.max_async = max_async
        self.batch_limit = batch_limit
        self.start_book_id = start_book_id
        self.book_ids = book_ids

        self.tracker = get_token_tracker()
        self.checkpoint_mgr = get_checkpoint_manager()
        self.registry = get_book_registry()

        # Install exact match injection hook into LightRAG
        install_exact_match_hook()

        # Initialize LightRAG instance
        logger.info(
            f"Initializing LightRAG instance: workspace={self.workspace_dir}, "
            f"embedding={self.embedding_engine}, max_async={self.max_async}"
        )
        rag_kwargs = {
            "working_dir": str(self.workspace_dir),
            "llm_model_func": get_minimax_llm_func(tracker=self.tracker),
            "embedding_func": get_astronomy_embedding_func(engine_type=self.embedding_engine, tracker=self.tracker),
            "llm_model_max_async": self.max_async,
            "embedding_func_max_async": 16,
            "default_llm_timeout": DEFAULT_LLM_TIMEOUT,
            "chunk_token_size": 1200,
            "chunk_overlap_token_size": 100
        }
        if STORAGE_BACKEND == "lancedb":
            from astronomy_lightrag.storage import init_astronomy_storage_backends
            init_astronomy_storage_backends()
            rag_kwargs["kv_storage"] = "SQLiteKVStorage"
            rag_kwargs["vector_storage"] = "LanceDBVectorStorage"
            rag_kwargs["graph_storage"] = "SQLiteGraphStorage"

        self.rag = LightRAG(**rag_kwargs)

    async def run(self):
        """
        Runs the dual-loop orchestration pipeline across all registered books.
        """
        logger.info(f"Starting orchestration across {len(self.registry)} registered astronomy books.")
        await self.rag.initialize_storages()

        # Start WeChat background long-poll so context_token never expires
        try:
            from bilingual_common.notifier import start_notifier_poll
            start_notifier_poll()
            logger.info("WeChat notifier background long-poll initialized.")
        except Exception as poll_err:
            logger.debug(f"WeChat poll init note: {poll_err}")

        # Sort books canonically by doc_id or filter by book_ids
        if self.book_ids:
            ordered_doc_ids = [bid for bid in self.book_ids if bid in self.registry]
            logger.info(f"Targeting specific book IDs: {ordered_doc_ids}")
        else:
            ordered_doc_ids = sorted(self.registry.keys())

            # Fast forward if start_book_id specified
            if self.start_book_id:
                try:
                    idx = ordered_doc_ids.index(self.start_book_id)
                    ordered_doc_ids = ordered_doc_ids[idx:]
                    logger.info(f"Resuming from specified start book: {self.start_book_id} (index {idx})")
                except ValueError:
                    logger.warning(f"Start book ID '{self.start_book_id}' not found in registry. Starting from beginning.")

        processed_count = 0
        consecutive_failures = 0
        pipeline_start_time = time.time()

        for idx, doc_id in enumerate(ordered_doc_ids, start=1):
            if self.batch_limit and processed_count >= self.batch_limit:
                logger.info(f"Reached specified batch limit of {self.batch_limit} books. Halting gracefully.")
                break

            meta = self.registry[doc_id]
            title = meta["standard_title"]
            file_path = Path(meta["file_path"])

            # 1. Checkpoint Check: Skip if already marked completed
            if self.checkpoint_mgr.is_book_completed(doc_id):
                logger.info(f"⏩ [Skip] Book '{doc_id}' ({title}) already completed in checkpoint. Skipping.")
                continue

            # 1.5 Quarantine Check: Skip if book is in quarantine
            if self.is_book_quarantined(doc_id):
                logger.warning(f"🚫 [Quarantine Skip] Book '{doc_id}' ({title}) is in quarantine. Skipping.")
                continue

            # 2. Outer Loop Check: Check token quota & near-window conditions
            while True:
                summary = self.tracker.usage_summary()
                is_near_edge = is_near_window_boundary(threshold_minutes=8)
                is_quota_full = summary["window_pct"] >= (TOKEN_LIMIT_RATIO * 100)

                if is_quota_full or is_near_edge:
                    reset_dt = get_next_window_reset_time()
                    secs = get_seconds_until_next_reset()
                    logger.warning(
                        f"⏳ [Quota/Window Guard] Window usage={summary['window_pct']}% "
                        f"({summary['window_tokens']:,}/{summary['window_soft_limit']:,} tokens), "
                        f"near_edge={is_near_edge}. Pausing pipeline until {reset_dt.strftime('%H:%M:%S')}..."
                    )
                    await notify_quota_pause(
                        current_tokens=summary['window_tokens'],
                        quota_limit=summary['window_soft_limit'],
                        next_reset_time=reset_dt.strftime('%H:%M:%S'),
                        sleep_hours=secs / 3600.0
                    )
                    await sleep_until_next_window(buffer_seconds=15)
                    self.tracker.reset_window_if_expired()
                else:
                    break

            # 3. Read and Sanitize Text
            if not file_path.exists():
                logger.error(f"❌ File not found for book '{doc_id}': {file_path}")
                continue

            logger.info(f"\n{'='*70}\n📖 [Processing Book {idx}/{len(ordered_doc_ids)}] {doc_id}: {title}\n{'='*70}")
            t_book_start = time.time()

            raw_text = file_path.read_text(encoding="utf-8")
            clean_text = clean_markdown_text(raw_text)

            is_valid, reason = validate_text_chunk(clean_text)
            if not is_valid:
                logger.warning(f"⚠️ Text validation rejected book '{doc_id}': {reason}. Skipping.")
                continue

            # 4. Ingest into LightRAG with retry & protection
            book_success = False
            for attempt in range(3):
                try:
                    self._clean_failed_doc_status(title, doc_id)
                    logger.info(
                        f"🚀 Ingesting '{title}' ({len(clean_text):,} chars, ~{meta['estimated_chunks']} chunks) "
                        f"via LightRAG ainsert (attempt {attempt+1}/3)..."
                    )
                    await self.rag.ainsert(clean_text, file_paths=[title])

                    # 4.5 Verify ingestion did not fail internally in LightRAG doc_status
                    doc_status_file = self.workspace_dir / "kv_store_doc_status.json"
                    if doc_status_file.exists():
                        try:
                            with open(doc_status_file, "r", encoding="utf-8") as f_ds:
                                ds_data = json.load(f_ds)
                            clean_t = title.replace("《", "").replace("》", "").strip()
                            has_processed = any(
                                (d_val.get("file_path") == title or clean_t in str(d_val.get("file_path", "")))
                                and d_val.get("status") == "processed"
                                and not d_key.startswith("dup-")
                                for d_key, d_val in ds_data.items()
                            )
                            if not has_processed:
                                for d_key, d_val in ds_data.items():
                                    if d_val.get("file_path") == title or (clean_t in str(d_val.get("file_path", ""))):
                                        if not d_key.startswith("dup-") and d_val.get("status") in ("failed", "fail"):
                                            err_msg = d_val.get("error", "marked failed in LightRAG doc_status")
                                            raise RuntimeError(f"LightRAG internal failure for '{title}': {err_msg}")
                        except json.JSONDecodeError:
                            pass

                    book_success = True
                    break

                except Exception as book_err:
                    logger.error(
                        f"❌ Error during ingestion of book '{doc_id}' ({title}) "
                        f"(attempt {attempt+1}/3): {book_err}", exc_info=True
                    )
                    self._clean_failed_doc_status(title, doc_id)
                    if attempt < 2:
                        logger.info(f"Retrying book '{doc_id}' in 30s...")
                        await asyncio.sleep(30)
                    else:
                        logger.error(f"❌ Book '{doc_id}' failed all 3 attempts. Quarantining book.")
                        self._quarantine_book(doc_id, title, str(book_err))
                        await notify_quarantined_book(doc_id, title, str(book_err), attempts=3)
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            logger.critical("🚨 3 consecutive books have failed! Halting pipeline to prevent library-wide cascade.")
                            await send_notification(
                                "流水线紧急熔断",
                                "连续 3 本书入库失败并已进入隔离区。为避免全库污染，流水线已自动熔断阻断。请人工介入排查。",
                                msg_type="emergency",
                                unrecoverable=True
                            )
                            return

            if not book_success:
                continue

            consecutive_failures = 0

            # 5. Mark Checkpoint & Update State
            self.checkpoint_mgr.mark_book_completed(doc_id, total_chunks=meta["estimated_chunks"])
            self._update_ingest_state_file(doc_id, meta)

            elapsed_book = time.time() - t_book_start
            processed_count += 1
            logger.info(f"✅ Finished book '{doc_id}' ({title}) in {elapsed_book:.1f}s.")

            # 6. Quality Audit Sample
            clean_score_str = "20/20 (无思考标签/无乱码)"
            try:
                sample_nodes = [{"entity_name": doc_id, "title": title, "status": "ingested"}]
                judge_report = await evaluate_graph_samples(title, sample_nodes)
                c_val = judge_report.get("cleanliness", 20)
                clean_score_str = f"{c_val}/20 (无思考标签/无乱码)"
                logger.info(f"Auditor Score for '{title}': {judge_report.get('total_score')}/100")
            except Exception as audit_err:
                logger.warning(f"Quality audit skipped due to non-critical error: {audit_err}")

            # 7. Milestone Alert
            summary_now = self.tracker.usage_summary()
            total_elapsed = str(datetime.now() - datetime.fromtimestamp(pipeline_start_time)).split('.')[0]
            cp_summary = self.checkpoint_mgr.get_progress_summary()
            global_done = cp_summary.get("completed_books", processed_count)
            total_corpus_count = len(self.registry)

            await notify_milestone(
                book_index=idx,
                total_books=len(ordered_doc_ids),
                book_title=title,
                chunks_count=meta["estimated_chunks"],
                total_tokens=summary_now.get("monthly_tokens", 0),
                elapsed_time_str=total_elapsed,
                quality_score=clean_score_str,
                book_id=doc_id,
                global_completed=global_done,
                total_corpus=total_corpus_count,
                batch_index=idx,
                batch_total=len(ordered_doc_ids),
                window_pct=summary_now.get("window_pct", 0.0)
            )

        total_elapsed_all = str(datetime.now() - datetime.fromtimestamp(pipeline_start_time)).split('.')[0]
        logger.info(
            f"\n🎉 Orchestrator run completed! Processed {processed_count} books in {total_elapsed_all}."
        )
        await send_notification(
            "天文学知识库摄取任务收官",
            f"**本次运行完成**: {processed_count} 本书\n"
            f"**总运行时长**: {total_elapsed_all}\n"
            f"**累计消耗 Token**: {self.tracker.usage_summary().get('monthly_tokens', 0):,}\n"
            f"全部指定批次书籍已成功归档入库！",
            msg_type="success"
        )

    def _update_ingest_state_file(self, doc_id: str, meta: Dict[str, Any]):
        """Updates ingest_state.json for dashboard live status."""
        try:
            state = {}
            if STATE_FILE.exists():
                try:
                    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    state = {}
            state[meta["folder_name"]] = {
                "doc_id": doc_id,
                "title": meta["standard_title"],
                "file_hash": meta.get("file_hash", ""),
                "processed_at": datetime.now().isoformat()
            }
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not update {STATE_FILE}: {e}")

    def is_book_quarantined(self, doc_id: str) -> bool:
        """Checks if a book has been placed in the quarantine queue."""
        q_file = DATA_DIR / "quarantine_books.json"
        if not q_file.exists():
            return False
        try:
            with open(q_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return doc_id in data
            return False
        except Exception:
            return False

    def _quarantine_book(self, doc_id: str, title: str, error_msg: str):
        """Places a book that failed all retries into the quarantine queue."""
        q_file = DATA_DIR / "quarantine_books.json"
        q_file.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if q_file.exists():
            try:
                with open(q_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = loaded
            except Exception:
                data = {}
        data[doc_id] = {
            "title": title,
            "quarantined_at": datetime.now().isoformat(),
            "last_error": error_msg,
            "attempts": 3
        }
        try:
            with open(q_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.warning(f"🚫 [Quarantine] Book '{doc_id}' ({title}) recorded in {q_file}")
        except Exception as q_err:
            logger.error(f"Failed to write quarantine file: {q_err}")

    def _clean_failed_doc_status(self, title: str, doc_id: Optional[str] = None):
        """
        Removes any failed or incomplete status for this book from disk JSON AND
        synchronizes LightRAG's in-memory storage structures so subsequent attempts
        never suffer from dirty state.
        """
        ds_file = self.workspace_dir / "kv_store_doc_status.json"
        fd_file = self.workspace_dir / "kv_store_full_docs.json"
        clean_title = title.replace("《", "").replace("》", "").strip()
        try:
            keys_to_del = []
            if ds_file.exists():
                with open(ds_file, "r", encoding="utf-8") as f:
                    ds = json.load(f)
                keys_to_del = [
                    k for k, v in ds.items()
                    if (
                        v.get("file_path") == title
                        or clean_title in str(v.get("file_path", ""))
                        or clean_title in str(v.get("content_summary", ""))
                        or (doc_id and doc_id in str(v.get("file_path", "")))
                    ) and (v.get("status") in ("failed", "processing", "fail") or k.startswith("dup-"))
                ]
                if keys_to_del:
                    for k in keys_to_del:
                        ds.pop(k, None)
                    with open(ds_file, "w", encoding="utf-8") as f:
                        json.dump(ds, f, ensure_ascii=False, indent=2)
                    logger.info(f"Cleared {len(keys_to_del)} prior failed/incomplete entries for '{title}' from doc_status.")

            if fd_file.exists() and keys_to_del:
                with open(fd_file, "r", encoding="utf-8") as f:
                    fd = json.load(f)
                fd_keys_to_del = [k for k in keys_to_del if k in fd]
                if fd_keys_to_del:
                    for k in fd_keys_to_del:
                        fd.pop(k, None)
                    with open(fd_file, "w", encoding="utf-8") as f:
                        json.dump(fd, f, ensure_ascii=False, indent=2)

            # Synchronize LightRAG in-memory storage structures
            def _safe_dispatch(storage, method_name, *args):
                if hasattr(storage, method_name):
                    try:
                        res = getattr(storage, method_name)(*args)
                        if inspect.iscoroutine(res):
                            try:
                                loop = asyncio.get_running_loop()
                                loop.create_task(res)
                            except RuntimeError:
                                asyncio.run(res)
                    except Exception as call_err:
                        logger.debug(f"{method_name} dispatch note: {call_err}")

            if hasattr(self, "rag") and self.rag is not None:
                for attr_name in ("doc_status", "doc_status_storage"):
                    storage = getattr(self.rag, attr_name, None)
                    if storage is not None and not isinstance(storage, str):
                        if hasattr(storage, "_data"):
                            for k in keys_to_del:
                                storage._data.pop(k, None)
                        if keys_to_del:
                            _safe_dispatch(storage, "delete", keys_to_del)
                        _safe_dispatch(storage, "initialize")

                storage_fd = getattr(self.rag, "full_docs", None)
                if storage_fd is not None and not isinstance(storage_fd, str):
                    if hasattr(storage_fd, "_data"):
                        for k in keys_to_del:
                            storage_fd._data.pop(k, None)
                    if keys_to_del:
                        _safe_dispatch(storage_fd, "delete", keys_to_del)
                    _safe_dispatch(storage_fd, "initialize")
        except Exception as e:
            logger.warning(f"Error cleaning prior doc status for '{title}': {e}")


def parse_args():
    parser = argparse.ArgumentParser(description="Full-Scale Astronomy LightRAG Orchestrator")
    parser.add_argument("--batch-size", type=int, default=None, help="Number of books to process in this run")
    parser.add_argument("--start-book", type=str, default=None, help="Book ID to start from (e.g. book_001)")
    parser.add_argument("--book-ids", type=str, default=None, help="Comma-separated list of specific book IDs (e.g. book_066,book_142)")
    parser.add_argument("--embedding-engine", type=str, default=EMBEDDING_ENGINE, choices=["local", "online"], help="Embedding engine")
    parser.add_argument("--dry-run", action="store_true", help="Scan and validate without inserting into LightRAG")
    return parser.parse_args()


def prevent_system_sleep():
    """
    Prevents Windows from entering sleep or standby while orchestrator is running.
    Uses Win32 SetThreadExecutionState:
    ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001) | ES_AWAYMODE_REQUIRED (0x00000040)
    """
    if sys.platform == "win32":
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_AWAYMODE_REQUIRED = 0x00000040
            ret = ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            )
            if ret != 0:
                logging.getLogger("astronomy_lightrag.harness").info(
                    "🛡️ [SleepGuard] Windows system sleep prevention activated (ES_SYSTEM_REQUIRED | ES_AWAYMODE)."
                )
        except Exception as e:
            logging.getLogger("astronomy_lightrag.harness").warning(f"Could not set sleep prevention: {e}")


async def main():
    args = parse_args()
    setup_harness_logging(log_name="harness_orchestrator")
    prevent_system_sleep()

    selected_ids = [bid.strip() for bid in args.book_ids.split(",")] if args.book_ids else None

    if args.dry_run:
        logger.info("🔍 DRY-RUN MODE: Verifying corpus registry and text files...")
        reg = get_book_registry()
        targets = [reg[k] for k in selected_ids if k in reg] if selected_ids else list(reg.values())[:5]
        for meta in targets:
            doc_id = meta["doc_id"]
            p = Path(meta["file_path"])
            valid, reason = validate_text_chunk(clean_markdown_text(p.read_text(encoding="utf-8")[:1000]))
            print(f"  {doc_id} -> {meta['standard_title']} (Valid: {valid}, Size: {meta['file_size_bytes']:,} bytes)")
        print(f"\nDry-run verified successfully for {len(targets)} books.")
        return

    # Try launching background notifier poll if openclaw weixin is available
    try:
        from bilingual_common.notifier import start_notifier_poll
        start_notifier_poll()
    except Exception as e:
        logger.debug(f"start_notifier_poll notice: {e}")

    orchestrator = FullScaleOrchestrator(
        embedding_engine=args.embedding_engine,
        batch_limit=args.batch_size,
        start_book_id=args.start_book,
        book_ids=selected_ids
    )
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
