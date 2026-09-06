
from __future__ import annotations

import enum

from pydantic import Field

from app.schemas.analysis import AnalysisResult
from app.schemas.common import CamelModel


class Role(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatTurn(CamelModel):
    role: Role
    content: str
    
    
class ChatHistory(CamelModel):
    history: list[ChatTurn]


class ChatRequest(CamelModel):
    
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list)
    analysis: AnalysisResult | None = None


class Citation(CamelModel):
    """Provenance for a retrieved chunk, so an answer can be traced to a page."""
    # citatiosn came form my RAG and it came from IRRI , so I made it a string
    chunk_id: str
    document_title: str
    organization: str | None = None
    page_start: int | None = None
    source_url: str | None = None


class ProductHit(CamelModel):
    """
    A catalogue product the agent looked up at the user's request.

    No prices: the catalogue stores them, but this app informs, it does not sell.
    """
    id: str
    source: str
    name: str
    category: str | None = None
    active_ingredient: str | None = None
    product_url: str | None = None
    technical_sheet_url: str | None = None
    safety_sheet_url: str | None = None


class ChatResponse(CamelModel):
    reply: str
    suggestions: list[str] | None = None
    # Extra to the TS type, which ignores unknown fields. Lets the UI show
    # sources later without a backend change.
    citations: list[Citation] = Field(default_factory=list)
    # Products returned by the search tool this turn, so the UI can render
    # cards with sheet links instead of parsing them out of the prose.
    products: list[ProductHit] = Field(default_factory=list)
