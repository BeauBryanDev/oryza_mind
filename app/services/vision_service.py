
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from app.core.config import CLASS_NAMES, get_settings
from app.core.load_vision_model import get_model
from app.schemas.vision import BoundingBox, Detection, VisionResult
from app.utils.image_utils import decode_image
from app.utils.mask import mask_area_px, overlay_masks, to_data_uri
from app.utils.postprocessing import parse_output
from app.utils.preprocessing import to_tensor
from app.utils.segmentation import affected_ratio, union_mask

logger = logging.getLogger(__name__)

# it does not handle rice spikes, it handles onyl rice leaves
@dataclass
class ImageAnalysis:
    """VisionResult plus the arrays the caller needs to aggregate across images."""

    result: VisionResult
    masks: list[np.ndarray]
    class_ids: np.ndarray
    image_bgr: np.ndarray
    # Post processing
    @property
    def total_px(self) -> int:
        h, w = self.image_bgr.shape[:2]
        return h * w

    @property
    def lesion_px(self) -> int:
        h, w = self.image_bgr.shape[:2]
        return int(np.count_nonzero(union_mask(self.masks, (h, w))))


def analyze_image(
    data: bytes,
    image_index: int = 0,
    filename: str | None = None,
    with_overlay: bool = True,
) -> ImageAnalysis:
    
    settings = get_settings()
    image = decode_image(data, filename)
    
    h, w = image.shape[:2]

    tensor, info = to_tensor(image, settings.yolo_input_size)
    out0, out1 = get_model().run(tensor)

    from app.utils.segmentation import build_masks

    raw = parse_output(out0, info, settings)
    masks = build_masks(raw, out1, info, settings.yolo_mask_threshold)

    detections = [
        Detection(
            class_name=CLASS_NAMES[int(cid)],
            confidence=float(score),
            box=BoundingBox(x1=float(b[0]), y1=float(b[1]), x2=float(b[2]), y2=float(b[3])),
            mask_area_px=mask_area_px(masks[i]) if i < len(masks) else 0,
        )
        for i, (b, score, cid) in enumerate(zip(raw.boxes, raw.scores, raw.class_ids))
    ]

    overlay = None
    
    if with_overlay:
        rendered = overlay_masks(image, masks, raw.class_ids) if masks else image
        overlay = to_data_uri(rendered)

    result = VisionResult(
        image_index=image_index,
        width=w,
        height=h,
        detections=detections,
        affected_ratio=affected_ratio(masks, image),
        overlay_data_uri=overlay,
    )
    logger.info(
        "image %d: %d detection(s), affected=%.2f%%",
        image_index,
        len(detections),
        result.affected_ratio * 100,
    )
    
    return ImageAnalysis(result, masks, raw.class_ids, image)
