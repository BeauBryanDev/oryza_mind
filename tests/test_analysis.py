from __future__ import annotations

import numpy as np
import pytest

from app.core.exceptions import TooManyImagesError
from app.schemas.common import SeverityLevel
from app.schemas.vision import BoundingBox, Detection, VisionResult
from app.services import analysis_service
from app.services.analysis_service import _aggregate, _to_lines, analyze
from app.services.vision_service import ImageAnalysis


def _detection(name: str, confidence: float) -> Detection:
    return Detection(
        class_name=name,
        confidence=confidence,
        box=BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0),
        mask_area_px=100,
    )


def _analysis(index: int, detections, masks, size=(100, 100)) -> ImageAnalysis:
    image = np.zeros((*size, 3), dtype=np.uint8)
    result = VisionResult(
        image_index=index,
        width=size[1],
        height=size[0],
        detections=detections,
        affected_ratio=0.0,
    )
    return ImageAnalysis(result, masks, np.zeros(len(detections), dtype=np.int64), image)


def _mask(shape, box) -> np.ndarray:
    m = np.zeros(shape, dtype=bool)
    y0, y1, x0, x1 = box
    m[y0:y1, x0:x1] = True
    return m


def test_findings_merge_across_images():
    mask = _mask((100, 100), (0, 10, 0, 10))
    first = _analysis(0, [_detection("Brown_Spot", 0.4)], [mask])
    second = _analysis(1, [_detection("Brown_Spot", 0.8)], [mask])

    findings = _aggregate([first, second])
    assert len(findings) == 1
    assert findings[0].confidence == 0.8
    assert findings[0].lesion_count == 2
    assert findings[0].image_indices == [0, 1]


def test_overlapping_lesions_of_one_class_are_not_double_counted():
    a = _mask((100, 100), (0, 10, 0, 10))
    b = _mask((100, 100), (0, 10, 5, 15))
    image = _analysis(0, [_detection("Leaf_Blast", 0.5), _detection("Leaf_Blast", 0.6)], [a, b])

    findings = _aggregate([image])
    # union is 150 px of 10,000, not 200
    assert findings[0].affected_ratio == pytest.approx(0.015)


def test_recommendation_lines_are_stripped_of_markdown():
    reply = "## Plan\n- Apply **propiconazole** at label rate\n| a | b |\n```\n* Drain the field"
    assert _to_lines(reply) == ["Apply propiconazole at label rate", "Drain the field"]
    assert _to_lines("\n\n#\n") is None


def test_image_count_limits():
    assert analyze([]).diseases == []
    with pytest.raises(TooManyImagesError):
        analyze([(b"a", None)] * 4)


@pytest.mark.xfail(reason="known defect: overall divides by total pixels across all images")
def test_a_healthy_photo_does_not_dilute_severity(monkeypatch):
    diseased = _analysis(0, [_detection("Sheath_Blight", 0.9)], [_mask((100, 100), (0, 40, 0, 40))])
    clean = _analysis(1, [], [])

    prepared = iter([diseased, clean])
    monkeypatch.setattr(analysis_service, "analyze_image", lambda *a, **k: next(prepared))

    alone = analyze([(b"a", None)], with_recommendations=False)
    prepared = iter([diseased, clean])
    monkeypatch.setattr(analysis_service, "analyze_image", lambda *a, **k: next(prepared))
    batched = analyze([(b"a", None), (b"b", None)], with_recommendations=False)

    assert alone.overall_severity is SeverityLevel.HIGH
    assert batched.overall_severity is alone.overall_severity
