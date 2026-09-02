from __future__ import annotations

import numpy as np

from app.utils.nms import batched_nms, nms


def test_best_scoring_box_is_kept_first(boxes):
    scores = np.array([0.4, 0.9, 0.6], dtype=np.float32)
    assert nms(boxes, scores, 0.9)[0] == 1


def test_overlapping_duplicates_collapse_to_one():
    boxes = np.array([[0.0, 0.0, 10.0, 10.0], [0.0, 0.0, 10.0, 10.0]])
    scores = np.array([0.9, 0.5])
    assert nms(boxes, scores, 0.45) == [0]


def test_weak_overlap_keeps_both(boxes):
    scores = np.array([0.9, 0.8, 0.1])
    # boxes 0 and 1 overlap at 0.33, under the threshold
    assert sorted(nms(boxes[:2], scores[:2], 0.45)) == [0, 1]


def test_empty_input_returns_nothing():
    assert nms(np.empty((0, 4)), np.empty(0), 0.45) == []


def test_single_box_survives():
    assert nms(np.array([[0.0, 0.0, 5.0, 5.0]]), np.array([0.7]), 0.45) == [0]


def test_suppression_never_crosses_classes():
    """Overlapping lesions of different diseases are both real."""
    boxes = np.array([[0.0, 0.0, 10.0, 10.0], [0.0, 0.0, 10.0, 10.0]])
    scores = np.array([0.9, 0.8])
    class_ids = np.array([0, 3])
    assert sorted(batched_nms(boxes, scores, class_ids, 0.45)) == [0, 1]


def test_batched_output_is_ordered_by_score():
    boxes = np.array(
        [[0.0, 0.0, 10.0, 10.0], [40.0, 40.0, 50.0, 50.0], [80.0, 80.0, 90.0, 90.0]]
    )
    scores = np.array([0.3, 0.95, 0.6])
    class_ids = np.array([0, 1, 2])
    assert batched_nms(boxes, scores, class_ids, 0.45) == [1, 2, 0]
