
from __future__ import annotations

import logging

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app import __version__
# load vision model, spike model and weaviate client
from app.core.load_spike_model import is_spike_model_available
from app.core.load_vision_model import is_model_available
from app.rag.vectorstore import get_client
from app.schemas.common import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def _weaviate_ready() -> bool:
    try:
        return get_client().is_ready()
    
    except Exception:
        logger.warning("weaviate not reachable", exc_info=True)
        return False


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    # Both checks touch blocking clients, and the Weaviate one is a network
    # round trip. Always 200: the payload reports degradation.
    model_loaded = await run_in_threadpool(is_model_available)
    spike_model_loaded = await run_in_threadpool(is_spike_model_available)
    weaviate_ready = await run_in_threadpool(_weaviate_ready)

    return HealthResponse(
        status="ok" if (model_loaded and weaviate_ready) else "degraded",
        version=__version__,
        model_loaded=model_loaded,
        weaviate_ready=weaviate_ready,
        spike_model_loaded=spike_model_loaded,
    )
