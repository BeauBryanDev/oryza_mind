from __future__ import annotations

import os

import numpy as np
import pytest

# Set before app.core.config is imported: Settings requires these and env vars
# win over the real .env, so tests never touch live credentials.
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("WEAVIATE_URL", "http://localhost:8080")
os.environ.setdefault("WEAVIATE_API_KEY", "test-key")
# Keeps the startup warm-up from downloading e5 in the offline suite.
os.environ.setdefault("WARMUP_ENCODER", "false")

from app.core.config import get_settings


@pytest.fixture
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def bgr_image() -> np.ndarray:
    """Square BGR frame with a bright block, so resizes are visible."""
    img = np.full((640, 640, 3), 40, dtype=np.uint8)
    img[100:300, 150:400] = (10, 200, 250)
    return img


@pytest.fixture
def wide_bgr_image() -> np.ndarray:
    """Non-square frame, where letterbox padding and offsets show up."""
    img = np.full((480, 1280, 3), 60, dtype=np.uint8)
    img[50:200, 300:900] = (200, 30, 30)
    return img


@pytest.fixture
def boxes() -> np.ndarray:
    return np.array(
        [
            [0.0, 0.0, 10.0, 10.0],
            [5.0, 0.0, 15.0, 10.0],
            [100.0, 100.0, 110.0, 110.0],
        ],
        dtype=np.float32,
    )
