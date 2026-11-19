"""Temporal confirmation for safe, one-event-per-placement detections.

This module is deliberately independent of OpenCV, Ultralytics and Arm_Lib so
its behaviour can be tested on a development computer.  It never controls an
arm; it only decides when a visual observation is stable enough to publish.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, replace
from typing import Deque, Optional, Tuple


@dataclass(frozen=True)
class DetectionCandidate:
    """The highest-confidence box selected from one frame."""

    class_id: str
    confidence: float
    bbox_xyxy: Tuple[float, float, float, float]


class DetectionGate:
    """Confirm a class across frames and re-arm only after it disappears."""

    def __init__(
        self,
        confirm_frames: int = 5,
        confirm_min: int = 4,
        min_confidence: float = 0.50,
        absence_frames: int = 3,
    ) -> None:
        if confirm_frames < 1 or not 1 <= confirm_min <= confirm_frames:
            raise ValueError("confirm_min must be within confirm_frames")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if absence_frames < 1:
            raise ValueError("absence_frames must be positive")
        self._samples: Deque[Optional[DetectionCandidate]] = deque(maxlen=confirm_frames)
        self._confirm_min = confirm_min
        self._min_confidence = min_confidence
        self._absence_frames = absence_frames
        self._absence_count = 0
        self._published_class: Optional[str] = None

    def update(self, candidate: Optional[DetectionCandidate]) -> Optional[DetectionCandidate]:
        """Return one confirmed detection, or ``None``.

        Low-confidence candidates are treated as no detection.  A published
        class remains latched until enough empty frames arrive, so a stationary
        block does not generate an event every frame.
        """

        if candidate is not None and candidate.confidence < self._min_confidence:
            candidate = None
        self._samples.append(candidate)

        if candidate is None:
            self._absence_count += 1
            if self._absence_count >= self._absence_frames:
                self._published_class = None
            return None

        self._absence_count = 0
        classes = [item.class_id for item in self._samples if item is not None]
        if len(classes) < self._confirm_min:
            return None
        class_id, count = Counter(classes).most_common(1)[0]
        if count < self._confirm_min or self._published_class == class_id:
            return None

        matching = [item for item in self._samples if item is not None and item.class_id == class_id]
        best = max(matching, key=lambda item: item.confidence)
        average_confidence = sum(item.confidence for item in matching) / len(matching)
        self._published_class = class_id
        return replace(best, confidence=average_confidence)
