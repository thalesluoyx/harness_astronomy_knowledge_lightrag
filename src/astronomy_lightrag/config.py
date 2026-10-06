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
LIGHTRAG_WORKSPACE = PROJECT_ROOT / "lightrag_workspace"
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
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("LLM_MODEL_NAME", "MiniMax-M3")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "embo-01")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

# Token Plan & Rate Limiting Configuration
# MiniMax 5h window: default upgraded to 5.4M tokens based on real measurement (64% = 3.45M)
TOKEN_QUOTA_PER_WINDOW = int(os.getenv("TOKEN_QUOTA_PER_WINDOW", "5400000"))
TOKEN_LIMIT_RATIO = float(os.getenv("TOKEN_LIMIT_RATIO", "0.90"))

# LightRAG execution timeout (default 5 hours to prevent premature worker timeout during rate limit pauses)
DEFAULT_LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "18000"))

