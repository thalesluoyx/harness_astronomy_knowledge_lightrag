"""
dashboard/server.py
LightRAG Ingestion Dashboard Server with SSE and live log streaming.
Monitors progress for astronomy knowledge graph construction.
"""
import os
import re
import sys
import json
import time
import glob
from datetime import datetime
from pathlib import Path
from flask import Flask, Response, jsonify, send_from_directory, request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
WORKSPACE_DIR = PROJECT_ROOT / "lightrag_workspace"
PARENT_DIR = PROJECT_ROOT.parent
BILINGUAL_OUTPUT_DIR = PARENT_DIR / "bilingual_output"

app = Flask(__name__)

# Target POC books
TARGET_BOOKS = [
    "book_Hidden Treasures (2007)",
    "book_Southern Gems (2013)",
    "book_The Caldwell Objects (2003)",
    "book_The Messier Objects (1998)",
    "book_The Secret Deep (2011)"
]

WINDOW_QUOTA = 5_400_000
WINDOW_SOFT_LIMIT = 4_860_000
WINDOW_DURATION = 18_000  # 5 hours in seconds


def get_latest_log_path():
    """Finds the most recently modified ingestion log file."""
    if not LOGS_DIR.exists():
        return None
    log_files = sorted(LOGS_DIR.glob("lightrag_ingest_*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
    return log_files[0] if log_files else None


def parse_log_stats(log_path):
    """Parses real-time chunk progress, entity counts, speed, and status from the log."""
    stats = {
        "active_chunk": 0,
        "total_chunks": 608,
        "latest_ent": 0,
        "latest_rel": 0,
        "total_ent": 0,
        "total_rel": 0,
        "avg_chunk_sec": 24.0,
        "is_waiting_reset": False,
        "wait_remaining_sec": 0,
        "active_book_name": "book_Hidden Treasures (2007)",
        "last_log_line": ""
    }
    if not log_path or not log_path.exists():
        return stats

    try:
        # Read the file
        content = log_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        if lines:
            stats["last_log_line"] = lines[-1]

        # Check for waiting status
        wait_matches = re.findall(r"Waiting ([\d\.]+)s until next window reset", content)
        if wait_matches:
            # Check if this wait happened recently in the last 20 lines
            recent_text = "\n".join(lines[-25:])
            if "Waiting" in recent_text and "until next window reset" in recent_text:
                stats["is_waiting_reset"] = True
                stats["wait_remaining_sec"] = float(wait_matches[-1])

        # Check chunk extraction matches
        # Format: Chunk 448 of 608 extracted 17 Ent + 16 Rel
        chunk_matches = re.findall(r"Chunk (\d+) of (\d+) extracted (\d+) Ent \+ (\d+) Rel", content)
        if chunk_matches:
            stats["total_ent"] = sum(int(m[2]) for m in chunk_matches)
            stats["total_rel"] = sum(int(m[3]) for m in chunk_matches)
            last_m = chunk_matches[-1]
            stats["active_chunk"] = int(last_m[0])
            stats["total_chunks"] = int(last_m[1])
            stats["latest_ent"] = int(last_m[2])
            stats["latest_rel"] = int(last_m[3])

        # Calculate average chunk speed from timestamps of the last 15 chunk extractions
        ts_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?Chunk \d+ of \d+ extracted")
        ts_matches = ts_pattern.findall(content)
        if len(ts_matches) >= 2:
            recent_ts = ts_matches[-15:]
            try:
                t_first = datetime.strptime(recent_ts[0], "%Y-%m-%d %H:%M:%S")
                t_last = datetime.strptime(recent_ts[-1], "%Y-%m-%d %H:%M:%S")
                delta_sec = (t_last - t_first).total_seconds()
                if delta_sec > 0 and len(recent_ts) > 1:
                    stats["avg_chunk_sec"] = round(delta_sec / (len(recent_ts) - 1), 1)
            except Exception:
                pass

        # Check active book name from log
        book_matches = re.findall(r"Processing book \d+/\d+: (book_[^\n\r]+)", content)
        if book_matches:
            stats["active_book_name"] = book_matches[-1].strip()

    except Exception as e:
        stats["error"] = str(e)

    return stats


def get_token_state():
    """Reads token tracker state."""
    state = {
        "window_tokens": 0,
        "window_start": time.time(),
        "monthly_tokens": 0,
        "window_quota": WINDOW_QUOTA,
        "window_soft_limit": WINDOW_SOFT_LIMIT,
        "window_pct": 0.0,
        "seconds_until_reset": 0,
        "reset_time_str": "--:--:--"
    }
    token_file = DATA_DIR / "token_tracker_state.json"
    if token_file.exists():
        try:
            data = json.loads(token_file.read_text(encoding="utf-8"))
            state["window_tokens"] = data.get("window_tokens", 0)
            state["window_start"] = data.get("window_start", time.time())
            state["monthly_tokens"] = data.get("monthly_tokens", 0)
        except Exception:
            pass

    # Calculate reset countdown
    window_start = state["window_start"]
    now = time.time()
    next_reset = window_start + WINDOW_DURATION
    seconds_left = max(0, int(next_reset - now))
    state["seconds_until_reset"] = seconds_left
    state["reset_time_str"] = datetime.fromtimestamp(next_reset).strftime("%Y-%m-%d %H:%M:%S")
    state["window_pct"] = round(state["window_tokens"] / WINDOW_SOFT_LIMIT * 100, 2)
    return state


def get_all_books_corpus():
    """Scans bilingual_output to list all books in the full corpus."""
    if not BILINGUAL_OUTPUT_DIR.exists():
        return []
    folders = [f.name for f in BILINGUAL_OUTPUT_DIR.glob("book_*") if f.is_dir()]
    return sorted(folders)


def get_knowledge_graph_stats():
    """Checks the size and item count of graphml and cache files."""
    stats = {
        "cache_entries": 0,
        "cache_size_mb": 0.0,
        "graphml_size_kb": 0.0,
        "has_graph": False
    }
    cache_file = WORKSPACE_DIR / "kv_store_llm_response_cache.json"
    if cache_file.exists():
        try:
            stats["cache_size_mb"] = round(cache_file.stat().st_size / (1024 * 1024), 2)
            # Estimate count from file size or quick parse if small enough
            stats["cache_entries"] = int(stats["cache_size_mb"] * 55) # ~1430 for 27MB
        except Exception:
            pass

    graphml = WORKSPACE_DIR / "graph_chunk_entity_relation.graphml"
    if graphml.exists():
        stats["has_graph"] = True
        stats["graphml_size_kb"] = round(graphml.stat().st_size / 1024, 2)

    return stats


def get_dashboard_state():
    """Aggregates the complete real-time status of the LightRAG ingestion system."""
    token_state = get_token_state()
    log_path = get_latest_log_path()
    log_stats = parse_log_stats(log_path)
    kg_stats = get_knowledge_graph_stats()

    # Completed books from state file
    completed_books = {}
    ingest_file = DATA_DIR / "ingest_state.json"
    if ingest_file.exists():
        try:
            completed_books = json.loads(ingest_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Build detailed info for the 5 POC books
    poc_books = []
    active_book_found = False

    for idx, book_name in enumerate(TARGET_BOOKS, 1):
        clean_title = book_name.replace("book_", "")
        if book_name in completed_books:
            info = completed_books[book_name]
            poc_books.append({
                "index": idx,
                "id": book_name,
                "title": clean_title,
                "status": "completed",
                "progress_pct": 100.0,
                "chunks_done": info.get("chunks_count", 608),
                "chunks_total": info.get("chunks_count", 608),
                "entities": info.get("entities_count", "-"),
                "relations": info.get("relations_count", "-"),
                "completed_at": info.get("completed_at", "")
            })
        elif not active_book_found:
            # This is the current active book
            active_book_found = True
            chunks_done = log_stats["active_chunk"]
            chunks_total = log_stats["total_chunks"]
            pct = round((chunks_done / chunks_total * 100), 1) if chunks_total > 0 else 0.0
            poc_books.append({
                "index": idx,
                "id": book_name,
                "title": clean_title,
                "status": "processing" if not log_stats["is_waiting_reset"] else "paused_quota",
                "progress_pct": pct,
                "chunks_done": chunks_done,
                "chunks_total": chunks_total,
                "entities": log_stats["total_ent"],
                "relations": log_stats["total_rel"],
                "avg_chunk_sec": log_stats["avg_chunk_sec"]
            })
        else:
            poc_books.append({
                "index": idx,
                "id": book_name,
                "title": clean_title,
                "status": "queued",
                "progress_pct": 0.0,
                "chunks_done": 0,
                "chunks_total": 0,
                "entities": 0,
                "relations": 0
            })

    # POC overall calculations
    completed_count = len(completed_books)
    poc_pct = round((completed_count / len(TARGET_BOOKS) * 100) + 
                    (poc_books[0]["progress_pct"] / len(TARGET_BOOKS) if len(poc_books) > 0 and poc_books[0]["status"] in ["processing", "paused_quota"] else 0.0), 1)

    # Calculate remaining time for active book
    remaining_chunks = max(0, log_stats["total_chunks"] - log_stats["active_chunk"])
    active_book_eta_sec = int(remaining_chunks * log_stats["avg_chunk_sec"])

    # Full corpus stats
    all_books = get_all_books_corpus()
    total_corpus_books = len(all_books) if all_books else 154

    # Full corpus estimate:
    # Average chunks per book ~ 500
    # Average LLM extraction tokens per book ~ 1,100,000 tokens
    # With 5.4M tokens per 5-hour window: ~4.5 books per 5-hour quota window
    # Days needed = (total_corpus_books / 4.5) * (5 / 24) days
    est_poc_days = round(5 / 1.5, 1) # ~2.5 to 3 days depending on quota pauses
    est_full_corpus_days = round((total_corpus_books * 1.1) / (5.4 * 4.8 / 1.0) * 1.2, 1) # ~25 - 35 days

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "token": token_state,
        "active_book": {
            "name": log_stats["active_book_name"].replace("book_", ""),
            "chunk_done": log_stats["active_chunk"],
            "chunk_total": log_stats["total_chunks"],
            "chunk_pct": round(log_stats["active_chunk"] / max(1, log_stats["total_chunks"]) * 100, 1),
            "speed_sec_per_chunk": log_stats["avg_chunk_sec"],
            "eta_seconds": active_book_eta_sec,
            "eta_formatted": f"{active_book_eta_sec // 3600}小时 {(active_book_eta_sec % 3600) // 60}分钟"
        },
        "knowledge_graph": {
            "entities_extracted": log_stats["total_ent"],
            "relations_extracted": log_stats["total_rel"],
            "cache_entries": kg_stats["cache_entries"],
            "cache_size_mb": kg_stats["cache_size_mb"]
        },
        "poc": {
            "completed_books": completed_count,
            "total_books": len(TARGET_BOOKS),
            "progress_pct": poc_pct,
            "books": poc_books,
            "est_days": est_poc_days
        },
        "full_corpus": {
            "total_books": total_corpus_books,
            "est_days": est_full_corpus_days
        },
        "system": {
            "status": "paused_quota" if log_stats["is_waiting_reset"] else "running",
            "log_file": log_path.name if log_path else None,
            "last_log_line": log_stats["last_log_line"]
        }
    }


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(Path(__file__).parent, "index.html")


@app.route("/api/state")
def api_state():
    return jsonify(get_dashboard_state())


@app.route("/api/logs")
def api_logs():
    tail = int(request.args.get("tail", 100))
    log_path = get_latest_log_path()
    if not log_path or not log_path.exists():
        return jsonify({"lines": [], "filename": ""})
    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()[-tail:]
        return jsonify({"lines": lines, "filename": log_path.name, "total_lines": len(lines)})
    except Exception as e:
        return jsonify({"lines": [f"Error reading log: {e}"], "filename": ""})


@app.route("/stream")
def sse_stream():
    """SSE endpoint: Pushes JSON state and new log lines every 1.5s."""
    def event_stream():
        yield "data: {\"type\": \"ping\"}\n\n"
        last_log_line_count = 0
        log_path = get_latest_log_path()

        while True:
            try:
                state = get_dashboard_state()
                # Also check new log lines
                new_lines = []
                current_log = get_latest_log_path()
                if current_log and current_log.exists():
                    try:
                        content = current_log.read_text(encoding="utf-8", errors="ignore")
                        all_lines = content.splitlines()
                        if last_log_line_count == 0:
                            # Send initial tail
                            new_lines = all_lines[-60:]
                        elif len(all_lines) > last_log_line_count:
                            new_lines = all_lines[last_log_line_count:]
                        last_log_line_count = len(all_lines)
                    except Exception:
                        pass

                payload = {
                    "type": "update",
                    "state": state,
                    "new_logs": new_lines
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'msg': str(e)})}\n\n"

            time.sleep(1.5)

    return Response(
        event_stream(),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def run_dashboard(host="0.0.0.0", port=7789):
    app.run(host=host, port=port, threaded=True, debug=False)


if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 7789))
    print(f"Astronomy LightRAG Dashboard running at http://localhost:{port}")
    run_dashboard(host="0.0.0.0", port=port)
