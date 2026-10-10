import os
import sys
import logging
from datetime import datetime
from pathlib import Path
import asyncio

# Add src to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from astronomy_lightrag.config import (
    BILINGUAL_OUTPUT_DIR,
    LIGHTRAG_WORKSPACE,
    LOGS_DIR,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    STATE_FILE,
    TARGET_BOOKS,
    DEFAULT_LLM_TIMEOUT,
)
from astronomy_lightrag.token_tracker import get_token_tracker
from astronomy_lightrag.llm import get_minimax_llm_func, get_minimax_embedding_func
from astronomy_lightrag.ingestor import run_ingestion_pipeline


def setup_logging():
    """
    Configures unified logging to both console and logs/lightrag_ingest_*.log.
    Directs LightRAG's internal logger and subloggers to the file so no progress or errors are missed.
    """
    log_dir = LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"lightrag_ingest_{timestamp}.log"


    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # File Handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [console_handler, file_handler]

    # Explicitly wire up LightRAG and sub-loggers to file_handler
    for name in ["lightrag", "nano-vectordb", "astronomy_lightrag"]:
        l = logging.getLogger(name)
        l.setLevel(logging.INFO)
        l.propagate = True
        if file_handler not in l.handlers:
            l.addHandler(file_handler)

    # LightRAG built-in setup_logger hook
    try:
        from lightrag.utils import setup_logger
        setup_logger("lightrag", level="INFO", log_file_path=str(log_file))
    except Exception as e:
        root_logger.warning(f"LightRAG setup_logger fallback: {e}")

    # Suppress raw low-level HTTP transport spam
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.info(f"Unified logging initialized. Output log file: {log_file}")
    return log_file

async def async_main():
    log_file = setup_logging()
    logger = logging.getLogger("run_ingestion")

    logger.info("Verifying configuration...")
    if not LLM_API_KEY:
        logger.error("LLM_API_KEY is not configured! Please check your .env file.")
        sys.exit(1)

    tracker = get_token_tracker()
    summary = tracker.usage_summary()

    logger.info(f"Target LLM: {LLM_MODEL} via {LLM_BASE_URL}")
    logger.info(f"LightRAG Workspace: {LIGHTRAG_WORKSPACE}")
    logger.info(f"State File: {STATE_FILE}")
    logger.info(
        f"Token Plan Status: 5h Window Usage: {summary['window_pct']}% "
        f"({summary['window_tokens']:,}/{summary['window_soft_limit']:,} limit: {tracker.limit_ratio*100:.0f}%) | "
        f"Next Reset: {summary['resume_time']}"
    )

    LIGHTRAG_WORKSPACE.mkdir(parents=True, exist_ok=True)

    # Initialize LightRAG components
    try:
        from lightrag import LightRAG
    except ImportError:
        logger.error("lightrag-hku is not installed. Please run: pip install -r requirements.txt")
        sys.exit(1)

    logger.info("Initializing MiniMax LLM and Embedding functions with TokenTracker...")
    llm_func = get_minimax_llm_func(tracker=tracker)
    embedding_func = get_minimax_embedding_func(tracker=tracker)

    os.environ["LLM_TIMEOUT"] = str(DEFAULT_LLM_TIMEOUT)
    logger.info(f"Instantiating LightRAG (default_llm_timeout={DEFAULT_LLM_TIMEOUT}s)...")
    rag = LightRAG(
        working_dir=str(LIGHTRAG_WORKSPACE),
        llm_model_func=llm_func,
        embedding_func=embedding_func,
        default_llm_timeout=DEFAULT_LLM_TIMEOUT
    )

    logger.info("Initializing LightRAG storages...")
    await rag.initialize_storages()
    logger.info("LightRAG storages initialized successfully.")

    # Execute ingestion pipeline
    await run_ingestion_pipeline(
        rag_instance=rag,
        base_dir=BILINGUAL_OUTPUT_DIR,
        state_file=STATE_FILE,
        target_books=TARGET_BOOKS,
        tracker=tracker
    )

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    asyncio.run(async_main())
    logging.info("Run ingestion completed. Process exiting cleanly.")
    sys.exit(0)

if __name__ == "__main__":
    main()

