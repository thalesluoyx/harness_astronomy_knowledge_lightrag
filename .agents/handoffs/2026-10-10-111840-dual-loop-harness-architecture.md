# Handoff: Astronomy LightRAG POC Review & Harness Architecture Design

## Session Metadata
- Created: 2026-10-10 11:18:40
- Project: C:\Work\openclaw_projects\bilingual_project
- Branch: [not a git repo or detached HEAD]
- Session duration: 1 hour

## Handoff Chain

- **Continues from**: None (fresh start)
- **Supersedes**: None

> This is the first handoff for this task.

## Current State Summary

We have just completed the "POC Review and Optimization Design" phase for building the Astronomy Knowledge Graph (155 bilingual books). The user provided a reference architecture for a Harness orchestrator. We have designed a new **Dual-Loop ReAct Harness** system, documented the architectural diagram as an SVG, and written a comprehensive optimization report. We are now ready to begin **coding the Harness framework** in the next session.

## Codebase Understanding

### Architecture Overview

**The New Dual-Loop ReAct Harness Architecture:**
1. **Outer Loop (Orchestrator)**: Manages the 155 books. Includes Budget-Aware dispatching, state loading (Checkpointing), Evaluate & Quality Check (using a Gemini Judge), and deciding whether to proceed or sleep based on the MiniMax 5h window limit.
2. **Inner Loop (Parallel Pipeline)**:
   - **Track A (Stage 1+2)**: Uses MiniMax-M3 for knowledge extraction and graph fusion. *CRITICAL CONSTRAINT: Strict single-book sequential execution to respect Token limits.*
   - **Track B (Stage 3)**: Uses a local bge-m3 embedding model on an AMD Mini PC. 
   - **Handoff Queue**: An `asyncio.Queue` decoupled Stage 1+2 and Stage 3. This allows Book N's Stage 3 to run in parallel with Book N+1's Stage 1+2.
3. **Quality Check**: Uses Gemini 3.1 Pro (Heterogeneous LLM-as-a-Judge) to sample 5 chunks per book and evaluate graph quality. Total score must be >80.
4. **Notifier**: We will extract the WeChat notifier from existing code into a `bilingual_project/bilingual_common/notifier.py` module for alerting on failures or low QA scores.

### Critical Files

| File | Purpose | Relevance |
|------|---------|-----------|
| `docs/astronomy_lightrag_poc_review_and_optimization.md` | Comprehensive POC summary and architectural blueprint | Primary design document. Contains 4 optimization suggestions. |
| `astronomy_harness_architecture.svg` | Architecture diagram | Visual reference for the Dual-Loop Harness. Located in artifact dir and linked in the markdown. |
| `harness/notifier.py` | Reference WeChat notifier code | Contains the `WeixinNotifier` logic using `ilinkai` long-polling. Needs to be refactored into `bilingual_common`. |

### Key Patterns Discovered

- **Avoid `cd` commands**: The agent must always use the explicit `Cwd` argument in shell commands instead of `cd`.
- **Scratch Files**: All temporary or one-off scripts MUST be saved in the `scratch/` directory.
- **Log Routing**: Subprocess stdout/stderr must be piped into the Python logging module and stored in the `bilingual_output` directory. Raw progress bars (e.g., `tqdm`) should be suppressed in logs.

## Work Completed

### Tasks Finished

- [x] Analyzed 6 core engineering issues from the POC phase (Token limits, HTTP 422, Vector DB limits, etc.).
- [x] Designed the Dual-Loop ReAct Harness architecture.
- [x] Generated the SVG architecture diagram `astronomy_harness_architecture.svg`.
- [x] Proposed and finalized the Gemini Judge (Heterogeneous QA) strategy.
- [x] Updated the optimization summary document (`astronomy_lightrag_poc_review_and_optimization.md`).

## Pending Work

## Immediate Next Steps

1. **Refactor Notifier**: Create the `bilingual_project/bilingual_common` directory and migrate/adapt the `notifier.py` into a unified public module for WeChat alerts.
2. **Implement Outer Loop**: Scaffold the new `astronomy_harness.py` script featuring the Outer Loop (Budget-aware dispatch, Checkpointing, Evaluate Milestone).
3. **Implement Inner Loop**: Build the `asyncio` based dual-track pipeline (Track A for MiniMax Stage 1+2, Track B for Local Stage 3 embedding).
4. **Implement Gemini Judge**: Add the QA script that samples 5 chunks per book and generates `book_N_quality_report.md`.

### Blockers/Open Questions

- [ ] Need to verify where the local embedding model (`bge-m3`) is stored and how to invoke it in the new codebase (e.g., ONNX Runtime or FastEmbed).

## Context for Resuming Agent

## Important Context

- **Do NOT begin coding until you review the `astronomy_lightrag_poc_review_and_optimization.md` document**. It contains the locked architectural decisions.
- **Stage 1+2 is STRICTLY sequential**: Never run Stage 1+2 for two books concurrently due to the 5h token limit of the MiniMax Code Plan.
- **Gemini QA limits**: The QA process is designed to be very lightweight (5 chunks per book) to respect the user's Google AI Pro limits. Do NOT perform full-book QA.

## Assumptions Made

- The user has a Mini PC (AMD Ryzen 7 PRO 6850H, 24GB LPDDR5 8000MHz) that will run Stage 3 locally.
- The user's WeChat bot credentials exist in `~/.openclaw/openclaw-weixin/accounts/` as required by the `notifier.py` script.

## Potential Gotchas

- **Windows Paths**: Use forward slashes (`/`) or `Path.as_posix()` internally in Python scripts to avoid cross-platform hash/path mismatch issues (this was Issue #2 in the POC!).
- **Background Tasks**: There are existing background tasks (e.g., Dashboard Server on port 7789, cloudflared tunnel). Do NOT kill them.

## Environment State

### Tools/Services Used
- Python environment: `C:\Users\33991\miniconda3\envs\MinerU\python.exe`
- Target Books: 155 books located in `c:\Work\openclaw_projects\bilingual_project\bilingual_output\`

### Active Processes
- `task-553`: Dashboard Server (`dashboard/server.py`) running on port 7789.
- `task-574`: Cloudflare Tunnel (`cloudflared`) exposing port 7789.

---

**Security Reminder**: Run `validate_handoff.py` to check for accidental secret exposure before concluding.
