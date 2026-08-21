from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
import onnxruntime as ort

from app.core.config import get_settings
from app.core.exceptions import InferenceError, ModelNotLoadedError
"""ONNX Runtime wrapper for the rice spike binary classifier."""

logger = logging.getLogger(__name__)

# NHWC, unlike the YOLO model's NCHW: this graph came from Keras via tf2onnx.
EXPECTED_INPUT = (1, 640, 640, 3)
EXPECTED_OUTPUT = (1, 1)


class SpikeModel:
    def __init__(self, session: ort.InferenceSession):
        
        self.session = session
        self.input_name = session.get_inputs()[0].name
        self.output_name = session.get_outputs()[0].name

    def run(self, tensor: np.ndarray) -> float:
        """Returns the sigmoid score, P(unhealthy)."""
        try:
            out = self.session.run([self.output_name], {self.input_name: tensor})[0]
            
        except Exception as exc:
            
            logger.exception("spike onnx inference failed")
            raise InferenceError(str(exc)) from exc

        return float(np.asarray(out).reshape(-1)[0])


@lru_cache
def get_spike_model() -> SpikeModel:
    """Loads the ONNX model from disk."""
    settings = get_settings()
    path = settings.spike_model_path

    if not path.exists():
        raise ModelNotLoadedError(f"Spike model file not found at {path}")

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    shape = tuple(session.get_inputs()[0].shape)
    if shape != EXPECTED_INPUT:
        raise ModelNotLoadedError(
            f"Spike model input shape {shape}, want {EXPECTED_INPUT}"
        )

    out_shape = tuple(session.get_outputs()[0].shape)
 
    if out_shape != EXPECTED_OUTPUT:
        
        raise ModelNotLoadedError(
            f"Spike model output shape {out_shape}, want {EXPECTED_OUTPUT}. "
            "This head must stay a single sigmoid unit."
        )

    logger.info("spike model loaded from %s", path)
    
    return SpikeModel(session)


def is_spike_model_available() -> bool:
    
    try:
        get_spike_model()
        return True
    
    except Exception:
        
        return False
