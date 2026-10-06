import json
import hashlib
import logging
from pathlib import Path
from typing import List, Set, Any, Optional
from datetime import datetime
from lightrag.lightrag import DocStatus

from .config import BILINGUAL_OUTPUT_DIR, STATE_FILE, TARGET_BOOKS
from .token_tracker import TokenTracker, get_token_tracker

logger = logging.getLogger("astronomy_lightrag.ingestor")


def get_file_hash(filepath: Path) -> str:
    """Computes MD5 hash of file contents for change detection."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_state(state_file: Path = STATE_FILE) -> Set[str]:
    """Loads the set of processed file identifiers from the state file."""
    if not state_file.exists():
        return set()
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.keys())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"State file {state_file} read error ({e}). Returning empty state.")
        return set()

def save_state(filepath_key: str, file_hash: str, state_file: Path = STATE_FILE):
    """Saves a successfully verified processed file record to the state file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state = {}
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception:
            state = {}

    state[filepath_key] = {
        "hash": file_hash,
        "processed_at": datetime.now().isoformat()
    }

    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def discover_files(
    base_dir: Path = BILINGUAL_OUTPUT_DIR,
    target_books: List[str] = TARGET_BOOKS
) -> List[Path]:
    """
    Discovers all *_bilingual.md files inside the specified target book folders,
    searching recursively into subdirectories (e.g. auto/).
    """
    files_to_process = []
    if not base_dir.exists():
        logger.error(f"Base corpus directory does not exist: {base_dir}")
        return files_to_process

    for book_folder_name in target_books:
        book_dir = base_dir / book_folder_name
        if not book_dir.exists():
            logger.warning(f"Target book directory not found: {book_dir}")
            continue

        matches = sorted(list(book_dir.rglob("*_bilingual.md")))
        if not matches:
            logger.warning(f"No *_bilingual.md found inside: {book_dir}")
        else:
            files_to_process.extend(matches)

    return sorted(files_to_process)

async def run_ingestion_pipeline(
    rag_instance: Any,
    base_dir: Path = BILINGUAL_OUTPUT_DIR,
    state_file: Path = STATE_FILE,
    target_books: List[str] = TARGET_BOOKS,
    tracker: Optional[TokenTracker] = None
):
    """
    Runs the incremental knowledge base ingestion with strict verification:
    1. Cleans up any prior failed doc status entries to allow clean retry.
    2. Discovers files within target scope.
    3. Filters out verified processed files.
    4. Reads raw bilingual markdown and inserts into LightRAG.
    5. Verifies document processing status in LightRAG doc_status storage.
    6. Updates state file ONLY when the document is truly PROCESSED.
    """
    if tracker is None:
        tracker = get_token_tracker()

    logger.info("=" * 65)
    logger.info("Starting Astronomy Knowledge Base Ingestion Pipeline (LightRAG)")
    logger.info("=" * 65)

    # 1. Clean up any stale failed document entries in LightRAG storage to enable retry
    try:
        if hasattr(rag_instance, "doc_status") and hasattr(rag_instance.doc_status, "get_docs_by_statuses"):
            failed_docs = await rag_instance.doc_status.get_docs_by_statuses([DocStatus.FAILED])
            if failed_docs:
                failed_keys = list(failed_docs.keys())
                logger.info(f"🧹 Found {len(failed_keys)} failed documents in LightRAG storage. Cleaning up to enable retry...")
                await rag_instance.doc_status.delete(failed_keys)
    except Exception as cleanup_err:
        logger.warning(f"Notice on doc_status cleanup: {cleanup_err}")

    processed_keys = load_state(state_file)
    files_to_process = discover_files(base_dir, target_books)

    logger.info(f"Target books configured: {len(target_books)}")
    logger.info(f"Total matching files discovered: {len(files_to_process)}")
    logger.info(f"Verified processed files in state: {len(processed_keys)}")

    if not files_to_process:
        logger.warning("No files found to process. Exiting pipeline.")
        return

    for idx, filepath in enumerate(files_to_process, 1):
        rel_key = filepath.name
        try:
            rel_key = str(filepath.relative_to(base_dir))
        except ValueError:
            rel_key = filepath.name

        if rel_key in processed_keys:
            logger.info(f"[{idx}/{len(files_to_process)}] ⏭️ SKIPPED (already verified in state): {rel_key}")
            continue

        # Check token quota before starting a new book
        if tracker:
            await tracker.wait_if_limit_reached()
            tok_summary = tracker.usage_summary()
            logger.info(
                f"📊 [Token Status] Pre-ingestion for book [{idx}/{len(files_to_process)}]: "
                f"5h window usage: {tok_summary['window_pct']:.1f}% "
                f"({tok_summary['window_tokens']:,}/{tok_summary['window_quota']:,} tokens)"
            )

        file_size_kb = filepath.stat().st_size / 1024
        logger.info("-" * 65)
        logger.info(f"[{idx}/{len(files_to_process)}] 📖 INGESTING ({file_size_kb:.1f} KB): {rel_key}")
        logger.info("-" * 65)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()


            logger.info(f"Calling LightRAG ainsert() for {rel_key} ({len(content):,} chars)...")
            track_id = await rag_instance.ainsert(content)
            logger.info(f"LightRAG ainsert() finished with track_id: {track_id}. Verifying completion status...")

            # Verify document completion status in LightRAG
            docs_status = await rag_instance.aget_docs_by_track_id(track_id)
            if not docs_status:
                logger.warning(f"No document status records returned for track_id: {track_id}")
                continue

            all_succeeded = True
            for doc_id, doc_info in docs_status.items():
                status_val = getattr(doc_info, "status", None)
                chunks_count = getattr(doc_info, "chunks_count", 0)
                logger.info(f"Doc {doc_id[:16]}...: Status = {status_val}, Chunks = {chunks_count}")

                if status_val != DocStatus.PROCESSED and status_val != "processed":
                    all_succeeded = False
                    logger.error(
                        f"❌ Document {doc_id} failed with status: {status_val}. "
                        f"Will not mark {rel_key} as completed in state."
                    )

            if all_succeeded:
                file_hash = get_file_hash(filepath)
                save_state(rel_key, file_hash, state_file)
                logger.info(f"🎉 SUCCESS: {rel_key} fully PROCESSED in LightRAG and saved to state.")
            else:
                logger.warning(f"⚠️ {rel_key} had failed chunks/documents. State NOT updated for retry.")

        except Exception as e:
            logger.error(f"❌ ERROR: Ingestion failed for {rel_key}: {e}", exc_info=True)
            continue

    logger.info("=" * 65)
    logger.info("Ingestion Pipeline Run Completed.")
    logger.info("=" * 65)
