
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image
"""Image to model tensor. Ultralytics letterbox convention."""
# I do not want to install torch , Ultralytics over here
#  They are too heavy libraries for this project, 
#  I  use them during ML models training but not in backend production software
PAD_VALUE = 114  # Ultralytics letterbox grey.
# Hence we made everything manuall and this is the fun part

@dataclass(frozen=True)
class LetterboxInfo:
    """Everything needed to map model coordinates back to the original image."""
    # inference image should match what the model was trained on
    scale: float
    pad_x: float
    pad_y: float
    orig_w: int
    orig_h: int


def letterbox(
    image: np.ndarray, 
    size: int = 640
) -> tuple[np.ndarray, LetterboxInfo]:
    """Resize preserving aspect ratio, pad to a square."""
    h, w = image.shape[:2] #  get the image size
    scale = min(size / w, size / h) #  calculate the scale ratio
    new_w, new_h = round(w * scale), round(h * scale)
    # Resize and pad to a square, using the Ultralytics letterbox convention.
    # The model expects a square input, so the model can be resized directly.
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    #  paste the resized image onto the canvas
    pad_x, pad_y = (size - new_w) / 2, (size - new_h) / 2
    top, left = int(round(pad_y - 0.1)), int(round(pad_x - 0.1))
    canvas[top : top + new_h, left : left + new_w] = resized
    #  paste the letterbox onto the canvas
    return canvas, LetterboxInfo(scale, pad_x, pad_y, w, h)


def to_tensor(image_bgr: np.ndarray, 
              size: int = 640
              ) -> tuple[np.ndarray, LetterboxInfo]:
    """BGR uint8 image to NCHW float32 in [0,1], RGB order."""
    padded, info = letterbox(image_bgr, size)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    # this is the funny part, we need to convert the image to float32 in [0,1]
    #  and then swap the axes to NHWC, because my  model expects this.
    tensor = rgb.astype(np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]
    
    return np.ascontiguousarray(tensor), info


def to_spike_tensor(image_bgr: np.ndarray, size: int = 640) -> np.ndarray:
    """
    BGR uint8 image to NHWC float32 raw [0,255], RGB order.

    A plain stretch, not a letterbox: the Keras training pipeline resized
    directly, and padding grey bars in would shift the input distribution.
    Rescaling and ImageNet normalization are baked into the ONNX graph, so the
    pixels must stay raw [0,255] here.
    
    """
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    resized = Image.fromarray(rgb).resize((size, size), Image.BILINEAR)
    #  convert to float32 in [0,1]
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
