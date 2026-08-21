
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import get_settings
from app.core.exceptions import OryzaError
from app.core.logging import setup_logging
from app.rag.vectorstore import close_client
from app.routers import analysis_router, chat_router, health_router, spike_router
"""FastAPI application main entry file. Served at the root on port 8005."""

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("OryzaMind %s starting | env=%s", __version__, settings.environment)
    # The ONNX session and the e5 encoder load lazily on first use. Left that
    # way deliberately: eager loading would add ~30s to startup and make an
    # unreachable Weaviate a boot failure rather than a degraded /health.
    try:
        yield
        
    finally:
        close_client()
        logger.info("shutdown complete")


app = FastAPI(
    title="OryzaMind API",
    version=__version__,
    description="Rice leaf disease detection and agronomic guidance.",
    lifespan=lifespan,
)
# CORS Handling here  to avoid headless browser errors and to allow the Vite dev frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OryzaError)
async def oryza_error_handler(request: Request, exc: OryzaError) -> JSONResponse:
 
    logger.warning("%s on %s: %s", exc.code, request.url.path, exc.message)
    
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    
    logger.exception("unhandled error on %s", request.url.path)
    
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred.", "code": "internal_error"},
    )

# HTTP routes
app.include_router(health_router)
app.include_router(analysis_router)
app.include_router(spike_router)
app.include_router(chat_router)
