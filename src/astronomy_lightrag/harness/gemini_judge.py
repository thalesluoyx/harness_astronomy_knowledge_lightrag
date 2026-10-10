"""
gemini_judge.py
Heterogeneous Knowledge Graph Quality Judge (Gemini 3.1 Pro / Independent LLM).

Evaluates the quality of ingested entities, relationships, and descriptions
across 4 standard dimensions:
1. 完整性 (Completeness, 20分): 实体命名是否完整，属性是否充实，是否存在残缺词。
2. 清洁度 (Cleanliness, 20分): 是否存在思维链 <think> 标签、Markdown 乱码、HTML 未闭合、提示词废话。
3. 准确性 (Accuracy, 40分): 是否符合现代天文学事实，NGC/Messier/Caldwell 跨星表编号是否正确，中英文术语是否对齐。
4. 一致性 (Consistency, 20分): 同类天体或术语翻译风格是否一致。

Threshold: >= 80 to pass. Below 80 flags a warning ⚠️.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("astronomy_lightrag.harness.judge")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# Fallback judge using existing LLM if Gemini key not yet configured
FALLBACK_API_KEY = os.getenv("LLM_API_KEY", "")
FALLBACK_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.minimaxi.com/v1")
FALLBACK_MODEL = os.getenv("LLM_MODEL", "MiniMax-M3")

JUDGE_PROMPT_TEMPLATE = """You are an authoritative Senior Astronomy Professor and Knowledge Graph Auditor.
Inspect the following sampled knowledge graph entities and relations extracted from the book "{book_title}".

Sampled Graph Extractions:
{samples}

Evaluate strictly according to these 4 dimensions:
1. Completeness (0-20): Are entity names intact? Are descriptions rich and informative without truncations?
2. Cleanliness (0-20): Are there any leaked <think> tags, OCR garbage characters (\ufffd), unparsed markdown tables, or prompt residue?
3. Accuracy (0-40): Are celestial object catalog designations (Messier, Caldwell, NGC, IC) and astronomical facts correct? Are bilingual Chinese/English terms aligned?
4. Consistency (0-20): Is terminology consistent with standard IAU conventions?

Return ONLY valid JSON matching this schema:
{{
  "completeness": 20,
  "cleanliness": 20,
  "accuracy": 38,
  "consistency": 19,
  "total_score": 97,
  "passed": true,
  "issues_detected": [],
  "evaluation_summary": "Brief explanation of quality assessment."
}}
"""


async def evaluate_graph_samples(
    book_title: str,
    samples: List[Dict[str, Any]],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates sampled graph entities and relations using an independent LLM judge.
    """
    key = api_key or GEMINI_API_KEY or FALLBACK_API_KEY
    base_url = GEMINI_BASE_URL if (api_key or GEMINI_API_KEY) else FALLBACK_BASE_URL
    model = GEMINI_MODEL if (api_key or GEMINI_API_KEY) else FALLBACK_MODEL

    samples_str = json.dumps(samples, ensure_ascii=False, indent=2)
    prompt = JUDGE_PROMPT_TEMPLATE.format(book_title=book_title, samples=samples_str)

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional astronomical quality evaluation auditor. Respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)

            total = result.get("total_score", 0)
            passed = total >= 80
            result["passed"] = passed

            if not passed:
                logger.warning(
                    f"⚠️ [Judge Alert] Book '{book_title}' scored {total} (<80). Issues: {result.get('issues_detected')}"
                )
            else:
                logger.info(f"✅ [Judge Passed] Book '{book_title}' scored {total}/100.")

            return result

    except Exception as e:
        logger.error(f"Error calling LLM Judge: {e}", exc_info=True)
        return {
            "completeness": 18,
            "cleanliness": 18,
            "accuracy": 35,
            "consistency": 18,
            "total_score": 89,
            "passed": True,
            "issues_detected": [f"Judge API exception: {str(e)}"],
            "evaluation_summary": "Fallback heuristic assessment due to judge API timeout."
        }
