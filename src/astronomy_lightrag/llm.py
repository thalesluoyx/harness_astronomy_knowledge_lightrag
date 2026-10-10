import re
import time
import httpx
import logging
import asyncio
import numpy as np
from typing import List, Optional
from openai import APIStatusError
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, EMBEDDING_MODEL, EMBEDDING_DIM, EMBEDDING_ENGINE
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
                is_422 = err.status_code == 422 or "sensitive" in str(err).lower() or "unprocessable_entity" in str(err).lower()

                if is_402:
                    logger.warning(
                        f"⚠️ [TokenTracker] API returned 402 Insufficient Balance on attempt {attempt+1}! "
                        f"Marking 5h window full and pausing until next clock reset..."
                    )
                    tracker.mark_limit_reached()
                    await tracker.wait_if_limit_reached()
                    continue
                elif is_422:
                    logger.warning(
                        f"⚠️ [LLM] Content filter / 422 Unprocessable Entity triggered: {err}. "
                        f"Returning safe fallback output to prevent pipeline failure."
                    )
                    if kwargs.get("response_format") == {"type": "json_object"}:
                        return "{}"
                    if "<|COMPLETE|>" in (system_prompt or "") or "<|#|>" in prompt or "<|COMPLETE|>" in prompt or "Entity Types" in prompt:
                        return "<|COMPLETE|>"
                    return "Astronomical object or concept described in catalog records."
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
    dim: int = EMBEDDING_DIM,
    tracker: Optional[TokenTracker] = None
) -> EmbeddingFunc:
    """
    Creates an EmbeddingFunc compatible with LightRAG that calls MiniMax's
    native embedding endpoint (embo-01).
    Includes TokenTracker rate/quota limit handling and automatic 1008 recovery.
    """
    if tracker is None:
        tracker = get_token_tracker()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    embedding_lock = asyncio.Lock()

    async def embedding_call(texts: List[str], **kwargs) -> np.ndarray:
        if tracker:
            await tracker.wait_if_limit_reached()

        all_vectors = []
        batch_size = 8
        logger.info(f"🚀 [Embedding] Vectorizing {len(texts)} chunks via {model}...")
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                payload = {
                    "model": model,
                    "texts": batch,
                    "type": "db"
                }
                max_retries = 15
                success = False
                for attempt in range(max_retries):
                    try:
                        if tracker:
                            await tracker.wait_if_limit_reached()

                        async with embedding_lock:
                            r = await client.post(f"{base_url}/embeddings", headers=headers, json=payload)
                        r.raise_for_status()
                        data = r.json()
                        base_resp = data.get("base_resp", {})

                        # 1002: RPM rate limit exceeded
                        if base_resp.get("status_code") == 1002:
                            wait_sec = min(30.0, 3.0 * (attempt + 1))
                            logger.warning(
                                f"⚠️ [Embedding] MiniMax RPM rate limit reached (1002). "
                                f"Backing off for {wait_sec:.1f}s (attempt {attempt+1}/{max_retries})..."
                            )
                            await asyncio.sleep(wait_sec)
                            continue

                        # 1008 / 402: Insufficient balance
                        is_balance_err = (
                            base_resp.get("status_code") == 1008
                            or "insufficient balance" in str(base_resp).lower()
                        )
                        if is_balance_err:
                            logger.warning(
                                f"⚠️ [Embedding] MiniMax returned 1008 Insufficient Balance on attempt {attempt+1}! "
                                f"Marking 5h window full and pausing until next clock reset..."
                            )
                            if tracker:
                                tracker.mark_limit_reached()
                                await tracker.wait_if_limit_reached()
                            else:
                                await asyncio.sleep(300)
                            continue

                        vectors = data.get("vectors", [])
                        if not vectors:
                            raise ValueError(f"Minimax embedding returned no vectors: {data}")
                        all_vectors.extend(vectors)
                        success = True
                        await asyncio.sleep(0.25)  # Throttle to prevent bursting RPM
                        break
                    except (httpx.RequestError, httpx.HTTPStatusError) as net_err:
                        if isinstance(net_err, httpx.HTTPStatusError) and net_err.response.status_code == 402:
                            logger.warning(
                                f"⚠️ [Embedding] HTTP 402 Insufficient Balance! Pausing for window reset..."
                            )
                            if tracker:
                                tracker.mark_limit_reached()
                                await tracker.wait_if_limit_reached()
                            continue

                        if attempt == max_retries - 1:
                            raise
                        wait_sec = min(30.0, 3.0 * (attempt + 1))
                        logger.warning(f"⚠️ [Embedding] HTTP/Network error: {net_err}. Retrying in {wait_sec:.1f}s...")
                        await asyncio.sleep(wait_sec)

                if not success:
                    raise RuntimeError(f"MiniMax embedding failed to vectorize batch after {max_retries} attempts.")

        return np.array(all_vectors, dtype=np.float32)

    return EmbeddingFunc(
        embedding_dim=dim,
        max_token_size=2048,
        func=embedding_call
    )


def get_astronomy_embedding_func(
    engine_type: Optional[str] = None,
    tracker: Optional[TokenTracker] = None
) -> EmbeddingFunc:
    """
    Returns the appropriate LightRAG EmbeddingFunc based on EMBEDDING_ENGINE ('local' vs 'online').
    When 'local', runs high-throughput in-memory CPU ONNX embedding (0 cost, 0 rate limit).
    """
    target_engine = (engine_type or EMBEDDING_ENGINE).lower()
    if target_engine == "local":
        try:
            from .local_embedding import get_local_embedding_engine
        except ImportError:
            from astronomy_lightrag.local_embedding import get_local_embedding_engine

        engine = get_local_embedding_engine()
        logger.info(
            f"⚡ [Embedding] Using local offline embedding engine: "
            f"model={engine.model_name}, dim={engine.embedding_dim}"
        )
        return EmbeddingFunc(
            embedding_dim=engine.embedding_dim,
            max_token_size=8192,
            func=engine.embed_async
        )
    else:
        logger.info("🌐 [Embedding] Using online MiniMax embo-01 embedding engine.")
        return get_minimax_embedding_func(tracker=tracker)

