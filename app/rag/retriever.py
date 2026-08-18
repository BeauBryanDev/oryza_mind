

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any

from weaviate.classes.query import Filter, MetadataQuery

from app.core.config import CLASS_NAMES, get_settings
from app.rag.vectorstore import embed_query, get_collection
"""
Retrieval against the live OryzaMindChunk collection.
"""
logger = logging.getLogger(__name__)

# Excluded alongside the per-chunk flag: that flag could be missed on a future
# ingest, this is per-source.
SCREENING_DOCUMENT_TYPE = "screening_manual"

RETURN_PROPERTIES = [
    "chunk_id",
    "text",
    "source_document",
    "document_title",
    "organization",
    "source_url",
    "document_type",
    "chunk_type",
    "disease_name",
    "section",
    "page_start",
    "page_end",
    "is_inoculation_protocol",
    "recommended_treatment",
    "active_ingredient",
    "dosage",
    "crop_stage",
]


class RetrievalIntent(enum.Enum):
    """TREATMENT and REFERENCE both exclude inoculation protocols.

    UNFILTERED is for corpus diagnostics only, never a user-facing answer.
    """

    TREATMENT = "treatment"
    REFERENCE = "reference"
    UNFILTERED = "unfiltered"


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    source_document: str
    document_title: str | None
    organization: str | None
    source_url: str | None
    document_type: str | None
    chunk_type: str | None
    disease_name: str | None
    section: str | None
    page_start: int | None
    page_end: int | None
    is_inoculation_protocol: bool
    recommended_treatment: str | None = None
    active_ingredient: str | None = None
    dosage: str | None = None
    crop_stage: str | None = None
    score: float | None = None

    @property
    def citation(self) -> str:
        org = self.organization or "unknown source"
        title = self.document_title or self.source_document
        
        if self.page_start:
            
            return f"{title} ({org}), p. {self.page_start}"
        
        return f"{title} ({org})"


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    query: str
    disease_name: str | None
    intent: RetrievalIntent
    filters_applied: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.chunks)


def _build_filter(
    disease_name: str | None,
    intent: RetrievalIntent,
) -> tuple[Any | None, list[str]]:
    
    """Assemble the metadata filter and a human-readable record of it."""
    clauses: list[Any] = []
    applied: list[str] = []

    if intent is not RetrievalIntent.UNFILTERED:
        # SAFETY RULE 
        clauses.append(Filter.by_property("is_inoculation_protocol").equal(False))
        applied.append("is_inoculation_protocol == False")
        clauses.append( # do not says users how to inoculate rice plants, it is not a treatment
            Filter.by_property("document_type").not_equal(SCREENING_DOCUMENT_TYPE)
        )
        applied.append(f"document_type != {SCREENING_DOCUMENT_TYPE}")

    if disease_name is not None:
        clauses.append(Filter.by_property("disease_name").equal(disease_name))
        applied.append(f"disease_name == {disease_name}")

    if not clauses:
        
        return None, applied
    
    if len(clauses) == 1:
        
        return clauses[0], applied
    
    return Filter.all_of(clauses), applied


def retrieve(
    query: str,
    disease_name: str | None = None,
    intent: RetrievalIntent = RetrievalIntent.TREATMENT,
    top_k: int | None = None,
    query_vector: list[float] | None = None,
) -> RetrievalResult:
    """Vector search with the safety filters applied.

    query: raw text; embed_query adds the `query: ` prefix, do not add it here.
    disease_name: a canonical class, or None to search the whole corpus. Always
    pass it for Narrow_Brown -- only 13 chunks, mostly taxonomy, so an
    unfiltered query returns morphology instead of management.
    """
    settings = get_settings()

    if disease_name is not None and disease_name not in CLASS_NAMES:
        raise ValueError(
            f"disease_name {disease_name!r} is not a canonical class. "
            f"Expected one of {list(CLASS_NAMES)}. These strings are matched "
            "verbatim against Weaviate metadata; a near-miss silently returns "
            "nothing rather than erroring."
        )

    k = top_k or settings.retrieval_top_k
    k = max(1, min(k, settings.retrieval_max_top_k))

    where, applied = _build_filter(disease_name, intent)
    # A caller that batch-embedded several queries passes the vector in; the
    # `query: ` prefix was applied by embed_queries, so SAFETY RULE 1 holds
    # either way.
    vector = query_vector if query_vector is not None else embed_query(query, settings)

    response = get_collection().query.near_vector(
        near_vector=vector,
        limit=k,
        filters=where,
        return_properties=RETURN_PROPERTIES,
        return_metadata=MetadataQuery(distance=True),
    )

    chunks: list[RetrievedChunk] = []
    
    for obj in response.objects:
        props = obj.properties
        distance = obj.metadata.distance if obj.metadata else None
        chunk = RetrievedChunk(
            chunk_id=props.get("chunk_id", ""),
            text=props.get("text", ""),
            source_document=props.get("source_document", ""),
            document_title=props.get("document_title"),
            organization=props.get("organization"),
            source_url=props.get("source_url"),
            document_type=props.get("document_type"),
            chunk_type=props.get("chunk_type"),
            disease_name=props.get("disease_name"),
            section=props.get("section"),
            page_start=props.get("page_start"),
            page_end=props.get("page_end"),
            is_inoculation_protocol=bool(props.get("is_inoculation_protocol", False)),
            recommended_treatment=props.get("recommended_treatment"),
            active_ingredient=props.get("active_ingredient"),
            dosage=props.get("dosage"),
            crop_stage=props.get("crop_stage"),
            score=(1.0 - distance) if distance is not None else None,
        )

        # If this ever fires, the server-side filter failed. Drop and log loudly.
        if intent is not RetrievalIntent.UNFILTERED and chunk.is_inoculation_protocol:
            logger.error(
                "inoculation chunk %s passed the %s filter; dropped client-side",
                chunk.chunk_id,
                intent.value,
            )
            continue

        chunks.append(chunk)

    logger.info(
        "retrieved %d/%d chunks | disease=%s intent=%s filters=[%s]",
        len(chunks),
        k,
        disease_name,
        intent.value,
        "; ".join(applied) or "none",
    )
    return RetrievalResult(
        chunks=chunks,
        query=query,
        disease_name=disease_name,
        intent=intent,
        filters_applied=applied,
    )
