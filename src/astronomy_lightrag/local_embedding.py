"""
local_embedding.py
High-Throughput Local Offline Embedding Engine for Astronomy LightRAG.

Decouples LightRAG Stage 3 vector ingestion from online APIs:
- 0 API token cost
- 0 rate limit errors (429)
- 0 network timeout / connection drops
- Blazing-fast throughput leveraging Ryzen 7 PRO 6850H + 24GB LPDDR5 8000MHz RAM.

Supports:
1. 'fastembed' backend (default): Multi-threaded CPU ONNX Runtime with quantized models (e.g. BAAI/bge-small-zh-v1.5, intfloat/multilingual-e5-large).
2. 'sentence_transformers' backend: Full precision or INT8 models (e.g. BAAI/bge-m3).
3. Non-blocking asynchronous integration via asyncio.to_thread for LightRAG event loops.
"""
import os
import asyncio
import logging
from typing import List, Optional, Callable, Any
import numpy as np

logger = logging.getLogger("astronomy_lightrag.local_embedding")

# Default local model configuration
DEFAULT_MODEL_NAME = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
DEFAULT_BACKEND = os.getenv("LOCAL_EMBEDDING_BACKEND", "fastembed")
DEFAULT_THREADS = int(os.getenv("LOCAL_EMBEDDING_THREADS", "8"))
DEFAULT_BATCH_SIZE = int(os.getenv("LOCAL_EMBEDDING_BATCH_SIZE", "64"))


class LocalEmbeddingEngine:
    """
    Singleton-style local embedding inference engine with multi-threaded CPU acceleration.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        backend: str = DEFAULT_BACKEND,
        threads: int = DEFAULT_THREADS,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.model_name = model_name
        self.backend = backend.lower()
        self.threads = threads
        self.batch_size = batch_size
        self._model = None
        self._embedding_dim: Optional[int] = None

        logger.info(
            f"Initializing LocalEmbeddingEngine: model={self.model_name}, "
            f"backend={self.backend}, threads={self.threads}"
        )
        self._load_model()

    def __deepcopy__(self, memo):
        # FastEmbed onnx InferenceSession cannot be pickled/deepcopied.
        # Since this engine is thread-safe and acts as a singleton, just return self.
        return self

    def _load_model(self):
        """Loads the underlying embedding model into memory."""
        if self.backend == "fastembed":
            try:
                from fastembed import TextEmbedding
                self._model = TextEmbedding(model_name=self.model_name, threads=self.threads)
                # Test inference to obtain vector dimension
                test_vec = next(self._model.embed(["probe"]))
                self._embedding_dim = len(test_vec)
                logger.info(f"FastEmbed model '{self.model_name}' loaded. Dim: {self._embedding_dim}")
            except Exception as e:
                logger.error(f"Failed to load fastembed model ({e}). Falling back to sentence-transformers...")
                self.backend = "sentence_transformers"
                self._load_st_model()
        else:
            self._load_st_model()

    def _load_st_model(self):
        """Loads model via sentence_transformers."""
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_name, device="cpu")
        self._embedding_dim = self._model.get_sentence_embedding_dimension()
        logger.info(f"SentenceTransformer '{self.model_name}' loaded. Dim: {self._embedding_dim}")

    @property
    def embedding_dim(self) -> int:
        """Returns the embedding dimension."""
        return self._embedding_dim or 512

    def embed_sync(self, texts: List[str]) -> np.ndarray:
        """
        Synchronous batch embedding inference.

        Args:
            texts: List of strings to encode.

        Returns:
            np.ndarray of shape (len(texts), embedding_dim), dtype=float32.
        """
        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32)

        if self.backend == "fastembed":
            # fastembed returns generator of numpy arrays
            vecs = list(self._model.embed(texts, batch_size=self.batch_size))
            return np.array(vecs, dtype=np.float32)
        else:
            # sentence_transformers
            vecs = self._model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return vecs.astype(np.float32)

    async def embed_async(self, texts: List[str]) -> np.ndarray:
        """
        Asynchronous wrapper executing CPU inference in a worker thread.
        Prevents blocking LightRAG's asyncio event loop.
        """
        return await asyncio.to_thread(self.embed_sync, texts)


# Global singleton instance
_GLOBAL_ENGINE: Optional[LocalEmbeddingEngine] = None


def get_local_embedding_engine(
    model_name: Optional[str] = None,
    backend: Optional[str] = None
) -> LocalEmbeddingEngine:
    """Retrieves or instantiates the global LocalEmbeddingEngine singleton."""
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        _GLOBAL_ENGINE = LocalEmbeddingEngine(
            model_name=model_name or DEFAULT_MODEL_NAME,
            backend=backend or DEFAULT_BACKEND
        )
    return _GLOBAL_ENGINE


def get_local_embedding_func(
    engine: Optional[LocalEmbeddingEngine] = None
) -> Callable[[List[str]], Any]:
    """
    Returns an async callable compatible with LightRAG's embedding_func parameter.
    """
    eng = engine or get_local_embedding_engine()

    async def _embedding_func(texts: List[str]) -> np.ndarray:
        return await eng.embed_async(texts)

    # Attach dimension attribute for LightRAG initialization inspection
    setattr(_embedding_func, "embedding_dim", eng.embedding_dim)
    return _embedding_func


if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    print("Testing LocalEmbeddingEngine...")
    engine = get_local_embedding_engine()

    sample_queries = [
        "M31 (仙女座大星系) 的视星等与表面亮度是多少？",
        "What are the best visual filters for observing the Orion Nebula M42?",
        "NGC 869 and NGC 884 constitute Caldwell 14 Double Cluster.",
        "高桥 TSA-120 与裕众 130APO 三片式折射望远镜的色差矫正对比。",
    ] * 25 # 100 queries

    print(f"\nBenchmarking local inference on {len(sample_queries)} astronomy chunks...")
    t0 = time.time()
    embeddings = engine.embed_sync(sample_queries)
    elapsed = time.time() - t0

    print(f"Computed {len(embeddings)} embeddings in {elapsed:.3f}s")
    print(f"Throughput: {len(sample_queries) / elapsed:.1f} chunks/sec")
    print(f"Output Matrix Shape: {embeddings.shape}, Dtype: {embeddings.dtype}")
    print(f"Sample L2 Norm of first vector: {np.linalg.norm(embeddings[0]):.4f}")
