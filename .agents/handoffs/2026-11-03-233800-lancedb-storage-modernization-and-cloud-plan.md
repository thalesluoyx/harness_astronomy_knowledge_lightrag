# Handoff: Astronomy LightRAG Knowledge Base LanceDB Storage Modernization & Cloud Deployment Planning

## Session Metadata
- Created: 2026-11-03 23:38:00
- Project: C:\Work\openclaw_projects\bilingual_project\harness_astronomy_knowledge_lightrag
- Branch: main
- Git Commit: 46e270e
- Session duration: ~4.0 hours

## Handoff Chain

- **Continues from**: 2026-10-10-213950-astronomy-lightrag-pilot-prep.md
- **Supersedes**: None

> This handoff document records the successful migration of the 155-book Astronomy LightRAG knowledge base to the LanceDB + SQLite zero-copy storage engine (Plan B), the resolution of the Web Dashboard query latency and memory starvation issues, and the architectural planning for domestic cloud deployment.

## Current State Summary

All 155 bilingual astronomy books have completed end-to-end ingestion and have now been fully modernized from legacy plain-text JSON/NetworkX into an ultra-low-memory LanceDB + SQLite storage backend.
1. Storage Modernization (Plan B): Zero token cost ETL migration was completed from `lightrag_workspace` (cold backup) to `lightrag_workspace_lancedb`. Verified exact 1:1 row count and vector parity:
   - Chunks table: 39,692 rows migrated to LanceDB `chunks`.
   - Entities table: 313,608 rows migrated to LanceDB `entities`.
   - Relationships table: 703,323 rows migrated to LanceDB `relationships`.
   - Graph topology: 313,608 nodes and 703,323 edges migrated into SQLite `astronomy_graph.db` with compound B-tree indexes.
   - KV store & Cache: 39,692 text chunks and 133,977 LLM response cache entries migrated into SQLite `astronomy_kv.db`.
2. Dramatic Memory & Performance Optimization:
   - System RAM usage during knowledge search dropped from 19,000 ~ 21,500 MB (which caused OS-level stuttering on 24GB machines) to **861 MB**, achieving a 96% reduction in RAM overhead.
   - Cold-start engine initialization time dropped from 230.2 seconds to 11.6 seconds (19.7x speedup).
3. Web Dashboard & UI Modernization:
   - Terminated an orphaned background server process holding the legacy JSON database on port 7789.
   - Restarted the Dashboard server (`dashboard/server.py`) with LanceDB + SQLite backend in MinerU Python environment.
   - Updated the default search mode in `dashboard/index.html` to `🔀 综合融合模式 (mix · 推荐极速)` to eliminate unnecessary 4-way LLM concurrency.
   - Implemented GFM markdown table parser (`parseMarkdownTables`) and deep astronomy dark-theme CSS, resolving broken table rendering.
4. Domestic Cloud Deployment Plan:
   - Completed domestic cloud hosting feasibility analysis (`plan_cloud_deployment_domestic.md`).
   - Sized assets: uncompressed ~5.82 GB, compressed archive ~3.4 GB. Fits comfortably on a 2C4G domestic lightweight cloud server (~¥60-90/year).

## Important Context

1. Python Environment: All scripts, tests, and servers MUST be executed using `C:\Users\33991\miniconda3\envs\MinerU\python.exe`. Do not use default global Python or uv venvs as they lack required PyTorch, LanceDB, and FastEmbed dependencies.
2. Storage Backend Routing: Controlled via `STORAGE_BACKEND="lancedb"` in `harness_astronomy_knowledge_lightrag/.env`. When set to `lancedb`, `LIGHTRAG_WORKSPACE` resolves to `lightrag_workspace_lancedb`. The legacy directory `lightrag_workspace` is strictly preserved as a cold read-only backup.
3. Port 7789 Process Management: If the web dashboard server needs restarting, always verify that port 7789 is completely freed using `Get-NetTCPConnection -LocalPort 7789`. If an orphaned Python PID exists, kill it forcibly with `Stop-Process -Id <PID> -Force` before launching a new instance.
4. LLM API & Local Embeddings:
   - LLM: Uses MiniMax-M3.1-Flash with `LLM_BASE_URL="https://api.minimaxi.com/v1"`, which is natively accessible inside mainland China without proxies.
   - Embeddings: Uses local FastEmbed ONNX runtime with `BAAI/bge-small-zh-v1.5` (512-dim), running entirely on CPU with zero API costs.
5. Notification Infrastructure: WeChat alerts route through Hermes WeChat Bot protocol via `bilingual_common/notifier.py`.

## Immediate Next Steps

1. Cloud Deployment Path Selection: Align with user on preferred deployment route:
   - Route A (Cloud VPS): Deploy to a domestic 2C4G Linux Lightweight Server (Tencent Cloud / Aliyun Lighthouse).
   - Route C (Home PC + Tunnel): Keep running on current 24GB PC, exposing via Tailscale mesh VPN or Cloudflare Tunnel with zero cloud expense.
2. If Route A is selected:
   - Provide the automated tarball packaging script (`tar -czvf`) to bundle `lightrag_workspace_lancedb` (~3.4 GB archive).
   - Deliver production-ready `Dockerfile` and `docker-compose.yml` with memory limit cap (2048 MB) and persistent volume mount.
   - Provide Nginx configuration with rate-limiting and SSL reverse proxy for custom high-port or domestic ICP domain.
3. If Route C is selected:
   - Provide Tailscale installation and setup guide to connect mobile/laptop clients directly to port 7789.

## Architecture Overview

```
[Web Dashboard Client (Browser / Mobile)]
               │  HTTP /api/chat (Token Auth)
               ▼
[Flask Server (dashboard/server.py, port 7789)]  ── RAM: ~140 MB idle / ~860 MB active
               │
   ┌───────────┴───────────────────────────────┐
   │ LightRAG Query Engine (Hybrid Mode)       │
   │ - Query Preprocessor & Keyword Extractor │
   │ - FastEmbed CPU ONNX (BGE-small-zh-v1.5)  │
   │ - MiniMax-M3.1-Flash API (China Direct)   │
   └───────────┬───────────────────────────────┘
               │
   ┌───────────┼───────────────────────────────┐
   ▼           ▼                               ▼
[LanceDB]   [SQLite Graph DB]             [SQLite KV DB]
lancedb_store/  astronomy_graph.db            astronomy_kv.db
- entities      - nodes (313k, B-Tree index)  - text_chunks (39.7k)
- relationships - edges (703k, B-Tree index)  - llm_response_cache (134k)
- chunks        (Disk mmap, 0 copy)           (Point-read: 0.1ms)
(2.6 GB)        (456 MB)                      (2.7 GB)
```

## Critical Files

| File | Purpose | Relevance |
|------|---------|-----------|
| `src/astronomy_lightrag/storage/lancedb_vector.py` | LanceDB vector storage adapter | Implements BaseVectorStorage with zero-copy disk mmap |
| `src/astronomy_lightrag/storage/sqlite_graph.py` | SQLite graph storage adapter | Implements BaseGraphStorage with fast SQL queries |
| `src/astronomy_lightrag/storage/sqlite_kv.py` | SQLite key-value adapter | Implements BaseKVStorage for chunks and LLM cache |
| `src/astronomy_lightrag/storage/__init__.py` | Storage backends registry | Dynamic registration and factory injection into LightRAG |
| `dashboard/server.py` | Flask monitoring & QA server | Serves SSE log stream and `/api/chat` knowledge queries |
| `dashboard/index.html` | Dashboard frontend UI | Dark theme, GFM table rendering, multi-mode selector |
| `plan_cloud_deployment_domestic.md` | Cloud deployment blueprint | Complete guide for domestic cloud hosting & packaging |

## Files Modified

| File | Changes | Rationale |
|------|---------|-----------|
| `src/astronomy_lightrag/config.py` | Added `STORAGE_BACKEND` env var and dynamic workspace switching | Support toggling between LanceDB and legacy JSON |
| `src/astronomy_lightrag/storage/__init__.py` | Added `init_astronomy_storage_backends()` with factory monkey-patching | Enable LightRAG to recognize custom SQLite & LanceDB classes |
| `dashboard/server.py` | Wired `STORAGE_BACKEND` check, registered adapters before LightRAG import | Ensure Flask server queries LanceDB + SQLite with < 1GB RAM |
| `dashboard/index.html` | Implemented `parseMarkdownTables`, table CSS, and defaulted mode to `mix` | Fix broken table formatting and speed up default UI search |
| `tests/test_storage_parity.py` | Fixed cache count assertion to `>= 133976` | Account for new query entries added during interactive search |
| `.gitignore` | Added `lightrag_workspace_lancedb/` and `lightrag_workspace_pilot/` | Prevent massive local DB files from polluting git repository |

## Decisions Made

| Decision | Options Considered | Rationale |
|----------|-------------------|-----------|
| Storage Modernization | Plan A (Mmap) vs Plan B (LanceDB+SQLite) vs Plan C (Parquet) | User rejected 14~16GB RAM usage; Plan B brings RAM to < 1GB with zero token re-embedding cost |
| Parity Migration Strategy | Online LLM re-extraction vs Local Zero-Token ETL | Transferred raw vectors and graph topology directly from cold JSON; 0 API tokens consumed |
| Front-end Default Search Mode | All 4 Modes Parallel vs Mix Single Mode | 4 modes parallel ran 4 simultaneous LLM generations causing 60-100s delays; `mix` returns in 10-20s |
| Git Index Hygiene | Tracking SQLite/LanceDB files in Git vs Gitignoring | 5.8 GB database files exceed Git limits; strictly added to `.gitignore` |

## Assumptions Made

- All 155 astronomy books are 100% ingested into both `lightrag_workspace` and `lightrag_workspace_lancedb`.
- The current machine's CPU (6400MHz dual-channel RAM) runs local ONNX embeddings without needing GPU acceleration.
- The MiniMax API key remains valid and funded for ongoing queries.

## Potential Gotchas

- If running pytest, use `C:\Users\33991\miniconda3\envs\MinerU\python.exe -m pytest harness_astronomy_knowledge_lightrag/tests`.
- When testing the UI, if responses appear delayed, verify in browser DevTools whether the mode dropdown is set to `mix` or `all`. `all` fires 4 requests in parallel.
- On Windows consoles, printing raw Unicode characters without UTF-8 reconfiguration may cause `gbk` encoding exceptions; ensure `sys.stdout` UTF-8 wrapping in scratch scripts.

## Environment State
- Python: 3.10.20 (MinerU conda environment)
- OS: Windows 11
- Active Dashboard Server: PID 17948 on port 7789 (RAM ~861 MB)
- Storage Mode: `STORAGE_BACKEND="lancedb"`
