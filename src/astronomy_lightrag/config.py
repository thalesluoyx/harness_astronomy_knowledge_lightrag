import os
from pathlib import Path
from dotenv import load_dotenv

# Project Root (harness_astronomy_knowledge_lightrag)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env")

# Workspace and storage paths
WORKSPACE_ROOT = PROJECT_ROOT.parent
BILINGUAL_OUTPUT_DIR = WORKSPACE_ROOT / "bilingual_output"
DATA_DIR = PROJECT_ROOT / "data"
STATE_FILE = DATA_DIR / "ingest_state.json"
# Storage Backend: "lancedb" (modern zero-copy mmap, < 1GB RAM) or "json" (legacy plain text)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "lancedb").lower()
LIGHTRAG_WORKSPACE_JSON = PROJECT_ROOT / "lightrag_workspace"
LIGHTRAG_WORKSPACE_LANCEDB = PROJECT_ROOT / "lightrag_workspace_lancedb"

if STORAGE_BACKEND == "lancedb":
    LIGHTRAG_WORKSPACE = LIGHTRAG_WORKSPACE_LANCEDB
else:
    LIGHTRAG_WORKSPACE = LIGHTRAG_WORKSPACE_JSON

LOGS_DIR = PROJECT_ROOT / "logs"


# Corpus Scope - The targeted "The Deep Sky Companions" series
TARGET_BOOKS = [
    "book_Hidden Treasures (2007)",
    "book_Southern Gems (2013)",
    "book_The Caldwell Objects (2003)",
    "book_The Messier Objects (1998)",
    "book_The Secret Deep (2011)"
]

# LLM Configuration (supports both LLM_* and OPENAI_* naming)
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("LLM_MODEL_NAME", "MiniMax-M3.1-Flash")
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")

# Embedding Configuration: "local" (default, 0 API cost, 500+ chunks/sec) or "online" (MiniMax embo-01)
EMBEDDING_ENGINE = os.getenv("EMBEDDING_ENGINE", "local").lower()
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
LOCAL_EMBEDDING_BACKEND = os.getenv("LOCAL_EMBEDDING_BACKEND", "fastembed")
LOCAL_EMBEDDING_THREADS = int(os.getenv("LOCAL_EMBEDDING_THREADS", "8"))

if EMBEDDING_ENGINE == "local":
    EMBEDDING_MODEL = LOCAL_EMBEDDING_MODEL
    # BAAI/bge-small-zh-v1.5 dimension is 512
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "512"))
else:
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "embo-01")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

# Concurrency: Stage 1 extraction concurrency (calibrated to 4 for Flash high-throughput RPM safety)
MAX_ASYNC = int(os.getenv("MAX_ASYNC", "4"))

# Token Plan & Rate Limiting Configuration
# MiniMax 5h window: calibrated to 7.0M tokens for Flash (soft limit 90% = 6.30M)
TOKEN_QUOTA_PER_WINDOW = int(os.getenv("TOKEN_QUOTA_PER_WINDOW", "7000000"))
TOKEN_LIMIT_RATIO = float(os.getenv("TOKEN_LIMIT_RATIO", "0.90"))

# LightRAG execution timeout (default 5 hours to prevent premature worker timeout during rate limit pauses)
DEFAULT_LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "18000"))

