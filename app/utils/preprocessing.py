
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image
"""Image to model tensor. Ultralytics letterbox convention."""

PAD_VALUE = 114  # Ultralytics letterbox grey.


@dataclass(frozen=True)
class LetterboxInfo:
    """Everything needed to map model coordinates back to the original image."""

    scale: float
    pad_x: float
    pad_y: float
    orig_w: int
    orig_h: int


def letterbox(
    image: np.ndarray, size: int = 640
) -> tuple[np.ndarray, LetterboxInfo]:
    """Resize preserving aspect ratio, pad to a square."""
    h, w = image.shape[:2]
    scale = min(size / w, size / h)
    new_w, new_h = round(w * scale), round(h * scale)
    # Resize and pad to a square, using the Ultralytics letterbox convention.
    # The model expects a square input, so the model can be resized directly.
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    pad_x, pad_y = (size - new_w) / 2, (size - new_h) / 2
    top, left = int(round(pad_y - 0.1)), int(round(pad_x - 0.1))
    canvas[top : top + new_h, left : left + new_w] = resized

    return canvas, LetterboxInfo(scale, pad_x, pad_y, w, h)


def to_tensor(image_bgr: np.ndarray, size: int = 640) -> tuple[np.ndarray, LetterboxInfo]:
    """BGR uint8 image to NCHW float32 in [0,1], RGB order."""
    padded, info = letterbox(image_bgr, size)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    tensor = rgb.astype(np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]
    
    return np.ascontiguousarray(tensor), info


def to_spike_tensor(image_bgr: np.ndarray, size: int = 640) -> np.ndarray:
    """BGR uint8 image to NHWC float32 raw [0,255], RGB order.

    A plain stretch, not a letterbox: the Keras training pipeline resized
    directly, and padding grey bars in would shift the input distribution.
    Rescaling and ImageNet normalization are baked into the ONNX graph, so the
    pixels must stay raw [0,255] here.
    
    """
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    resized = Image.fromarray(rgb).resize((size, size), Image.BILINEAR)
    
    return np.ascontiguousarray(np.asarray(resized, dtype=np.float32)[np.newaxis, ...])


def scale_boxes(boxes: np.ndarray, info: LetterboxInfo) -> np.ndarray:
    """Undo letterbox: model xyxy back to original image pixels."""
    if boxes.size == 0:
        return boxes
    
    out = boxes.copy()
    out[:, [0, 2]] = (out[:, [0, 2]] - info.pad_x) / info.scale
    out[:, [1, 3]] = (out[:, [1, 3]] - info.pad_y) / info.scale
    out[:, [0, 2]] = out[:, [0, 2]].clip(0, info.orig_w)
    out[:, [1, 3]] = out[:, [1, 3]].clip(0, info.orig_h)
    
    return out
