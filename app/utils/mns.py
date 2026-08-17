"""Non-Maximum Suppression. Named mns.py to match the existing module layout."""

from __future__ import annotations

import numpy as np

from app.utils.iou import iou_xyxy


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy NMS over a single class. Returns kept indices, best score first."""
    if boxes.size == 0:
        return []

    order = np.argsort(scores)[::-1]
    keep: list[int] = []
    
    while order.size:
        
        best = int(order[0])
        keep.append(best)
        
        if order.size == 1:
            break
        
        overlaps = iou_xyxy(boxes[best], boxes[order[1:]])
        order = order[1:][overlaps < iou_threshold]
        
    return keep


def batched_nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    iou_threshold: float,
) -> list[int]:
    """NMS per class. Lesions of different diseases may legitimately overlap,
    so suppression never crosses class boundaries."""
    keep: list[int] = []
    
    for cid in np.unique(class_ids):
        idx = np.flatnonzero(class_ids == cid)
        kept = nms(boxes[idx], scores[idx], iou_threshold)
        keep.extend(idx[k] for k in kept)
        
    return sorted(keep, key=lambda i: -scores[i])
