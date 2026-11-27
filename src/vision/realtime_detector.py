#!/usr/bin/env python3
"""Run local YOLO inference on the latest frame from the 200DK.

The detector publishes every visible box so the web UI can draw all objects in
the camera view, and keeps a primary detection for the manual \"分拣该物体\"
button.  It never opens Arm_Lib or posts a PickTask.
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
    from vision.detection_gate import DetectionCandidate
except ImportError:  # Supports direct execution from src/vision.
    from detection_gate import DetectionCandidate


def fetch_frame(url: str, timeout_s: float) -> np.ndarray:
    with urlopen(url, timeout=timeout_s) as response:  # nosec B310 - user supplied local endpoint
        payload = response.read()
    frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("frame endpoint did not return a decodable image")
    return frame


def all_candidates(result: Any, min_confidence: float) -> list[DetectionCandidate]:
    """返回当前帧中所有超过置信度阈值的检测框，供前端逐个展示。"""
    if result.boxes is None or len(result.boxes) == 0:
        return []
    candidates: list[DetectionCandidate] = []
    names = result.names
    for index in range(len(result.boxes)):
        confidence = float(result.boxes.conf[index].item())
        if confidence < min_confidence:
            continue
        bbox = result.boxes.xyxy[index].cpu().tolist()
        class_index = int(result.boxes.cls[index].item())
        candidates.append(
            DetectionCandidate(
                class_id=str(names[class_index]),
                confidence=confidence,
                bbox_xyxy=tuple(float(value) for value in bbox),
            )
        )
    return candidates


def detection_item(candidate: DetectionCandidate, frame_shape: Tuple[int, int]) -> Dict[str, Any]:
    height, width = frame_shape
    left, top, right, bottom = candidate.bbox_xyxy
    left = max(0, min(int(round(left)), width - 1))
    top = max(0, min(int(round(top)), height - 1))
    right = max(left + 1, min(int(round(right)), width))
    bottom = max(top + 1, min(int(round(bottom)), height))
    box_width, box_height = right - left, bottom - top
    return {
        "class_id": candidate.class_id,
        "confidence": round(candidate.confidence, 4),
        "bbox_px": [left, top, box_width, box_height],
        "center_px": [left + box_width // 2, top + box_height // 2],
    }


def detection_payload(
    candidates: list[DetectionCandidate],
    frame_shape: Tuple[int, int],
    elapsed_ms: float,
    fallback_class: str = "other",
) -> Dict[str, Any]:
    """组装一帧的检测结果：检测列表 + 供现有分拣按钮使用的首选目标。"""
    captured_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    items = [detection_item(candidate, frame_shape) for candidate in candidates]
    payload: Dict[str, Any] = {
        "frame_id": "vision-" + captured_at,
        "inference_ms": round(elapsed_ms, 2),
        "count": len(items),
        "detections": items,
    }
    if candidates:
        # 分拣按钮对应的首选目标取「离画面中心最近」的框：机械臂在桌面中央抓取，
        # 这样多个物体同时出现时，类别的选择与实际抓取位置一致。
        height, width = frame_shape
        center_x, center_y = width / 2.0, height / 2.0
        primary = min(
            candidates,
            key=lambda candidate: (
                ((candidate.bbox_xyxy[0] + candidate.bbox_xyxy[2]) / 2.0 - center_x) ** 2
                + ((candidate.bbox_xyxy[1] + candidate.bbox_xyxy[3]) / 2.0 - center_y) ** 2
            ),
        )
        payload.update(detection_item(primary, frame_shape))
    else:
        # 顶层 class_id 只为兼容后端现有校验；前端以 detections 列表为准。
        payload["class_id"] = fallback_class
    return payload


def post_json(url: str, payload: Dict[str, Any], timeout_s: float) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout_s) as response:  # nosec B310 - explicit team backend URL
        if not 200 <= response.status < 300:
            raise RuntimeError("callback returned HTTP %d" % response.status)


def draw_preview(frame: np.ndarray, candidates: list[DetectionCandidate]) -> np.ndarray:
    preview = frame.copy()
    for candidate in candidates:
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
    processed = 0
    last_class: Optional[str] = None
    print("Detector started. It posts all visible detections; it never commands the arm.")
    try:
        while args.max_frames <= 0 or processed < args.max_frames:
            started = time.perf_counter()
            try:
                frame = fetch_frame(args.frame_url, args.timeout_s)
                result = model.predict(source=frame, imgsz=640, conf=args.min_confidence, verbose=False)[0]
                candidates = all_candidates(result, args.min_confidence)
            except (RuntimeError, URLError, TimeoutError, cv2.error) as exc:
                print(json.dumps({"vision_error": str(exc)}, ensure_ascii=False), flush=True)
                time.sleep(args.poll_interval_ms / 1000.0)
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            payload = detection_payload(candidates, frame.shape[:2], elapsed_ms, last_class or "other")
            if candidates:
                last_class = payload["class_id"]
                print(json.dumps(payload, ensure_ascii=False), flush=True)
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
