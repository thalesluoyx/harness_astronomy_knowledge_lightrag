"""
logger_setup.py
Centralized logging configuration for the astronomy LightRAG harness.

Enforces project rules:
1. All logs output to bilingual_output directory (e.g. bilingual_output/harness_orchestrator.log).
2. Suppresses raw progress bar spam (%|) from file logs while preserving all textual logs.
3. Supports dual logging to Console (stdout) and File.
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

# Directory setup
CURRENT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = CURRENT_DIR.parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent
LOGS_DIR = PROJECT_ROOT / "logs"


class TqdmFilter(logging.Filter):
    """Filters out raw progress bar spam (%|) from file logs."""
    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        if "%|" in msg or "|/" in msg or "it/s" in msg and len(msg) < 80:
            return False
        return True


def setup_harness_logging(
    log_name: str = "harness_orchestrator",
    output_dir: Path = LOGS_DIR,
    level: int = logging.INFO
) -> logging.Logger:
    """
    Sets up a configured logger that streams to console and writes to harness_astronomy_knowledge_lightrag/logs/.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y%m%d")
    log_file = output_dir / f"{log_name}_{today_str}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Formatters
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # Ensure console handles UTF-8 on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # File Handler
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(TqdmFilter())

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    # Avoid adding duplicate handlers if already attached
    existing_file_handlers = [
        h for h in root_logger.handlers
        if isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == str(log_file)
    ]
    if not existing_file_handlers:
        root_logger.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        root_logger.addHandler(console_handler)

    logger = logging.getLogger("astronomy_lightrag.harness")
    logger.info(f"Harness logging initialized. Writing logs to: {log_file}")
    return logger
