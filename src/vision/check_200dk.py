"""Read-only readiness check for the Atlas 200I DK A2 vision environment.

This module never creates an Arm_Device instance and never sends servo commands.
"""

from __future__ import annotations

import argparse
import importlib.util
import platform
from pathlib import Path


DEFAULT_CONFIG_DIR = Path("/home/HwHiAiUser/RobotArm/Camera_Cal/config")


def status(ok: bool, message: str) -> None:
    marker = "OK" if ok else "MISSING"
    print(f"[{marker}] {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument(
        "--probe-camera",
        action="store_true",
        help="Open the camera and read one frame; no arm movement is performed.",
    )
    args = parser.parse_args()

    print(f"Host: {platform.node() or 'unknown'}")
    print(f"System: {platform.platform()}")
    print(f"Python: {platform.python_version()}")

    arm_lib = importlib.util.find_spec("Arm_Lib") is not None
    status(arm_lib, "Arm_Lib can be imported (the arm is not initialized)")

    video_device = Path(f"/dev/video{args.camera_index}")
    status(video_device.exists(), f"camera device {video_device}")

    config_dir = args.config_dir.expanduser().resolve()
    status(config_dir.is_dir(), f"config directory {config_dir}")
    for name in ("XYT_config.txt", "dp.bin", "data_collect_idx.txt"):
        path = config_dir / name
        status(path.is_file(), str(path))

    if not args.probe_camera:
        print("Camera frame was not read. Add --probe-camera after the USB camera is connected.")
        return 0

    try:
        import cv2
    except ImportError:
        status(False, "OpenCV (cv2) is installed")
        return 1

    capture = cv2.VideoCapture(args.camera_index)
    try:
        opened = capture.isOpened()
        status(opened, f"camera index {args.camera_index} opens")
        if not opened:
            return 1
        ok, frame = capture.read()
        status(ok and frame is not None, "one camera frame can be read")
        if ok and frame is not None:
            print(f"Frame: {frame.shape[1]}x{frame.shape[0]}")
            return 0
        return 1
    finally:
        capture.release()


if __name__ == "__main__":
    raise SystemExit(main())
