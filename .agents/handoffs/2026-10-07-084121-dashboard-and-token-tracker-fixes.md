# Handoff: Dashboard UX, Pipeline Stages, and Token Tracker Log Fixes

## Session Metadata
- Created: 2026-10-07 08:41:21
- Project: C:\Work\openclaw_projects\bilingual_project\harness_astronomy_knowledge_lightrag
- Branch: main
- Session duration: 1.5 hours

### Recent Commits (for context)
  - 00be2db docs: update README with dashboard, precise pipeline stages and token tracker features
  - 4c62e28 fix: rename pipeline stages to start from 1 for better UX
  - 9493452 fix: add concurrency lock and robust RPM backoff to embedding_call
  - da54a73 fix: accurate dashboard pipeline stage tracking & robust vector flush logging
  - cc79339 feat: enhance dashboard to visualize stage 2.5 entity merging and stage 3 embedding

## Handoff Chain

- **Continues from**: [2026-10-06-195339-lightrag-astronomy-poc.md](./2026-10-06-195339-lightrag-astronomy-poc.md)
  - Previous title: Astronomy Knowledge Base Ingestion POC (LightRAG + MiniMax)
- **Supersedes**: None

> Review the previous handoff for full context before filling this one.

## Current State Summary

I resolved several UX and logic desyncs on the Dashboard (`server.py`). Previously, the dashboard incorrectly reported 100% progress the moment "Extraction" finished, confusing the user because "Merging" and "Vector Flushing" still took significant time. The stages are now cleanly tracked and scaled. I also ensured that new `TokenTracker` pause logs are properly captured by the dashboard to show a `paused_quota` state. The user has manually requested to kill all background tasks to pause the ingestion process.

## Codebase Understanding

### Architecture Overview

- **LightRAG Internal Sequence**: The `ainsert()` process internally has 3 main stages: 
  1. Chunk-by-chunk Entity Extraction (reported progressively in `lightrag_ingest.log`).
  2. Entity Merging / Deduplication (batch LLM calls, no built-in progression logs).
  3. Vector DB Embedding/Flush (MiniMax `embo-01`).
- **Dashboard Monitoring**: The dashboard (`server.py`) is entirely stateless and independent. It infers pipeline progress **purely by parsing `lightrag_ingest.log`** using Regex. To capture Stage 3, the `embedding_func` in `llm.py` must explicitly emit `INFO` level logs with the "🚀 [Embedding]" signature.

### Critical Files

| File | Purpose | Relevance |
|------|---------|-----------|
| `dashboard/server.py` | Runs the Flask API and SSE stream | Contains log parsing logic and UI state aggregation. |
| `src/astronomy_lightrag/llm.py` | LightRAG LLM & Embedding overrides | Contains `logger.info` hook points that the dashboard relies on. |
| `README.md` | Project documentation | Documented architecture and pipeline stages. |

### Key Patterns Discovered

- **Decoupled Monitoring**: The web dashboard does not touch LightRAG's internal stores to avoid lock contention; it strictly parses logs and checks basic cache sizes.
- **Token Tracker Pause Strings**: The `token_tracker.py` now logs "Pausing pipeline until", which `server.py` watches to trigger the amber pause UI state.

## Work Completed

### Tasks Finished

- [x] Refactored `server.py` progress logic to weight stages: Extraction (0-70%), Merging (85%), Embedding (95%).
- [x] Renamed pipeline stages sequentially (1, 2, 3) instead of (2, 2.5, 3) based on user feedback.
- [x] Lifted `logger.debug` to `logger.info("🚀 [Embedding]")` in `llm.py` to expose Phase 3 to the dashboard.
- [x] Fixed `server.py` regex `wait_matches = re.findall(r"remaining ([\d\.]+)m", content)` to correctly handle new `TokenTracker` wait state logs.
- [x] Killed all background ingestion and dashboard tasks.
- [x] Updated `README.md` with detailed stage and dashboard info.

### Files Modified

| File | Changes | Rationale |
|------|---------|-----------|
| `dashboard/server.py` | Refactored `parse_log_stats` and `pct` logic; fixed token tracker regex. | To show accurate pipeline lifecycle instead of premature 100%. |
| `src/astronomy_lightrag/llm.py` | Changed `logger.debug` to `logger.info` in `get_minimax_embedding_func`. | The dashboard needs to grep this log line to know when embedding starts. |
| `README.md` | Added explanations of the 3 stages, token tracker, and dashboard. | Keep documentation up to date. |

### Decisions Made

| Decision | Options Considered | Rationale |
|----------|-------------------|-----------|
| **Renaming Stages 1, 2, 3** | Keep as 2, 2.5, 3 or start at 1. | User asked why there was no "Stage 1". I shifted the numbers because "Preprocessing/File reading" is instantaneous and not visible on the dashboard, making "Extraction" the natural Stage 1. |
| **Progress Scaling** | Try to calculate exact progress for Merging/Embedding vs Fixed percentages. | LightRAG doesn't log exact completion tracking for Merging/Embedding phases. Pinning to 85% and 95% offers a clean UX without needing deep library hacks. |

## Pending Work

## Immediate Next Steps

1. Restart the pipeline and dashboard (`python scripts/run_ingestion.py` and `python dashboard/server.py`). The pipeline will resume from the last saved state.
2. Monitor the dashboard during the "Merging" and "Embedding" phases to ensure it reliably captures the logs under full load.
3. Observe if any new `TokenTracker` output string formats break the `server.py` parser, as it's regex-based.

### Blockers/Open Questions

- [ ] None currently.

### Deferred Items

- None.

## Context for Resuming Agent

## Important Context

**The system is currently stopped.** All background tasks have been explicitly killed. When you resume, you will likely need to restart `scripts/run_ingestion.py` if the user wants to continue the POC. LightRAG's `DocStatus` and state JSON mechanisms are robust, so starting the ingestion script again is perfectly safe and will pick up where it left off.

If you ever change `token_tracker.py` or `llm.py`'s log output text, **you MUST also update the regex parsers in `dashboard/server.py`**. The entire dashboard relies on strictly formatted log lines.

### Assumptions Made

- The pipeline will comfortably run out of memory before it crashes if we don't throttle the embedding calls.

### Potential Gotchas

- **Do not edit `lightrag_workspace` JSONs manually.** LightRAG depends on these caches. Let `run_ingestion.py` manage them.
- If you see `NameError: name 'asyncio' is not defined` inside `operate.py` from the `lightrag` library, remember that we already fixed the overarching `asyncio` issue in our `llm.py` wrappers. Do not worry unless it fully crashes the script.

## Environment State

### Tools/Services Used

- **Flask**: Dashboard on port 7789
- **LightRAG**: Core RAG pipeline
- **MiniMax**: Provider for LLM (MiniMax-M3) and Embeddings (embo-01)

### Active Processes

- **None** (Explicitly terminated).

### Environment Variables

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `DASHBOARD_USERNAME`
- `DASHBOARD_PASSWORD`

## Related Resources

- `logs/lightrag_ingest_*.log`: Check this for exact pipeline execution history.
- `data/token_tracker_state.json`: Track current 5h limit context.

---

**Security Reminder**: Before finalizing, run `validate_handoff.py` to check for accidental secret exposure.
