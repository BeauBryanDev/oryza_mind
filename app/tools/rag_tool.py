
from __future__ import annotations

import logging
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import CLASS_NAMES
from app.rag.prompts import format_context
from app.rag.retriever import RetrievalIntent, retrieve
"""LangChain tool exposing the knowledge base to the agent."""

logger = logging.getLogger(__name__)


DiseaseClass = Literal[
    "Bacterial_Leaf_Blight",
    "Brown_Spot",
    "Leaf_Blast",
    "Narrow_Brown",
    "Rice_Tungro",
    "Sheath_Blight",
]

TOOL_DESCRIPTION = (
    "Searches agronomic reference manuals for treatment and management "
    "information about a specific rice disease. Use this before giving any "
    "treatment recommendation -- never state a treatment from memory without "
    "retrieving it first."
)


class RetrieveTreatmentInput(BaseModel):
    
    disease_name: DiseaseClass = Field(
        description="Must match a class name from run_rice_diagnosis output."
    )
    query: str = Field(
        
        description=(
            "Specific aspect to search, e.g. 'chemical treatment', "
            "'organic control', 'prevention timing'."
        )
    )


def _retrieve_treatment_info(disease_name: str, query: str) -> str:
    # Intent is fixed at TREATMENT and not exposed as a tool argument: the model
    # must not be able to widen its own retrieval to inoculation protocols.
    try:
        result = retrieve(
            query=query,
            disease_name=disease_name,
            intent=RetrievalIntent.TREATMENT,
        )
        
    except ValueError as exc:
        return f"Invalid disease name. {exc}"
    
    except Exception:
        logger.exception("retrieval failed for %s / %r", disease_name, query)
        return "The knowledge base is unavailable. answer from memory."

    if not result.chunks:
        return (
            f"No passages found for {disease_name} on '{query}'. then you answer "
            "from your own knowledge, "
        )

    logger.info(
        "rag_tool: %s / %r -> %d chunks", disease_name, query, len(result.chunks)
    )
    return format_context(result.chunks)


retrieve_treatment_info = StructuredTool.from_function(
    func=_retrieve_treatment_info,
    name="retrieve_treatment_info",
    description=TOOL_DESCRIPTION,
    args_schema=RetrieveTreatmentInput,
)


def get_rag_tools() -> list[StructuredTool]:
    return [retrieve_treatment_info]


# Guards the Literal against CLASS_NAMES drifting apart.
assert set(DiseaseClass.__args__) == set(CLASS_NAMES)
