from __future__ import annotations

import numpy as np
import pytest

from app.core.config import CLASS_NAMES
from app.schemas.common import SeverityLevel, severity_from_area
from app.utils.postprocessing import NUM_MASK_COEFFS, RawDetections, parse_output, xywh_to_xyxy
from app.utils.preprocessing import PAD_VALUE, letterbox, scale_boxes, to_tensor
from app.utils.segmentation import build_masks


def _preds(rows: list[tuple[float, float, float, float, int, float]]) -> np.ndarray:
    """Build a (1, 42, n) output0 from (cx, cy, w, h, class_id, score) rows."""
    out = np.zeros((len(rows), 4 + len(CLASS_NAMES) + NUM_MASK_COEFFS), dtype=np.float32)
    for i, (cx, cy, w, h, cid, score) in enumerate(rows):
        out[i, :4] = (cx, cy, w, h)
        out[i, 4 + cid] = score
        out[i, 4 + len(CLASS_NAMES) :] = 0.1
    return out.T[np.newaxis, ...]


def test_letterbox_output_is_a_square_canvas(wide_bgr_image):
    padded, _ = letterbox(wide_bgr_image, 640)
    assert padded.shape == (640, 640, 3)


def test_letterbox_preserves_aspect_and_pads_the_short_side(wide_bgr_image):
    padded, info = letterbox(wide_bgr_image, 640)
    assert info.scale == 640 / 1280
    # 480 * 0.5 = 240 tall, so 200 grey rows top and bottom
    assert (padded[0] == PAD_VALUE).all()
    assert (padded[-1] == PAD_VALUE).all()
    assert not (padded[320] == PAD_VALUE).all()


def test_scale_boxes_undoes_the_letterbox(wide_bgr_image):
    _, info = letterbox(wide_bgr_image, 640)
    original = np.array([[300.0, 50.0, 900.0, 200.0]])
    model_space = original.copy()
    model_space[:, [0, 2]] = model_space[:, [0, 2]] * info.scale + info.pad_x
    model_space[:, [1, 3]] = model_space[:, [1, 3]] * info.scale + info.pad_y
    assert np.allclose(scale_boxes(model_space, info), original, atol=1.0)


def test_to_tensor_is_nchw_normalised(bgr_image):
    tensor, _ = to_tensor(bgr_image, 640)
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert 0.0 <= tensor.min() and tensor.max() <= 1.0


def test_xywh_to_xyxy_converts_a_known_box():
    out = xywh_to_xyxy(np.array([[10.0, 20.0, 4.0, 6.0]]))
    assert out.tolist() == [[8.0, 17.0, 12.0, 23.0]]


def test_per_class_thresholds_are_applied_independently(settings, bgr_image):
    _, info = letterbox(bgr_image, 640)
    brown_spot = CLASS_NAMES.index("Brown_Spot")
    sheath = CLASS_NAMES.index("Sheath_Blight")
    output = _preds(
        [
            (100.0, 100.0, 20.0, 20.0, brown_spot, 0.20),
            (400.0, 400.0, 20.0, 20.0, sheath, 0.20),
        ]
    )
    raw = parse_output(output, info, settings)
    assert raw.class_ids.tolist() == [brown_spot]


def test_nothing_above_threshold_yields_empty_detections(settings, bgr_image):
    _, info = letterbox(bgr_image, 640)
    output = _preds([(100.0, 100.0, 20.0, 20.0, 0, 0.01)])
    raw = parse_output(output, info, settings)
    assert raw.boxes.shape == (0, 4)
    assert raw.mask_coeffs.shape == (0, NUM_MASK_COEFFS)


def _raw_one_box() -> RawDetections:
    return RawDetections(
        boxes=np.array([[100.0, 100.0, 300.0, 300.0]], dtype=np.float32),
        scores=np.array([0.8], dtype=np.float32),
        class_ids=np.array([0]),
        mask_coeffs=np.full((1, NUM_MASK_COEFFS), 0.5, dtype=np.float32),
    )


def test_build_masks_returns_one_full_resolution_mask_per_detection(bgr_image):
    _, info = letterbox(bgr_image, 640)
    protos = np.full((1, NUM_MASK_COEFFS, 160, 160), 1.0, dtype=np.float32)
    masks = build_masks(_raw_one_box(), protos, info)
    assert len(masks) == 1
    assert masks[0].dtype == bool
    assert masks[0].shape == (info.orig_h, info.orig_w)


def test_mask_never_extends_outside_its_own_box(bgr_image):
    _, info = letterbox(bgr_image, 640)
    protos = np.full((1, NUM_MASK_COEFFS, 160, 160), 1.0, dtype=np.float32)
    mask = build_masks(_raw_one_box(), protos, info)[0]
    outside = mask.copy()
    outside[100:300, 100:300] = False
    assert not outside.any()


@pytest.mark.parametrize(
    "ratio, level",
    [
        (0.0, SeverityLevel.LOW),
        (0.029, SeverityLevel.LOW),
        (0.03, SeverityLevel.MODERATE),
        (0.099, SeverityLevel.MODERATE),
        (0.10, SeverityLevel.HIGH),
        (0.179, SeverityLevel.HIGH),
        (0.18, SeverityLevel.CRITICAL),
    ],
)
def test_severity_bands(ratio, level):
    assert severity_from_area(ratio) is level
