import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from vision.detection_gate import DetectionCandidate, DetectionGate


def _candidate(class_id="recyclable", confidence=0.8):
    return DetectionCandidate(class_id, confidence, (10.0, 20.0, 110.0, 120.0))


def test_requires_stable_majority():
    gate = DetectionGate(confirm_frames=5, confirm_min=4, min_confidence=0.5)
    assert gate.update(_candidate()) is None
    assert gate.update(_candidate()) is None
    assert gate.update(_candidate("hazardous")) is None
    assert gate.update(_candidate()) is None
    confirmed = gate.update(_candidate())
    assert confirmed is not None
    assert confirmed.class_id == "recyclable"


def test_stationary_block_emits_once_then_rearms_after_absence():
    gate = DetectionGate(confirm_frames=3, confirm_min=2, absence_frames=2)
    assert gate.update(_candidate()) is None
    assert gate.update(_candidate()) is not None
    assert gate.update(_candidate()) is None
    assert gate.update(None) is None
    assert gate.update(None) is None
    assert gate.update(_candidate()) is None
    assert gate.update(_candidate()) is not None


def test_low_confidence_is_not_confirmed():
    gate = DetectionGate(confirm_frames=3, confirm_min=2, min_confidence=0.5)
    assert gate.update(_candidate(confidence=0.49)) is None
    assert gate.update(_candidate(confidence=0.49)) is None
    assert gate.update(_candidate(confidence=0.49)) is None
