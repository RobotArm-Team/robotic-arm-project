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
from typing import Any, Dict, Optional, Tuple
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


def top_candidate(result: Any) -> Optional[DetectionCandidate]:
    if result.boxes is None or len(result.boxes) == 0:
        return None
    best_index = int(result.boxes.conf.argmax().item())
    bbox = result.boxes.xyxy[best_index].cpu().tolist()
    class_index = int(result.boxes.cls[best_index].item())
    return DetectionCandidate(
        class_id=str(result.names[class_index]),
        confidence=float(result.boxes.conf[best_index].item()),
        bbox_xyxy=tuple(float(value) for value in bbox),
    )


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


def draw_preview(frame: np.ndarray, candidate: Optional[DetectionCandidate]) -> np.ndarray:
    preview = frame.copy()
    if candidate is not None:
        left, top, right, bottom = (int(round(value)) for value in candidate.bbox_xyxy)
        cv2.rectangle(preview, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.putText(
            preview,
            "%s %.2f" % (candidate.class_id, candidate.confidence),
            (left, max(22, top - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
    return preview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real-time four-class block detector")
    parser.add_argument("--model", type=Path, required=True, help="local YOLO .pt weight path")
    parser.add_argument("--frame-url", required=True, help="200DK GET /frame URL")
    parser.add_argument("--callback-url", help="optional team-agreed backend URL for DetectionResult JSON")
    parser.add_argument("--min-confidence", type=float, default=0.50)
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
    if not 0.0 <= args.min_confidence <= 1.0:
        raise SystemExit("--min-confidence must be between 0 and 1")
    if not args.model.is_file():
        raise SystemExit("model weight does not exist: %s" % args.model)
    model = YOLO(str(args.model))
    gate = DetectionGate(
        confirm_frames=args.confirm_frames,
        confirm_min=args.confirm_min,
        min_confidence=args.min_confidence,
        absence_frames=args.absence_frames,
    )
    processed = 0
    last_payload: Optional[Dict[str, Any]] = None
    last_class: Optional[str] = None
    last_post_at = 0.0
    print("Detector started. It only emits stable DetectionResult JSON; it never commands the arm.")
    try:
        while args.max_frames <= 0 or processed < args.max_frames:
            started = time.perf_counter()
            try:
                frame = fetch_frame(args.frame_url, args.timeout_s)
                result = model.predict(source=frame, imgsz=640, conf=args.min_confidence, verbose=False)[0]
                candidate = top_candidate(result)
            except (RuntimeError, URLError, TimeoutError, cv2.error) as exc:
                print(json.dumps({"vision_error": str(exc)}, ensure_ascii=False), flush=True)
                time.sleep(args.poll_interval_ms / 1000.0)
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            confirmed = gate.update(candidate)
            now = time.monotonic()
            if confirmed is not None:
                payload = detection_result(confirmed, frame.shape[:2], elapsed_ms)
                last_payload, last_class, last_post_at = payload, confirmed.class_id, now
                print(json.dumps(payload, ensure_ascii=False), flush=True)
                if args.callback_url:
                    try:
                        post_json(args.callback_url, payload, args.timeout_s)
                    except (RuntimeError, URLError, TimeoutError) as exc:
                        print(json.dumps({"callback_error": str(exc), "payload": payload}, ensure_ascii=False), flush=True)
            elif (
                last_payload is not None
                and candidate is not None
                and candidate.class_id == last_class
                and candidate.confidence >= args.min_confidence
                and now - last_post_at >= 1.0
            ):
                # 物体仍在同一位置：每秒补发一次心跳，避免后端 3 秒过期误判"目标已离开"。
                last_post_at = now
                if args.callback_url:
                    try:
                        post_json(args.callback_url, last_payload, args.timeout_s)
                    except (RuntimeError, URLError, TimeoutError) as exc:
                        print(json.dumps({"callback_error": str(exc), "payload": last_payload}, ensure_ascii=False), flush=True)
            if args.preview:
                cv2.imshow("Block detection (Q to quit)", draw_preview(frame, candidate))
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
