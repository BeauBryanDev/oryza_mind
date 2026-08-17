"""Mask rendering, encoding and serialization."""

from __future__ import annotations

import base64

import cv2
import numpy as np

# Distinct per class, index matches CLASS_NAMES order. BGR.
CLASS_COLORS_BGR: tuple[tuple[int, int, int], ...] = (
    (77, 255, 140),   # Bacterial_Leaf_Blight
    (0, 240, 199),    # Brown_Spot
    (112, 255, 57),   # Leaf_Blast
    (91, 166, 79),    # Narrow_Brown
    (58, 122, 46),    # Rice_Tungro
    (200, 255, 77),   # Sheath_Blight
)


def overlay_masks(
    image_bgr: np.ndarray,
    masks: list[np.ndarray],
    class_ids: np.ndarray,
    alpha: float = 0.45,
    draw_contours: bool = True,
) -> np.ndarray:
    """Tint each lesion by class and outline it."""
    out = image_bgr.copy()
    
    for mask, cid in zip(masks, class_ids):
        
        if not mask.any():
            continue
        
        color = np.array(CLASS_COLORS_BGR[int(cid) % len(CLASS_COLORS_BGR)], np.uint8)
        
        out[mask] = (out[mask] * (1 - alpha) + color * alpha).astype(np.uint8)
        
        if draw_contours:
            
            contours, _ = cv2.findContours(
                mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            cv2.drawContours(out, contours, -1, color.tolist(), 2)
            
    return out


def to_data_uri(
    image_bgr: np.ndarray, max_width: int = 1024, quality: int = 85
) -> str:
    """Encode as a data URI the frontend <img> can render directly.

    JPEG, not PNG: these are photographs, and lossless encoding made a single
    overlay 1.4-3.1 MB. Three of those would be an 8 MB JSON response.
    """
    h, w = image_bgr.shape[:2]
    
    if w > max_width:

        scale = max_width / w
        
        image_bgr = cv2.resize(
            
            image_bgr, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA
        )
        
    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    
    if not ok:
        
        raise ValueError("JPEG encoding failed")
    
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def to_png_data_uri(image_bgr: np.ndarray, max_width: int = 1024) -> str:
    """Lossless variant. Use only where exact pixels matter."""
    h, w = image_bgr.shape[:2]
    
    if w > max_width:
        
        scale = max_width / w
        
        image_bgr = cv2.resize(
            image_bgr, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA
        )
        
    ok, buf = cv2.imencode(".png", image_bgr)
    
    if not ok:
        
        raise ValueError("PNG encoding failed")
    
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def mask_area_px(mask: np.ndarray) -> int:
    
    return int(np.count_nonzero(mask))


def encode_mask_rle(mask: np.ndarray) -> dict:
    """Run-length encoding, for storing masks without the pixels."""
    flat = mask.ravel(order="F").astype(np.uint8)
    
    changes = np.flatnonzero(np.diff(flat)) + 1
    bounds = np.concatenate(([0], changes, [flat.size]))
    counts = np.diff(bounds).tolist()
    
    if flat[0] == 1:
        
        counts.insert(0, 0)
        
    return {"size": list(mask.shape), "counts": counts}
