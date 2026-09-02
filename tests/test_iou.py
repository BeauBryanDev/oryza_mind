from __future__ import annotations

import numpy as np

from app.utils.iou import iou_xyxy, mask_iou


def test_identical_boxes_overlap_fully():
    box = np.array([0.0, 0.0, 10.0, 10.0])
    assert iou_xyxy(box, box[None, :])[0] == 1.0


def test_disjoint_boxes_do_not_overlap():
    box = np.array([0.0, 0.0, 10.0, 10.0])
    other = np.array([[50.0, 50.0, 60.0, 60.0]])
    assert iou_xyxy(box, other)[0] == 0.0


def test_half_overlap_matches_hand_computed_value():
    box = np.array([0.0, 0.0, 10.0, 10.0])
    other = np.array([[5.0, 0.0, 15.0, 10.0]])
    # inter 50, union 150
    assert iou_xyxy(box, other)[0] == np.float32(50 / 150)


def test_empty_candidates_return_empty_array():
    box = np.array([0.0, 0.0, 10.0, 10.0])
    out = iou_xyxy(box, np.empty((0, 4)))
    assert out.shape == (0,)


def test_degenerate_box_reports_no_overlap():
    box = np.array([5.0, 5.0, 5.0, 5.0])
    other = np.array([[5.0, 5.0, 5.0, 5.0]])
    assert iou_xyxy(box, other)[0] == 0.0


def test_mask_iou_handles_overlap_and_empty_masks():
    a = np.zeros((10, 10), dtype=bool)
    b = np.zeros((10, 10), dtype=bool)
    a[:5, :] = True
    b[2:7, :] = True
    assert mask_iou(a, b) == 30 / 70
    assert mask_iou(np.zeros((4, 4), bool), np.zeros((4, 4), bool)) == 0.0
