
from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
import onnxruntime as ort

from app.core.config import get_settings
from app.core.exceptions import InferenceError, ModelNotLoadedError


logger = logging.getLogger(__name__)


EXPECTED_INPUT = (1, 3, 640, 640)
EXPECTED_CHANNELS = 42  # 4 box + 6 classes + 32 mask coefficients
EXPECTED_PROTOS = 32
"""ONNX Runtime wrapper for the YOLO segmentation model."""

class VisionModel:
    # this is my YOLO SEG  model , it isued yo be the only single model  
    # but now there is an EfficientNetB0 model that handle rice spikes health 
    def __init__(self, session: ort.InferenceSession):  # the name preseverd for the future
        
        self.session = session
        
        self.input_name = session.get_inputs()[0].name
        
        self.output_names = [o.name for o in session.get_outputs()]

    def run(self, tensor: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Returns (output0, output1): detections and mask prototypes."""
        try:
            out0, out1 = self.session.run(self.output_names, {self.input_name: tensor})
            
        except Exception as exc:
            
            logger.exception("onnx inference failed")
            
            raise InferenceError(str(exc)) from exc
        
        return out0, out1


@lru_cache
def get_model() -> VisionModel:
    # This is a singleton, so it is safe to cache.
    settings = get_settings()
    path = settings.yolo_model_path
    
    if not path.exists():
        
        raise ModelNotLoadedError(f"Model file not found at {path}")

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    shape = session.get_inputs()[0].shape
    
    if tuple(shape) != EXPECTED_INPUT:
        
        raise ModelNotLoadedError(f"Unexpected input shape {shape}, want {EXPECTED_INPUT}")
    
    out0, out1 = session.get_outputs()
    # A retrained model with a different class count changes output0's channel
    # dimension. Fail here rather than decoding garbage into confident boxes.
    if out0.shape[1] != EXPECTED_CHANNELS:
        
        raise ModelNotLoadedError(
            f"output0 has {out0.shape[1]} channels, expected {EXPECTED_CHANNELS}. "
            "The model's class count may not match CLASS_NAMES."
        )
    if out1.shape[1] != EXPECTED_PROTOS:
        raise ModelNotLoadedError(f"output1 has {out1.shape[1]} prototypes, expected 32")

    logger.info("vision model loaded from %s", path)
    
    return VisionModel(session)


def is_model_available() -> bool:
    
    try:
        get_model()
        
        return True
    
    except Exception:
        
        return False
