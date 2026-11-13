"""Capture colored-block images without importing or moving the robot arm.

Press Space or S to save the current frame. Press Q or Escape to finish.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


LABELS = ("recyclable", "hazardous", "kitchen", "other")
FRAME_SIZE = (640, 480)


def clean_session_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    if not cleaned:
        raise ValueError("session name must contain letters or numbers")
    return cleaned


def load_warp_points(path: Path) -> np.ndarray:
    points = np.fromfile(path, dtype=np.int32)
    if points.size != 8:
        raise ValueError(f"{path} must contain four int32 (x, y) points")
    return points.reshape(4, 2).astype(np.float32)


def order_points(points: np.ndarray) -> np.ndarray:
    """Return points as top-left, bottom-left, bottom-right, top-right."""
    sums = points.sum(axis=1)
    differences = points[:, 0] - points[:, 1]
    top_left = points[np.argmin(sums)]
    bottom_right = points[np.argmax(sums)]
    bottom_left = points[np.argmin(differences)]
    top_right = points[np.argmax(differences)]
    return np.array(
        [top_left, bottom_left, bottom_right, top_right], dtype=np.float32
    )


def perspective_transform(frame: np.ndarray, points: np.ndarray) -> np.ndarray:
    source = order_points(points)
    target = np.array(
        [[0, 0], [0, FRAME_SIZE[1]], [FRAME_SIZE[0], FRAME_SIZE[1]], [FRAME_SIZE[0], 0]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(source, target)
    return cv2.warpPerspective(frame, matrix, FRAME_SIZE)


def next_image_path(session_dir: Path, label: str) -> Path:
    pattern = re.compile(rf"^{re.escape(label)}_(\d{{4}})\.jpg$")
    indices = []
    for path in session_dir.glob(f"{label}_*.jpg"):
        match = pattern.match(path.name)
        if match:
            indices.append(int(match.group(1)))
    next_index = max(indices, default=0) + 1
    return session_dir / f"{label}_{next_index:04d}.jpg"


def write_jpeg(path: Path, frame: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise RuntimeError(f"failed to encode {path}")
    encoded.tofile(path)


def write_session_metadata(
    session_dir: Path,
    *,
    label: str,
    camera_index: int,
    warp_file: Path | None,
    saved_count: int,
) -> None:
    metadata = {
        "label": label,
        "camera_index": camera_index,
        "frame_width": FRAME_SIZE[0],
        "frame_height": FRAME_SIZE[1],
        "warp_file": str(warp_file) if warp_file else None,
        "saved_count": saved_count,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "arm_motion": False,
    }
    (session_dir / "session.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, choices=LABELS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--session",
        default=datetime.now().strftime("%Y%m%d-%H%M%S"),
        help="ASCII session identifier; defaults to the current date and time.",
    )
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument(
        "--warp",
        type=Path,
        help="Optional course dp.bin produced by camera calibration.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = clean_session_name(args.session)
    session_dir = args.output.expanduser().resolve() / session / args.label
    session_dir.mkdir(parents=True, exist_ok=True)

    warp_file = args.warp.expanduser().resolve() if args.warp else None
    warp_points = load_warp_points(warp_file) if warp_file else None

    capture = cv2.VideoCapture(args.camera_index)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_SIZE[0])
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_SIZE[1])
    if not capture.isOpened():
        print(f"Cannot open camera index {args.camera_index}.")
        return 1

    saved_count = len(list(session_dir.glob(f"{args.label}_*.jpg")))
    window_name = "RobotArm block capture (Space/S: save, Q/Esc: quit)"
    print(f"Saving {args.label} samples to {session_dir}")
    print("This process does not import Arm_Lib or move the arm.")
    try:
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                print("Camera frame read failed.")
                return 1
            frame = cv2.resize(frame, FRAME_SIZE)
            if warp_points is not None:
                frame = perspective_transform(frame, warp_points)

            preview = frame.copy()
            cv2.putText(
                preview,
                f"{args.label} | saved {saved_count}",
                (12, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key in (ord("s"), ord("S"), 32):
                target = next_image_path(session_dir, args.label)
                write_jpeg(target, frame)
                saved_count += 1
                print(f"Saved {target.name}")
                write_session_metadata(
                    session_dir,
                    label=args.label,
                    camera_index=args.camera_index,
                    warp_file=warp_file,
                    saved_count=saved_count,
                )
    finally:
        capture.release()
        cv2.destroyAllWindows()
        write_session_metadata(
            session_dir,
            label=args.label,
            camera_index=args.camera_index,
            warp_file=warp_file,
            saved_count=saved_count,
        )
    print(f"Finished. Saved images in this class: {saved_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

