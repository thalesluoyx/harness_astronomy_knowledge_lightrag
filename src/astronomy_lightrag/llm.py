import re
import time
import httpx
import logging
import numpy as np
from typing import List, Optional
from openai import APIStatusError
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, EMBEDDING_MODEL, EMBEDDING_DIM
from .token_tracker import get_token_tracker, TokenTracker

logger = logging.getLogger("astronomy_lightrag.llm")

def get_minimax_llm_func(
    model: str = LLM_MODEL,
    api_key: str = LLM_API_KEY,
    base_url: str = LLM_BASE_URL,
    tracker: Optional[TokenTracker] = None
):
    """
    Creates an LLM model function for LightRAG with:
    1. 90% Token plan exhaustion prevention (pauses until 5h clock reset).
    2. Automatic recovery from 402 insufficient balance errors.
    3. Live progress and token consumption logging.
    4. Automatic stripping of <think> reasoning tags.
    """
    if tracker is None:
        tracker = get_token_tracker()

    async def llm_func(prompt, system_prompt=None, history_messages=None, **kwargs):
        # 1. Check & wait if 90% window limit has been reached
        await tracker.wait_if_limit_reached()

        summary = tracker.usage_summary()
        logger.info(
            f"⚡ [LLM] Calling {model} (prompt: {len(prompt)} chars) | "
            f"5h Window: {summary['window_pct']}% ({summary['window_tokens']:,}/{summary['window_soft_limit']:,} tokens)"
        )

        start_time = time.time()
        max_retries = 3

        for attempt in range(max_retries):
            try:
                result = await openai_complete_if_cache(
                    model=model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=api_key,
                    base_url=base_url,
                    token_tracker=tracker,
                    **kwargs
                )

                elapsed = time.time() - start_time
                summary_after = tracker.usage_summary()
                logger.info(
                    f"✅ [LLM] Response received in {elapsed:.1f}s | "
                    f"Current 5h usage: {summary_after['window_pct']}% ({summary_after['window_tokens']:,} tokens)"
                )

                # Clean <think> tags if present
                if isinstance(result, str):
                    cleaned = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
                    return cleaned if cleaned else result
                return result

            except APIStatusError as err:
                is_402 = err.status_code == 402 or "insufficient_balance" in str(err)
                if is_402:
                    logger.warning(
                        f"⚠️ [TokenTracker] API returned 402 Insufficient Balance on attempt {attempt+1}! "
                        f"Marking 5h window full and pausing until next clock reset..."
                    )
                    tracker.mark_limit_reached()
                    await tracker.wait_if_limit_reached()
                    continue
                else:
                    logger.error(f"❌ [LLM] APIStatusError {err.status_code}: {err}", exc_info=True)
                    raise

            except Exception as e:
                logger.error(f"❌ [LLM] Call error on attempt {attempt+1}: {e}", exc_info=True)
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

    return llm_func

def get_minimax_embedding_func(
    model: str = EMBEDDING_MODEL,
    api_key: str = LLM_API_KEY,
    base_url: str = LLM_BASE_URL,
    dim: int = EMBEDDING_DIM
) -> EmbeddingFunc:
    """
    Creates an EmbeddingFunc compatible with LightRAG that calls MiniMax's
    native embedding endpoint (embo-01).
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async def embedding_call(texts: List[str], **kwargs) -> np.ndarray:
        all_vectors = []
        batch_size = 10
        logger.debug(f"Vectorizing {len(texts)} chunks via {model}...")
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                payload = {
                    "model": model,
                    "texts": batch,
                    "type": "db"
                }
                r = await client.post(f"{base_url}/embeddings", headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                vectors = data.get("vectors", [])
                if not vectors:
                    raise ValueError(f"Minimax embedding returned no vectors: {data}")
                all_vectors.extend(vectors)

        return np.array(all_vectors, dtype=np.float32)

    return EmbeddingFunc(
        embedding_dim=dim,
        max_token_size=2048,
        func=embedding_call
    )
