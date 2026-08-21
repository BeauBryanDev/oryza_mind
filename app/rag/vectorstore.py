
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

import weaviate
from weaviate.classes.init import AdditionalConfig, Auth, Timeout

from app.core.config import Settings, get_settings
"""
Weaviate client and query embedding.

OryzaMindChunk is vectorizer:none, so I build query vectors ourselves.

SAFETY RULE 1: e5 is asymmetric. Ingest used `passage: `, search must use
`query: `. Omitting it raises nothing and silently degrades retrieval, so
embed_query() applies it and is the only sanctioned path to a search vector.
"""
if TYPE_CHECKING:  # heavy import, deferred at runtime
    from sentence_transformers import SentenceTransformer
# the model is loaded lazily, so it pulls in torch localhost and GPU
logger = logging.getLogger(__name__)


@lru_cache
def get_encoder() -> "SentenceTransformer":
    """Load e5-large-v2 once per process. Imported lazily; it pulls in torch."""
    from sentence_transformers import SentenceTransformer
    #  this is the reason ti takes long time at frist start up
    settings = get_settings()
    logger.info("loading embedding model %s", settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)

    dim = model.get_sentence_embedding_dimension()
    
    if dim != settings.embedding_dim:
        
        raise RuntimeError(
            f"{settings.embedding_model} reports dim {dim}, expected "
            f"{settings.embedding_dim}. The live collection holds "
            f"{settings.embedding_dim}-dim vectors; a mismatch cannot be searched."
        )
    return model


def embed_query(query: str, settings: Settings | None = None) -> list[float]:
    """Encode a query: applies the `query: ` prefix and normalizes, as at ingest."""
    settings = settings or get_settings()
    text = query.strip()
    
    if not text:
        
        raise ValueError("cannot embed an empty query")

    prefixed = f"{settings.embedding_query_prefix}{text}"
    vector = get_encoder().encode(
        prefixed,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vector.tolist()


def embed_queries(queries: list[str], settings: Settings | None = None) -> list[list[float]]:
    """
    Encode several queries in one forward pass.

    Same prefix and normalization as embed_query -- SAFETY RULE 1 applies
    identically. One batched call rather than N: the encoder is CPU-bound and
    holds the GIL, so threading N single encodes barely helps, while batching
    amortizes the per-call overhead across all of them.
    """
    settings = settings or get_settings()
    texts = [q.strip() for q in queries]
    
    if not all(texts):
        
        raise ValueError("cannot embed an empty query")

    prefixed = [f"{settings.embedding_query_prefix}{t}" for t in texts]
    
    vectors = get_encoder().encode(
        prefixed,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=len(prefixed),
    )
    return [v.tolist() for v in vectors]


@lru_cache
def get_client() -> weaviate.WeaviateClient:
    """Connect to Weaviate Cloud. Cached: one client per process."""
    settings = get_settings()
    # The default 2s init timeout is not enough for the gRPC startup ping to a
    # us-east cluster; it intermittently fails the whole connect while REST and
    # queries are fine.
    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=settings.weaviate_url,
        auth_credentials=Auth.api_key(settings.weaviate_api_key),
        additional_config=AdditionalConfig(timeout=Timeout(init=30, query=60, insert=60)),
    )
    logger.info("connected to Weaviate collection %s", settings.weaviate_collection)
    
    return client


def get_collection():
    """Handle to the `OryzaMindChunk` collection."""
    settings = get_settings()
    return get_client().collections.get(settings.weaviate_collection)


def close_client() -> None:
    """Release the connection. Call from the FastAPI shutdown hook."""
    if get_client.cache_info().currsize:
        get_client().close()
        get_client.cache_clear()
