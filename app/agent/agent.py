
from __future__ import annotations

import logging
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts import vision_context
from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.exceptions import AgentError
from app.rag.prompts import SYSTEM_PROMPT, format_context
from app.rag.retriever import RetrievalIntent, RetrievedChunk, retrieve
from app.schemas.chat import ChatTurn, Role

logger = logging.getLogger(__name__)
"""
OryzaMind Agent[Gemini] answer chain: retrieve, then generate.

"""
RETRIEVAL_TOP_K = 6
# Per class when several are detected, so a 3-disease leaf stays near the
# single-disease context size instead of tripling it.
PER_DISEASE_TOP_K = 4
# Acutally I do not see more than two dieases in a single leaf images 

@lru_cache
def get_llm() -> ChatGoogleGenerativeAI:
    
    settings = get_settings()
    
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        # Low but not zero: agronomic advice should be stable across identical
        # questions, and creative phrasing is not good here
        temperature=settings.temperature, 
        thinking_budget=settings.gemini_thinking_budget,
    )  

def _to_messages(history: list[ChatTurn]) -> list:
    
    out = []
    
    for turn in history:
        
        if turn.role is Role.USER:
            
            out.append(HumanMessage(content=turn.content))
            
        elif turn.role is Role.ASSISTANT:
            
            out.append(AIMessage(content=turn.content))
            
            
    return out


def _retrieve_for(message: str, 
                  state: AgentState
                  ) -> list[RetrievedChunk]:
    """
    Search the knowledge base for this turn.

    One pass per detected disease. A single pass filtered on the dominant class
    returns nothing for the others, and the grounding rule then forbids advising
    on them at all -- a co-infected leaf would silently get a plan for one
    disease. Diseases come from vision, never from the model, and TREATMENT
    intent keeps the inoculation filter on.
    """
    targets: list[str | None] = list(state.target_diseases) or [None]
    per_disease = PER_DISEASE_TOP_K if len(targets) > 1 else RETRIEVAL_TOP_K

    merged: dict[str, RetrievedChunk] = {}
    
    for target in targets:
        
        try:
            result = retrieve(
                query=message,
                disease_name=target,
                intent=RetrievalIntent.TREATMENT,
                top_k=per_disease,
            )
            
        except Exception:
            # One class failing must not lose the others.
            logger.exception("retrieval failed for %s; continuing", target)
            continue
        
        for chunk in result.chunks:
            # A chunk tagged with one disease can rank for another; keep the
            # first occurrence rather than duplicating it in the context.
            merged.setdefault(chunk.chunk_id, chunk)

    if not merged:
        # An answer with no sources is still safe: the prompt forbids answering
        # from general knowledge when the context is empty.
        logger.warning("no chunks retrieved for %s", targets)
        
    return list(merged.values())


def run_agent(
    message: str,
    state: AgentState,
    history: list[ChatTurn] | None = None,
    format_rule: str | None = None,
) -> tuple[str, list[RetrievedChunk]]:
    """
    Answer one turn. Returns the reply and the chunks it was grounded on.

    format_rule constrains the output shape for one caller only. /analyze uses it
    to get plain lines; chat passes nothing and keeps markdown.
    """
    #TODO: THIS IS TAKING LONG TIME, I MUST SEE WHY IS DELAYED
    chunks = _retrieve_for(message, state)
    state.retrieved = chunks

    system = "\n\n".join(
        part
        for part in [
            SYSTEM_PROMPT,
            format_rule,
            vision_context(state),
            "Retrieved passages:",
            format_context(chunks),
        ]
        if part # part is not None
    )
    messages = [SystemMessage(content=system), *_to_messages(history or []), 
                HumanMessage(content=message)]

    try:
        response = get_llm().invoke(messages)
        
    except Exception as exc:
        
        logger.exception("generation failed")
        
        raise AgentError(str(exc)) from exc

    reply = (response.content or "").strip()
    
    if not reply:
        
        raise AgentError("The agent returned an empty response.")

    state.answer = reply
    logger.info("answered from %d retrieved chunk(s)", len(chunks))
    
    return reply, chunks
