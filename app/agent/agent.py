
from __future__ import annotations

import logging
import time
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts import vision_context
from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.exceptions import AgentError
from app.rag.prompts import SYSTEM_PROMPT, format_context
from app.rag.retriever import RetrievalIntent, RetrievedChunk, retrieve
from app.schemas.chat import ChatTurn, Role
# tools for the agent
from app.tools.products_tool import ( format_for_model, 
                                     search_agrochemical_products, 
                                     search_products_tool )
from app.tools.check_plant_health_status import check_plant_health_status, check_plant_health_tool
from app.tools.recommend_crop import recommend_crop, recommend_crop_tool
from app.tools.fedearroz_tools import ( colombia_rice_price_tool,
                                       get_colombia_rice_price,
                                       get_rice_consumption,
                                       get_rice_planted_area,
                                       get_rice_production_costs,
                                       rice_consumption_tool,
                                       rice_planted_area_tool,
                                       rice_production_costs_tool )
from app.tools.rice_fertilizer import recommend_fertilizer_tool, recommend_rice_fertilizer
from app.tools.rice_price_tool import get_rice_price, get_rice_price_tool
from app.tools.weather_tool import get_crop_weather


logger = logging.getLogger(__name__)
"""
OryzaMind Agent[Gemini] answer chain: retrieve, then generate.

"""
RETRIEVAL_TOP_K = 5 # Had better to check thisnumber fits or not for retrieval
# Per class when several are detected, so a 3-disease leaf stays near the
# single-disease context size instead of tripling it.
PER_DISEASE_TOP_K = 2
# YOLo vision model was never perfect, so I will use the same number of results
MAX_TOOL_ROUNDS = 3
TOOLS = [search_products_tool, get_crop_weather, recommend_fertilizer_tool, recommend_crop_tool,
         check_plant_health_tool, get_rice_price_tool, colombia_rice_price_tool,
         rice_production_costs_tool, rice_planted_area_tool, rice_consumption_tool]
# Dispatch by tool name to the plain function, so the loop keeps the rows as
# dicts for the response while the model gets the JSON string.
TOOL_FUNCS = {
    search_products_tool.name: search_agrochemical_products,
    get_crop_weather.name: get_crop_weather.func,  # .func is the raw callable, not the StructuredTool wrapper
    recommend_fertilizer_tool.name: recommend_rice_fertilizer,
    recommend_crop_tool.name: recommend_crop,
    check_plant_health_tool.name: check_plant_health_status,
    get_rice_price_tool.name: get_rice_price,
    colombia_rice_price_tool.name: get_colombia_rice_price,
    rice_production_costs_tool.name: get_rice_production_costs,
    rice_planted_area_tool.name: get_rice_planted_area,
    rice_consumption_tool.name: get_rice_consumption,
}
# Tools whose result is a plain string handed to the model as-is. Products is
# the exception: it returns rows that also land on the response.
STRING_TOOLS = {get_crop_weather.name, 
                recommend_fertilizer_tool.name, recommend_crop_tool.name,
                check_plant_health_tool.name, get_rice_price_tool.name,
                colombia_rice_price_tool.name, rice_production_costs_tool.name,
                rice_planted_area_tool.name, rice_consumption_tool.name}

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
        timeout=settings.gemini_timeout,
        max_retries=settings.gemini_max_retries,
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
    # Most likley it is the conection to the Weaviate Cluster for VectorDB store 
    # I will deal with it later and bear with the latency for now on the model
    # I wil not mess with embeddings, it is makeing hard time to debug. 
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

    # Consent floor, enforced in code not prompt: the product tool can only run
    # in reply to something the assistant already said, so the first turn can
    # offer a lookup but never perform one.
    allow_tools = any(t.role is Role.ASSISTANT for t in history or [])
    response = _generate_with_tools(messages, state, allow_tools)

    # langchain-core 1.x returns content as a list of blocks; text joins the text ones.
    reply = (response.text or "").strip()

    if not reply:

        raise AgentError("The agent returned an empty response.")

    state.answer = reply
    logger.info("answered from %d retrieved chunk(s), %d product(s)", 
                len(chunks), len(state.products))

    return reply, chunks


def _generate_with_tools(messages: list, 
                         state: AgentState,  # the agent state carried through one turn
                         allow_tools: bool = True
                         ) -> AIMessage:
    """
    Run the model, executing tool calls until it answers in prose.

    Literature retrieval already happened before this loop and is not a tool:
    the model may decide to look up products, it may not decide to skip the
    corpus. Tool results are appended as ToolMessages; the AIMessage carrying
    the call is kept verbatim so Gemini's thought_signature travels back with it.
    """
    llm = get_llm().bind_tools(TOOLS) if allow_tools else get_llm()
    seen_ids = {p["id"] for p in state.products}

    for round_no in range(MAX_TOOL_ROUNDS + 1):
        # Timed, because a slow turn is otherwise invisible: the client times out
        # while this line is still waiting and the logs jump straight to silence.
        started = time.perf_counter()
        try:
            response = llm.invoke(messages)

        except Exception as exc:

            logger.error("llm round %d failed after %.1fs: %s",
                         round_no, time.perf_counter() - started, exc)
            raise AgentError(str(exc)) from exc

        logger.info("llm round %d: %.1fs, %d tool call(s)",
                    round_no, time.perf_counter() - started, len(response.tool_calls))

        if not response.tool_calls:
            return response

        messages.append(response)
        
        for call in response.tool_calls:
            
            func = TOOL_FUNCS.get(call["name"])
            
            if func is None:
                
                content = f"Unknown tool {call['name']}."
                
            else:
                try:
                    result = func(**call["args"])
                    
                except Exception:
                    logger.exception("tool %s failed", call["name"])
                    result = None
                    content = "The tool is unavailable right now."

                if result is None:
                    pass  # content already set above
                
                elif call["name"] in STRING_TOOLS:
                    content = result
                    logger.info("tool %s %s -> string result", call["name"], call["args"])
                else:
                    # Products tool returns list[dict] — track ids and format.
                    rows = result
                    for row in rows:
                        
                        if row["id"] not in seen_ids:
                            
                            seen_ids.add(row["id"])
                            state.products.append(row)
                            
                    content = format_for_model(rows)
                    
            messages.append(ToolMessage(content=content, 
                                        tool_call_id=call["id"]))

    # Out of rounds: answer from what was gathered, with tools withheld.
    try:
        
        return get_llm().invoke(messages)
    
    except Exception as exc:
        
        logger.exception("generation failed after tool rounds")
        raise AgentError(str(exc)) from exc
