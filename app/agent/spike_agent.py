
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.agent import get_llm
from app.core.exceptions import AgentError
from app.rag.prompts import (
    RECOMMENDATION_FORMAT,
    SPIKE_DIAGNOSIS_PROMPT,
    SPIKE_NO_CONTEXT_FALLBACK,
    SPIKE_SYSTEM_PROMPT,
    format_context,
)
from app.rag.retriever import RetrievalIntent, RetrievedChunk, retrieve
from app.rag.vectorstore import embed_queries
from app.schemas.spike import SpikeLabel, SpikeResult
"""
Answer chain for the spike classifier. Retrieve, then generate.

Separate from agent.py because the input is different in kind. Vision gives the
leaf chain a  class it can filter Weaviate on; the spike model gives a
condition and no class at all. So retrieval here is a fan-out over the panicle
vocabulary with no disease_name filter, and the answer is a differential rather
than a plan for a known disease.
"""
logger = logging.getLogger(__name__)

PER_QUERY_TOP_K = 3
# Trimmed from 10: the six queries overlap heavily, so the tail was mostly
# near-duplicate Arkansas passages that cost LLM latency without adding cover.
MAX_CONTEXT_CHUNKS = 7

# Panicle diseases
UNHEALTHY_QUERIES = (
    "panicle blast neck blast neck rot management of rice ears",
    "grain discoloration unfilled and spotted rice grains causes and control",
    "false smut and kernel smut of rice panicles control",
    "sheath rot and bacterial panicle blight symptoms and management",
    "fungicide timing at booting and heading to protect the panicle",
    "nitrogen rate water management and cultivar choice to reduce panicle disease",
) # this camee from my chunks IRRI collections from the RAG 


HEALTHY_QUERIES = (
    "protecting rice panicles at booting and heading preventive practices",
    "cultural practices for healthy grain filling and ripening in paddy",
    "field scouting for panicle blast and grain discoloration before harvest",
) # My EfficientNetB0 model was trainned as Binary Classification, hennce it does not know 
# Panicles dieases ,I need to help it to understand them


def _retrieve_panicle(label: SpikeLabel) -> list[RetrievedChunk]:
    """
    Fan out over panicle queries and merge by chunk_id.

    TREATMENT intent throughout, so the inoculation filter stays on. The 2025
    manual's panicle inoculation procedures rank well on exactly this
    vocabulary, which is the whole reason the filter exists.
    """
    queries = UNHEALTHY_QUERIES if label is SpikeLabel.UNHEALTHY else HEALTHY_QUERIES

    # One batched forward pass for all the queries, then the network calls in
    # parallel. Encoding six queries separately dominated this function: the
    # encoder is CPU-bound and holds the GIL, so only the Weaviate round trips
    # are worth threading.
    vectors = embed_queries(list(queries))
    # TODO:  IT  is taking so long painfully time to answr, 
    # it is not my panicle model, it is the  RAG retieval + Agent to answer.
    # I got to see how ti fix this bleeding issue. 
    def _one(pair: tuple[str, list[float]]) -> list[RetrievedChunk]:
        query, vector = pair
        try:
            return retrieve(
                query=query,
                disease_name=None,
                intent=RetrievalIntent.TREATMENT,
                top_k=PER_QUERY_TOP_K,
                query_vector=vector,
            ).chunks
            
        except Exception:
            # One query failing must not lose the rest of the differential.
            logger.exception("spike retrieval failed for %r; continuing", query)
            return []

    # Order is restored below by score, so the pool does not make results
    # nondeterministic.
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        batches = list(pool.map(_one, zip(queries, vectors)))

    merged: dict[str, RetrievedChunk] = {}
    
    for batch in batches:
        
        for chunk in batch:
            
            merged.setdefault(chunk.chunk_id, chunk)

    chunks = list(merged.values())
    # Ranked across queries, so trimming keeps the best of each rather than
    # everything from the first.
    chunks.sort(key=lambda c: c.score or 0.0, reverse=True)
    
    return chunks[:MAX_CONTEXT_CHUNKS]


def _describe(result: SpikeResult) -> tuple[str, str]:
    
    verdict = (
        
        f"{result.unhealthy_count} of {result.total_count} panicles classified UNHEALTHY"
        if result.unhealthy_count
        
        else f"Good news! All {result.total_count} panicle(s) classified HEALTHY"
    )
    lines = []
    
    for p in result.predictions:
        
        name = p.filename or f"image {p.image_index + 1}"
        note = " (borderline, near the decision threshold)" if p.uncertain else ""
        lines.append(f"- {name}: {p.label.value} at {p.confidence:.1%} confidence{note}")
        
    return verdict, "\n".join(lines)


def run_spike_agent(result: SpikeResult) -> tuple[str, list[RetrievedChunk], bool]:
    """
    Returns (answer, chunks it was grounded on, grounded).

    grounded is False when the corpus returned nothing and the model answered
    from its own knowledge. The caller must surface that distinction -- an
    ungrounded answer carries no citations and no dosages by construction.
    """
    chunks = _retrieve_panicle(result.overall_label)
    grounded = bool(chunks)

    verdict, per_image = _describe(result)
    
    user_prompt = SPIKE_DIAGNOSIS_PROMPT.format(
        total=result.total_count,
        verdict=verdict,
        per_image=per_image,
        context=format_context(chunks) if grounded else "",
    )

    # Same shape rule as /analyze: the panel takes a string[] of sentences, so
    # markdown structure cannot survive the trip.
    system_parts = [SPIKE_SYSTEM_PROMPT, RECOMMENDATION_FORMAT]
    
    if not grounded:
        logger.warning("spike: no chunks retrieved, answering from model knowledge")
        system_parts.append(SPIKE_NO_CONTEXT_FALLBACK)

    messages = [
        SystemMessage(content="\n\n".join(system_parts)),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = get_llm().invoke(messages)
        
    except Exception as exc:
        
        logger.exception("spike generation failed")
        raise AgentError(str(exc)) from exc

    answer = (response.content or "").strip()
    
    if not answer:
        raise AgentError("The agent returned an empty response.")

    logger.info(
        "spike answered from %d chunk(s), grounded=%s", len(chunks), grounded
    )
    
    return answer, chunks, grounded
