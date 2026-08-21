
from __future__ import annotations

import logging
import uuid

from app.agent.agent import run_agent
from app.agent.state import AgentState
from app.core.exceptions import AgentError
from app.schemas.analysis import AnalysisResult
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.rag.retriever import RetrievedChunk
from app.schemas.common import PipelineStage
"""Chat turns against the agent, with the current analysis as context."""

logger = logging.getLogger(__name__)


FALLBACK_SUGGESTIONS = [
    "What treatment do you recommend?",
    "How do I prevent this next season?",
    "Is this severe enough to spray now?",
]


def _state_from(analysis: AnalysisResult | None, 
                session_id: str
                ) -> AgentState:
    
    state = AgentState(session_id=session_id, stage=PipelineStage.ANALYZING)
    
    if analysis and analysis.primary_disease:
        
        p = analysis.primary_disease
        state.disease_name = p.name
        state.diseases = [j.name for j in analysis.diseases]
        state.confidence = p.confidence
        state.severity = analysis.overall_severity
        state.affected_ratio = analysis.overall_affected_ratio
        state.lesion_count = sum(l.lesion_count for l in analysis.diseases)
        
    return state


def _citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    """One citation per chunk the answer was grounded on."""
    return [
        Citation(
            chunk_id=c.chunk_id,
            document_title=c.document_title or c.source_document,
            organization=c.organization,
            page_start=c.page_start,
            source_url=c.source_url,
        )
        for c in chunks
    ]


def chat(request: ChatRequest, 
         session_id: str | None = None
         ) -> ChatResponse:
    
    sid = session_id or str(uuid.uuid4())
    state = _state_from(request.analysis, sid)

    try:
        reply, chunks = run_agent(request.message, state, request.history)
        
    except AgentError:
        raise
    
    except Exception as exc:
        
        logger.exception("chat failed")
        raise AgentError(str(exc)) from exc

    if not chunks:
        logger.info("answered with no retrieved context")

    return ChatResponse(
        reply=reply,
        suggestions=FALLBACK_SUGGESTIONS if request.analysis else None,
        citations=_citations(chunks),
    )
