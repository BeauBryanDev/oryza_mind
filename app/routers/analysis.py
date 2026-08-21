
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import InvalidImageError
from app.routers.uploads import collect_images
from app.schemas.analysis import AnalysisResult
from app.services.analysis_service import MAX_IMAGES, analyze

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_images(request: Request) -> AnalysisResult:
    
    images = await collect_images(request, MAX_IMAGES)
    
    if not images:
        raise InvalidImageError("No image was uploaded.")
    #TODO: IT IS TAKING LONG TIME, I MUST SEE WHY IS DELAYED
    logger.info("analyze: %d image(s)", len(images))
    # ONNX inference plus a Gemini call. Blocking, so off the event loop.
    return await run_in_threadpool(analyze, images)
