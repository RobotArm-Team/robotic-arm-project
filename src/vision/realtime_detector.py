#!/usr/bin/env python3
"""Run local YOLO inference on the latest frame from the 200DK.

The detector emits a standard ``DetectionResult`` JSON only after a class is
stable across consecutive frames.  It never opens Arm_Lib or posts a PickTask.
An optional callback is for a backend endpoint agreed by the team; it is not
enabled by default.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np
from ultralytics import YOLO

try:
    from vision.detection_gate import DetectionCandidate, DetectionGate
except ImportError:  # Supports direct execution from src/vision.
    from detection_gate import DetectionCandidate, DetectionGate


def fetch_frame(url: str, timeout_s: float) -> np.ndarray:
    with urlopen(url, timeout=timeout_s) as response:  # nosec B310 - user supplied local endpoint
        payload = response.read()
    frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("frame endpoint did not return a decodable image")
    return frame


def box_iou(first: DetectionCandidate, second: DetectionCandidate) -> float:
    """Return IoU for two xyxy boxes without requiring another ML package."""

    ax1, ay1, ax2, ay2 = first.bbox_xyxy
    bx1, by1, bx2, by2 = second.bbox_xyxy
    intersection_left, intersection_top = max(ax1, bx1), max(ay1, by1)
    intersection_right, intersection_bottom = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, intersection_right - intersection_left) * max(
        0.0, intersection_bottom - intersection_top
    )
    first_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    second_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = first_area + second_area - intersection
    return 0.0 if union <= 0 else intersection / union


def frame_candidates(result: Any, duplicate_iou: float) -> List[DetectionCandidate]:
    """Return all class-aware, non-overlapping candidates in a frame.

    Ultralytics already performs NMS, but this small second pass removes the
    partially overlapping duplicate boxes observed in close-up course images.
    Different categories are never suppressed against each other.
    """

    if result.boxes is None or len(result.boxes) == 0:
        return []
    raw = []
    for bbox, class_index, confidence in zip(
        result.boxes.xyxy.cpu().tolist(),
        result.boxes.cls.cpu().tolist(),
        result.boxes.conf.cpu().tolist(),
    ):
        raw.append(
            DetectionCandidate(
                class_id=str(result.names[int(class_index)]),
                confidence=float(confidence),
                bbox_xyxy=tuple(float(value) for value in bbox),
            )
        )
    selected: List[DetectionCandidate] = []
    for candidate in sorted(raw, key=lambda item: item.confidence, reverse=True):
        duplicate = any(
            candidate.class_id == existing.class_id and box_iou(candidate, existing) >= duplicate_iou
            for existing in selected
        )
        if not duplicate:
            selected.append(candidate)
    return selected


def detection_result(candidate: DetectionCandidate, frame_shape: Tuple[int, int], elapsed_ms: float) -> Dict[str, Any]:
    height, width = frame_shape
    left, top, right, bottom = candidate.bbox_xyxy
    left = max(0, min(int(round(left)), width - 1))
    top = max(0, min(int(round(top)), height - 1))
    right = max(left + 1, min(int(round(right)), width))
    bottom = max(top + 1, min(int(round(bottom)), height))
    box_width, box_height = right - left, bottom - top
    captured_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return {
        "frame_id": "vision-" + captured_at,
        "class_id": candidate.class_id,
        "confidence": round(candidate.confidence, 4),
        "bbox_px": [left, top, box_width, box_height],
        "center_px": [left + box_width // 2, top + box_height // 2],
        "inference_ms": round(elapsed_ms, 2),
    }


def post_json(url: str, payload: Dict[str, Any], timeout_s: float) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout_s) as response:  # nosec B310 - explicit team backend URL
        if not 200 <= response.status < 300:
            raise RuntimeError("callback returned HTTP %d" % response.status)


def draw_preview(frame: np.ndarray, candidates: List[DetectionCandidate]) -> np.ndarray:
    preview = frame.copy()
    colors = {
        "recyclable": (255, 120, 0),
        "hazardous": (0, 0, 255),
        "kitchen": (0, 180, 0),
        "other": (0, 210, 255),
    }
    for candidate in candidates:
        left, top, right, bottom = (int(round(value)) for value in candidate.bbox_xyxy)
        color = colors.get(candidate.class_id, (255, 255, 255))
        cv2.rectangle(preview, (left, top), (right, bottom), color, 2)
        cv2.putText(
            preview,
            "%s %.2f" % (candidate.class_id, candidate.confidence),
            (left, max(22, top - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )
    return preview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real-time four-class block detector")
    parser.add_argument("--model", type=Path, required=True, help="local YOLO .pt weight path")
    parser.add_argument("--frame-url", required=True, help="200DK GET /frame URL")
    parser.add_argument("--callback-url", help="optional team-agreed backend URL for DetectionResult JSON")
    parser.add_argument("--min-confidence", type=float, default=0.50)
    parser.add_argument(
        "--duplicate-iou",
        type=float,
        default=0.45,
        help="suppress same-class overlapping boxes at or above this IoU",
    )
    parser.add_argument("--confirm-frames", type=int, default=5)
    parser.add_argument("--confirm-min", type=int, default=4)
    parser.add_argument("--absence-frames", type=int, default=3)
    parser.add_argument("--poll-interval-ms", type=int, default=100)
    parser.add_argument("--timeout-s", type=float, default=3.0)
    parser.add_argument("--preview", action="store_true", help="show annotated local preview; press Q to exit")
    parser.add_argument("--max-frames", type=int, default=0, help="0 means run until Q/Ctrl+C")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0.0 <= args.min_confidence <= 1.0 or not 0.0 <= args.duplicate_iou <= 1.0:
        raise SystemExit("--min-confidence and --duplicate-iou must be between 0 and 1")
    if not args.model.is_file():
        raise SystemExit("model weight does not exist: %s" % args.model)
    model = YOLO(str(args.model))
    class_names = sorted(str(value) for value in model.names.values())
    gates = {
        class_id: DetectionGate(
            confirm_frames=args.confirm_frames,
            confirm_min=args.confirm_min,
            min_confidence=args.min_confidence,
            absence_frames=args.absence_frames,
        )
        for class_id in class_names
    }
    processed = 0
    # The backend considers a result older than three seconds stale. Keep a
    # heartbeat for each class independently so one visible colour cannot
    # hide another from the shared frontend.
    last_emitted: Dict[str, Tuple[Dict[str, Any], float]] = {}
    print("Detector started. It only emits stable DetectionResult JSON; it never commands the arm.")
    try:
        while args.max_frames <= 0 or processed < args.max_frames:
            started = time.perf_counter()
            try:
                frame = fetch_frame(args.frame_url, args.timeout_s)
                result = model.predict(source=frame, imgsz=640, conf=args.min_confidence, verbose=False)[0]
                candidates = frame_candidates(result, args.duplicate_iou)
            except (RuntimeError, URLError, TimeoutError, cv2.error) as exc:
                print(json.dumps({"vision_error": str(exc)}, ensure_ascii=False), flush=True)
                time.sleep(args.poll_interval_ms / 1000.0)
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            # The course scenario has one block per colour/class.  Each class
            # owns an independent confirmation gate, so all four classes can
            # be emitted from the same stable frame window.
            best_by_class = {}
            for candidate in candidates:
                if candidate.class_id not in best_by_class:
                    best_by_class[candidate.class_id] = candidate
            now = time.monotonic()
            for class_id, gate in gates.items():
                candidate = best_by_class.get(class_id)
                confirmed = gate.update(candidate)
                if confirmed is not None:
                    payload = detection_result(confirmed, frame.shape[:2], elapsed_ms)
                    print(json.dumps(payload, ensure_ascii=False), flush=True)
                else:
                    previous = last_emitted.get(class_id)
                    if (
                        candidate is None
                        or previous is None
                        or candidate.confidence < args.min_confidence
                        or now - previous[1] < 1.0
                    ):
                        continue
                    # The same class remains visible: repost the last stable
                    # result once a second to prevent the backend timing out.
                    payload = previous[0]
                last_emitted[class_id] = (payload, now)
                if args.callback_url:
                    try:
                        post_json(args.callback_url, payload, args.timeout_s)
                    except (RuntimeError, URLError, TimeoutError) as exc:
                        print(json.dumps({"callback_error": str(exc), "payload": payload}, ensure_ascii=False), flush=True)
            if args.preview:
                cv2.imshow("Block detection (Q to quit)", draw_preview(frame, candidates))
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                    break
            processed += 1
            time.sleep(args.poll_interval_ms / 1000.0)
    except KeyboardInterrupt:
        pass
    finally:
        if args.preview:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
