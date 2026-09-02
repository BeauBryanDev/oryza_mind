from __future__ import annotations

import cv2
import numpy as np
import pytest
from PIL import Image

from app.core.config import get_settings
from app.schemas.spike import SpikeLabel
from app.utils.preprocessing import PAD_VALUE, to_spike_tensor

TEST_IMGS = get_settings().spike_model_path.parent.parent / "test_imgs"


def test_tensor_is_nhwc(bgr_image):
    assert to_spike_tensor(bgr_image, 640).shape == (1, 640, 640, 3)


def test_pixels_stay_raw(bgr_image):
    """Rescaling and ImageNet normalization are baked into the graph."""
    tensor = to_spike_tensor(bgr_image, 640)
    assert tensor.max() > 1.0
    assert tensor.max() <= 255.0


def test_resize_is_pil_bilinear_not_cv2(wide_bgr_image):
    """cv2 does not antialias on downscale, and that flips the class."""
    rgb = cv2.cvtColor(wide_bgr_image, cv2.COLOR_BGR2RGB)
    pil = np.asarray(Image.fromarray(rgb).resize((640, 640), Image.BILINEAR), dtype=np.float32)
    naive = cv2.resize(rgb, (640, 640), interpolation=cv2.INTER_LINEAR).astype(np.float32)

    tensor = to_spike_tensor(wide_bgr_image, 640)[0]
    assert np.array_equal(tensor, pil)
    assert not np.allclose(tensor, naive)


def test_resize_is_a_plain_stretch(wide_bgr_image):
    """Keras resized directly; grey bars would shift the input distribution."""
    tensor = to_spike_tensor(wide_bgr_image, 640)[0]
    assert not (tensor[0] == PAD_VALUE).all()
    assert not (tensor[-1] == PAD_VALUE).all()


@pytest.mark.slow
def test_backend_matches_the_reference_script():
    from app.core.load_spike_model import get_spike_model
    from app.utils.image_utils import decode_image

    settings = get_settings()
    if not settings.spike_model_path.exists():
        pytest.skip("spike model not on disk")

    model = get_spike_model()
    files = sorted(p for p in TEST_IMGS.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    assert files

    for path in files:
        ours = model.run(to_spike_tensor(decode_image(path.read_bytes(), path.name), 640))

        img = Image.open(path).convert("RGB").resize((640, 640), Image.BILINEAR)
        reference = model.run(np.expand_dims(np.array(img, dtype=np.float32), axis=0))

        assert abs(ours - reference) < 1e-4, path.name


@pytest.mark.slow
def test_loader_rejects_an_unexpected_input_shape(monkeypatch):
    from app.core import load_spike_model as loader
    from app.core.exceptions import ModelNotLoadedError

    if not get_settings().spike_model_path.exists():
        pytest.skip("spike model not on disk")

    monkeypatch.setattr(loader, "EXPECTED_INPUT", (1, 3, 640, 640))
    loader.get_spike_model.cache_clear()
    with pytest.raises(ModelNotLoadedError):
        loader.get_spike_model()
    loader.get_spike_model.cache_clear()


@pytest.mark.parametrize(
    "score, label, confidence",
    [
        (0.70, SpikeLabel.UNHEALTHY, 0.70),
        (0.30, SpikeLabel.HEALTHY, 0.70),
    ],
)
def test_threshold_picks_label_and_confidence(monkeypatch, score, label, confidence):
    from app.services import spike_service

    monkeypatch.setattr(spike_service, "decode_image", lambda *a, **k: np.zeros((8, 8, 3), np.uint8))
    monkeypatch.setattr(spike_service, "to_spike_tensor", lambda *a, **k: None)
    monkeypatch.setattr(spike_service, "get_spike_model", lambda: _FakeModel(score))

    prediction = spike_service.classify_spike(b"x")
    assert prediction.label is label
    assert prediction.confidence == pytest.approx(confidence)


class _FakeModel:
    def __init__(self, score: float):
        self.score = score

    def run(self, tensor) -> float:
        return self.score


def test_scores_near_the_threshold_are_flagged_uncertain(monkeypatch):
    from app.services import spike_service

    monkeypatch.setattr(spike_service, "decode_image", lambda *a, **k: np.zeros((8, 8, 3), np.uint8))
    monkeypatch.setattr(spike_service, "to_spike_tensor", lambda *a, **k: None)
    monkeypatch.setattr(spike_service, "get_spike_model", lambda: _FakeModel(0.55))

    assert spike_service.classify_spike(b"x").uncertain


def test_batch_verdict_is_worst_case(monkeypatch):
    """One unhealthy panicle condemns the sample."""
    from app.services import spike_service

    scores = iter([0.1, 0.9, 0.2])
    monkeypatch.setattr(spike_service, "decode_image", lambda *a, **k: np.zeros((8, 8, 3), np.uint8))
    monkeypatch.setattr(spike_service, "to_spike_tensor", lambda *a, **k: None)
    monkeypatch.setattr(spike_service, "get_spike_model", lambda: _FakeModel(0.0))
    monkeypatch.setattr(_FakeModel, "run", lambda self, tensor: next(scores))

    result = spike_service.classify([(b"a", None), (b"b", None), (b"c", None)], with_recommendations=False)
    assert result.overall_label is SpikeLabel.UNHEALTHY
    assert result.unhealthy_count == 1
    assert result.total_count == 3
