
from __future__ import annotations

import logging

from fastapi import APIRouter, Header
from starlette.concurrency import run_in_threadpool

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat as chat_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])
"""POST /chat. One agent turn, with the prior analysis as context."""

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> ChatResponse:
    
    logger.info("chat: %d chars, analysis=%s", len(request.message), request.analysis is not None)
    # The agent chain is synchronous, and so is the embedding call inside its
    # retrieval tool.
    return await run_in_threadpool(chat_service, request, session_id)
