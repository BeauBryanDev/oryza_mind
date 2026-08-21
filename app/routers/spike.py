
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import InvalidImageError
from app.routers.uploads import collect_images
from app.schemas.spike import SpikeResult
from app.services.spike_service import MAX_IMAGES, classify

logger = logging.getLogger(__name__)

router = APIRouter(tags=["spike"])

# Make sure the CNN model is loaded .
@router.post("/spike", response_model=SpikeResult)
async def classify_spikes(request: Request) -> SpikeResult:
    
    images = await collect_images(request, MAX_IMAGES)
    
    if not images:
        
        raise InvalidImageError("No image was uploaded.")

    logger.info("spike: %d image(s)", len(images))
    # ONNX inference only, no LLM call, but still blocking.
    return await run_in_threadpool(classify, images)
