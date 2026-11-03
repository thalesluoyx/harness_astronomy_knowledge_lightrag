"""
gemini_judge.py
Heterogeneous Knowledge Graph Quality Sampler & Judge.

Architecture (aligned with bilingual_project/quality_checker):
1. Mechanical Sampling (Python side, zero LLM calls):
   - Extracts real entity & relation samples for the completed book from LightRAG VDB/KV stores.
   - Mechanically scans 100% of the book's entities/relations for <think> tag pollution or OCR garbage (\ufffd).
   - Writes the sample payload to `data/pending_graph_audits.json`.
2. Heterogeneous Evaluation (Antigravity built-in Gemini Agent):
   - The Antigravity Agent (running Gemini 3.8 Flash / Pro natively in the IDE) reads
     `data/pending_graph_audits.json`, evaluates across the 4 dimensions (Completeness,
     Cleanliness, Accuracy, Consistency), and writes the quality report.
   - Never falls back to MiniMax-M3 so the generator LLM never judges its own output.
"""
import os
import re
import json
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("astronomy_lightrag.harness.judge")

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent.parent
WORKSPACE_DIR = PROJECT_ROOT / "lightrag_workspace"
DATA_DIR = PROJECT_ROOT / "data"
PENDING_AUDITS_FILE = DATA_DIR / "pending_graph_audits.json"

THINKING_PATTERNS = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
]


def prepare_book_graph_sample(book_title: str, max_entities: int = 15, max_relations: int = 10) -> Dict[str, Any]:
    """
    Mechanically samples extracted entities and relations for `book_title` from LightRAG storage,
    and performs a 100% regex scan for <think> pollution and garbled characters.
    No LLM API calls are made.
    """
    clean_book_title = book_title.replace("《", "").replace("》", "").strip()
    matched_entities = []
    matched_relations = []
    thinking_hits = []
    garbled_hits = []

    vdb_ent_path = WORKSPACE_DIR / "vdb_entities.json"
    if vdb_ent_path.exists():
        try:
            vdb_ent = json.loads(vdb_ent_path.read_text(encoding="utf-8"))
            for item in vdb_ent.get("data", []):
                fp = item.get("file_path", "")
                if clean_book_title in fp or book_title in fp:
                    content = item.get("content", "")
                    ent_name = item.get("entity_name", "")
                    matched_entities.append({
                        "entity_name": ent_name,
                        "description": content[:500]
                    })
                    for pat in THINKING_PATTERNS:
                        if pat.search(content) or pat.search(ent_name):
                            thinking_hits.append(ent_name)
                    if "\ufffd" in content or "\ufffd" in ent_name:
                        garbled_hits.append(ent_name)
        except Exception as e:
            logger.warning(f"Failed to scan vdb_entities.json for {book_title}: {e}")

    vdb_rel_path = WORKSPACE_DIR / "vdb_relationships.json"
    if vdb_rel_path.exists():
        try:
            vdb_rel = json.loads(vdb_rel_path.read_text(encoding="utf-8"))
            for item in vdb_rel.get("data", []):
                fp = item.get("file_path", "")
                if clean_book_title in fp or book_title in fp:
                    content = item.get("content", "")
                    src = item.get("src_id", "")
                    tgt = item.get("tgt_id", "")
                    matched_relations.append({
                        "src": src,
                        "tgt": tgt,
                        "description": content[:400]
                    })
                    for pat in THINKING_PATTERNS:
                        if pat.search(content):
                            thinking_hits.append(f"{src}->{tgt}")
                    if "\ufffd" in content:
                        garbled_hits.append(f"{src}->{tgt}")
        except Exception as e:
            logger.warning(f"Failed to scan vdb_relationships.json for {book_title}: {e}")

    sampled_ents = random.sample(matched_entities, min(len(matched_entities), max_entities)) if matched_entities else []
    sampled_rels = random.sample(matched_relations, min(len(matched_relations), max_relations)) if matched_relations else []

    cleanliness_score = 20
    if thinking_hits:
        cleanliness_score -= min(15, len(thinking_hits) * 5)
    if garbled_hits:
        cleanliness_score -= min(5, len(garbled_hits) * 2)
    cleanliness_score = max(0, cleanliness_score)

    sample_payload = {
        "book_title": book_title,
        "sampled_at": datetime.now().isoformat(),
        "status": "pending_gemini_eval",
        "total_book_entities": len(matched_entities),
        "total_book_relations": len(matched_relations),
        "cleanliness_scan": {
            "cleanliness_score": cleanliness_score,
            "thinking_hits_count": len(thinking_hits),
            "thinking_hits_sample": thinking_hits[:5],
            "garbled_hits_count": len(garbled_hits),
            "garbled_hits_sample": garbled_hits[:5],
        },
        "sampled_entities": sampled_ents,
        "sampled_relations": sampled_rels,
    }

    # Persist to pending_graph_audits.json
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pending_data: Dict[str, Any] = {}
    if PENDING_AUDITS_FILE.exists():
        try:
            pending_data = json.loads(PENDING_AUDITS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pending_data = {}

    pending_data[clean_book_title] = sample_payload
    PENDING_AUDITS_FILE.write_text(json.dumps(pending_data, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        f"📋 [Mechanical Sampler] Prepared sample for '{book_title}': "
        f"{len(sampled_ents)}/{len(matched_entities)} entities, "
        f"{len(sampled_rels)}/{len(matched_relations)} relations, "
        f"cleanliness={cleanliness_score}/20. Queued for Antigravity Gemini Agent."
    )
    return sample_payload


async def evaluate_graph_samples(
    book_title: str,
    samples: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Runs mechanical graph sampling + regex cleanliness scan and queues the sample
    in `data/pending_graph_audits.json` for heterogeneous evaluation by the Antigravity
    Gemini Agent (never falls back to MiniMax-M3).
    """
    payload = prepare_book_graph_sample(book_title)
    clean_score = payload["cleanliness_scan"]["cleanliness_score"]

    return {
        "completeness": 20 if payload["total_book_entities"] > 0 else 0,
        "cleanliness": clean_score,
        "accuracy": "pending_antigravity_gemini",
        "consistency": "pending_antigravity_gemini",
        "total_score": f"Cleanliness {clean_score}/20 (Queued for Gemini Agent)",
        "passed": clean_score >= 15,
        "issues_detected": payload["cleanliness_scan"]["thinking_hits_sample"] + payload["cleanliness_scan"]["garbled_hits_sample"],
        "evaluation_summary": (
            f"Mechanical scan completed ({payload['total_book_entities']} entities, "
            f"{payload['total_book_relations']} relations). Queued in pending_graph_audits.json "
            f"for Antigravity native Gemini evaluation."
        )
    }
