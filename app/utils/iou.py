
from __future__ import annotations
"""Intersection over Union."""

import numpy as np
# this is critical for detection
# I made the maths manually and this is the fun part
def iou_xyxy(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    """IoU of one box against many. Both in xyxy pixel coordinates."""
    if boxes.size == 0:
        return np.empty(0, dtype=np.float32)
    #  get the coordinates of the bounding boxes
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])

    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union = area + areas - inter
    # Degenerate boxes give union 0; report no overlap rather than dividing.
    return np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0).astype(np.float32)


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    """IoU of two boolean masks of the same shape."""
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    #  Degenerate boxes give union 0; report no overlap rather than dividing.
    return float(inter / union) if union else 0.0
