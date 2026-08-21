
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import CLASS_NAMES, Settings
from app.utils.nms import batched_nms
from app.utils.preprocessing import LetterboxInfo, scale_boxes
"""Raw model output to filtered detections."""

NUM_CLASSES = len(CLASS_NAMES)
NUM_MASK_COEFFS = 32


@dataclass
class RawDetections:
    boxes: np.ndarray  # (n, 4) xyxy, original image pixels
    scores: np.ndarray  # (n,)
    class_ids: np.ndarray  # (n,)
    mask_coeffs: np.ndarray  # (n, 32)


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    
    out = np.empty_like(boxes)
    half_w, half_h = boxes[:, 2] / 2, boxes[:, 3] / 2
    
    out[:, 0] = boxes[:, 0] - half_w
    out[:, 1] = boxes[:, 1] - half_h
    out[:, 2] = boxes[:, 0] + half_w
    out[:, 3] = boxes[:, 1] + half_h
    
    return out


def parse_output(
    output0: np.ndarray,
    info: LetterboxInfo,
    settings: Settings,
) -> RawDetections:
    """
    Decode output0 (1, 42, 8400) into detections in original image space.

    Rows are 4 box + 6 class scores + 32 mask coefficients.
    """
    preds = output0[0].T  # (8400, 42)
    boxes_xywh = preds[:, :4]
    class_scores = preds[:, 4 : 4 + NUM_CLASSES]
    coeffs = preds[:, 4 + NUM_CLASSES :] # Tensor (1, 32, 160, 160)

    class_ids = class_scores.argmax(axis=1)
    scores = class_scores.max(axis=1)

    # Per-class threshold, not one global value: the low-recall classes are
    # deliberately allowed weaker detections.
    thresholds = np.array(  # (NUM_CLASSES,) it was a difficult dataset traning day
        [settings.confidence_threshold_for(CLASS_NAMES[i]) for i in range(NUM_CLASSES)],
        dtype=np.float32, # Actually the dataset was bleeding dificulties
        # By the way I made the maths manually and this is the fun part
    ) #  per-class threshold, not one global value
    keep = scores >= thresholds[class_ids]
    
    if not keep.any():
        
        empty = np.empty((0, 4), dtype=np.float32)
        
        return RawDetections(
            empty,
            np.empty(0, dtype=np.float32),
            np.empty(0, dtype=np.int64),
            np.empty((0, NUM_MASK_COEFFS), dtype=np.float32),
        )
    # The model outputs a single box per class, so we can use the same code for
    # both the YOLOv8 and EfficientNetB0 models.
    boxes = xywh_to_xyxy(boxes_xywh[keep])
    scores, class_ids, coeffs = scores[keep], class_ids[keep], coeffs[keep]

    kept = batched_nms(boxes, scores, class_ids, settings.yolo_iou_threshold)
    idx = np.array(kept, dtype=np.int64)

    return RawDetections(
        
        boxes=scale_boxes(boxes[idx], info),
        scores=scores[idx],
        class_ids=class_ids[idx],
        mask_coeffs=coeffs[idx],
        
    )
