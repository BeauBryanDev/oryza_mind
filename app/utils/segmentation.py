
from __future__ import annotations

import cv2
import numpy as np

from app.utils.postprocessing import RawDetections
from app.utils.preprocessing import LetterboxInfo
"""Mask prototypes plus coefficients to per-instance binary masks."""

def _sigmoid(x: np.ndarray) -> np.ndarray:
    
    return 1.0 / (1.0 + np.exp(-x))


def build_masks(
    detections: RawDetections,
    protos: np.ndarray,
    info: LetterboxInfo,
    mask_threshold: float = 0.5,
) -> list[np.ndarray]:
    """
    One boolean mask per detection, at original image resolution.

    protos is output1, shape (1, 32, 160, 160).
    """
    if detections.boxes.size == 0:
        return []

    protos = protos[0]
    c, mh, mw = protos.shape
    # (n, 32) @ (32, mh*mw) -> (n, mh, mw)
    flat = detections.mask_coeffs @ protos.reshape(c, -1)
    masks = _sigmoid(flat).reshape(-1, mh, mw)

    # The prototype grid covers the letterboxed 640 square. Crop away the
    # padding before resizing, or masks land offset on non-square images.
    size = mh  # 160, square
    pad_x = info.pad_x / (640 / size)
    pad_y = info.pad_y / (640 / size)
    x0, y0 = int(round(pad_x)), int(round(pad_y))
    x1, y1 = size - x0, size - y0 # Critical part, if it does not match training image
    masks = masks[:, max(y0, 0) : max(y1, y0 + 1), max(x0, 0) : max(x1, x0 + 1)] # we failed to crop the masks

    out: list[np.ndarray] = []
    
    for i, m in enumerate(masks):
        full = cv2.resize(
            m, (info.orig_w, info.orig_h), interpolation=cv2.INTER_LINEAR
        )
        binary = full > mask_threshold
        # Ultralytics crops each mask to its own box; without this, prototype
        # bleed shows lesions where the detector never found one.
        x1b, y1b, x2b, y2b = detections.boxes[i].astype(int)
        crop = np.zeros_like(binary)
        crop[max(y1b, 0) : y2b, max(x1b, 0) : x2b] = True
        out.append(binary & crop)
        
    return out


def union_mask(masks: list[np.ndarray], shape: tuple[int, int]) -> np.ndarray:
    """Combined lesion coverage, for the severity ratio."""
    if not masks:
        return np.zeros(shape, dtype=bool)
    
    total = np.zeros(shape, dtype=bool)
    
    for m in masks:
        total |= m
        
    return total


def affected_ratio(masks: list[np.ndarray], image_bgr: np.ndarray) -> float:
    """Lesion pixels over total image pixels.

    The corpus is field photography from working paddies, so there is no clean
    leaf to isolate as a denominator. Whole frame keeps it honest and stable:
    the number means "share of the photo showing lesions", not "share of the
    plant that is diseased". Report it that way to users.
    """
    h, w = image_bgr.shape[:2]
    lesion = int(np.count_nonzero(union_mask(masks, (h, w))))
    
    
    return float(min(lesion / max(h * w, 1), 1.0))
