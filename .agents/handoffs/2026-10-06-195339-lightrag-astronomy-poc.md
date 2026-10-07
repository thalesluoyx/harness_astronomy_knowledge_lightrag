# Handoff: Astronomy Knowledge Base Ingestion POC (LightRAG + MiniMax)

## Session Metadata
- Created: 2026-10-06 19:53:39
- Updated: 2026-10-06 20:27:00
- Project: C:\Work\openclaw_projects\bilingual_project
- Sub-Project: harness_astronomy_knowledge_lightrag
- Branch: main
- Git Remote: https://github.com/thalesluoyx/harness_astronomy_knowledge_lightrag.git
- Git Check Status: Clean commit 68b225a pushed to origin/main.
- Session duration: ~5.0 hours (Architecture setup, ADR implementation, token limiter, retry fix, global handoff skill setup, real-time SSE dashboard)

### Recent Commits
- 68b225a feat: add real-time LightRAG ingestion dashboard with SSE and log streamer
- 16095d6 feat: complete astronomy LightRAG ingestion POC with token limiter

## Current State Summary
Building an astronomy knowledge base ingestion POC using LightRAG (lightrag-hku) targeting 5 bilingual books from The Deep Sky Companions series in bilingual_output/. The ingestion pipeline is currently ALIVE and actively extracting Book 1 chunks (>465/608 chunks extracted, ~76.5% done, speed ~17.2s/chunk) in the 20:00-01:00 window. A real-time Flask+SSE progress dashboard has been deployed on `http://localhost:7789` with token quota gauges, reset countdown, live knowledge graph metrics, and a real-time log terminal.

## Important Context
1. Active Ingestion Task: Process task-585 is running python scripts/run_ingestion.py in background. Live logs stream to harness_astronomy_knowledge_lightrag/logs/lightrag_ingest_20261006_193257.log.
2. Clock-Aligned Quota: MiniMax 5h rate window resets at 20:00:00, 01:00:00, 06:00:00, etc. At 20:00:00, token_tracker will automatically reset to 0 and resume Book 1 extraction without manual restart.
3. Cache Protection: Extracted entities are saved to lightrag_workspace/kv_store_llm_response_cache.json. Any re-run reuses this cache instantly with zero token cost.
4. Git Check-in: The workspace does not yet have a .git folder. If user requests check-in, initialize git in bilingual_project and push to GitHub.

## Immediate Next Steps
1. Wait for 20:00:00 clock boundary: The pipeline will automatically wake up and finish the remaining chunks of Book 1.
2. Monitor Stage 3 Embedding: Verify that embo-01 embedding model is called to generate vectors for vdb_entities.json and vdb_relationships.json.
3. Process Books 2 to 5: Allow the pipeline to finish all 5 target books in sequence.
4. Verify Graphml and Vectors: Validate that lightrag_workspace contains complete knowledge graph.
5. Demonstrate QA retrieval: Run test query with LightRAG rag.aquery() across the 5 books.

## Architecture Overview
The system follows python-standard-layout under harness_astronomy_knowledge_lightrag/src/astronomy_lightrag/. It processes 5 bilingual markdown books from bilingual_output/. MiniMax-M3 is used for natural language entity/relation extraction, and embo-01 (1536 dim) is used for embedding. A TokenTracker monitors consumption against a 5.4M 5h window with a 90% soft-limit pause and 60-second heartbeat logging. LightRAG is configured with default_llm_timeout=18000s to avoid worker execution timeouts during rate pauses.

## Critical Files
| File | Purpose | Relevance |
|------|---------|-----------|
| harness_astronomy_knowledge_lightrag/src/astronomy_lightrag/config.py | Central configuration and paths | Defines TARGET_BOOKS, 5.4M quota, 18000s timeout |
| harness_astronomy_knowledge_lightrag/src/astronomy_lightrag/token_tracker.py | Rate-limiting tracker | Manages 5h clock-aligned window and 60s heartbeats |
| harness_astronomy_knowledge_lightrag/src/astronomy_lightrag/llm.py | MiniMax LLM & Embedding adapter | Strips think tags and connects native embo-01 endpoint |
| harness_astronomy_knowledge_lightrag/src/astronomy_lightrag/ingestor.py | Incremental ingestion engine | Handles discovery, ainsert, and DocStatus verification |
| harness_astronomy_knowledge_lightrag/scripts/run_ingestion.py | Execution entry point | Unified logging setup and clean process termination |

## Files Modified
| File | Changes | Rationale |
|------|---------|-----------|
| harness_astronomy_knowledge_lightrag/src/astronomy_lightrag/config.py | Added 5.4M quota, 18000s timeout, LOGS_DIR | Fix timeout conflicts and support local logs |
| harness_astronomy_knowledge_lightrag/src/astronomy_lightrag/token_tracker.py | Configurable quota, 60s heartbeats | Keep user informed and eliminate silent log periods |
| harness_astronomy_knowledge_lightrag/src/astronomy_lightrag/ingestor.py | Pre-book quota checks, stale doc cleanup | Prevent partial failures and ensure retryability |
| harness_astronomy_knowledge_lightrag/scripts/run_ingestion.py | Directed logs to logs/, passed 18000s timeout | Clean process termination and logging separation |

## Decisions Made
| Decision | Options Considered | Rationale |
|----------|-------------------|-----------|
| Upgrade 5h Quota to 5.4M | 3.8M vs 5.4M vs unlimited | Real usage measurement: 3.45M tokens = 64% on MiniMax console (3.45M / 0.64 = 5.4M) |
| Set default_llm_timeout=18000s | 240s vs 18000s | LightRAG internal worker timeout is 2x default_llm_timeout; 18000s avoids premature killing |
| Emit 60s Heartbeats | Single sleep vs periodic heartbeats | Eliminates silent log gaps and provides visible progress to user |
| Localize Logs | bilingual_output/ vs logs/ | Keeps translation directory bilingual_output/ clean and isolates lightrag logs |

## Assumptions Made
- MiniMax 5-hour quota rate window resets at 20:00:00 local time.
- MiniMax embo-01 embedding API expects type=db and texts list, returning 1536-dimensional vectors.
- LightRAG response cache at lightrag_workspace/kv_store_llm_response_cache.json will remain persistent across runs.

## Potential Gotchas
- LightRAG ainsert() returns without raising exceptions when workers fail; must check DocStatus via aget_docs_by_track_id().
- Stale failed documents in LightRAG doc_status storage must be purged before retrying ingestion of the same file.
- The project root is not currently a git repo; pushing to GitHub will require git init first.

## Environment State
- Python Environment: Miniconda MinerU (Python 3.10)
- Core Packages: lightrag-hku 1.5.7, httpx, openai, numpy
- Active Task: task-585 running scripts/run_ingestion.py
- Environment Variables: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, TOKEN_QUOTA_PER_WINDOW, LLM_TIMEOUT
