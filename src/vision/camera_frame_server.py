#!/usr/bin/env python3
"""Read a 200DK USB camera and expose the latest JPEG over read-only HTTP.

Endpoints:
  GET /health  JSON camera state
  GET /frame   latest JPEG frame

This service never imports Arm_Lib and has no endpoint that can move the arm.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Tuple

import cv2


class CameraReader:
    def __init__(self, index: int, jpeg_quality: int) -> None:
        self.index = index
        self.jpeg_quality = jpeg_quality
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._capture: Optional[cv2.VideoCapture] = None
        self._jpeg: Optional[bytes] = None
        self._frame_count = 0
        self._error: Optional[str] = None

    def start(self) -> None:
        self._capture = cv2.VideoCapture(self.index)
        if not self._capture.isOpened():
            self._capture.release()
            self._capture = None
            raise RuntimeError("cannot open camera index %d" % self.index)
        self._thread = threading.Thread(target=self._run, name="camera-reader", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        assert self._capture is not None
        while not self._stop.is_set():
            ok, frame = self._capture.read()
            if not ok or frame is None:
                with self._lock:
                    self._error = "camera read failed"
                time.sleep(0.05)
                continue
            ok, encoded = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            )
            if not ok:
                with self._lock:
                    self._error = "jpeg encode failed"
                continue
            with self._lock:
                self._jpeg = encoded.tobytes()
                self._frame_count += 1
                self._error = None

    def snapshot(self) -> Tuple[Optional[bytes], int, Optional[str]]:
        with self._lock:
            return self._jpeg, self._frame_count, self._error

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._capture is not None:
            self._capture.release()


class FrameHandler(BaseHTTPRequestHandler):
    server: "FrameServer"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/health":
            frame, frame_count, error = self.server.reader.snapshot()
            payload = json.dumps(
                {
                    "status": "READY" if frame is not None and error is None else "DEGRADED",
                    "camera_index": self.server.reader.index,
                    "frame_count": frame_count,
                    "error": error,
                }
            ).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        if self.path == "/frame":
            frame, _frame_count, error = self.server.reader.snapshot()
            if frame is None:
                payload = json.dumps({"error": error or "frame not ready"}).encode("utf-8")
                self._send(503, payload, "application/json; charset=utf-8")
                return
            self._send(200, frame, "image/jpeg")
            return
        self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8")


class FrameServer(ThreadingHTTPServer):
    def __init__(self, address: Tuple[str, int], reader: CameraReader) -> None:
        super().__init__(address, FrameHandler)
        self.reader = reader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only 200DK camera-frame service")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5010)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--jpeg-quality", type=int, default=80, choices=range(30, 101))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reader = CameraReader(args.camera_index, args.jpeg_quality)
    reader.start()
    server = FrameServer((args.host, args.port), reader)
    print("camera frame server: http://%s:%d" % (args.host, args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        reader.stop()


if __name__ == "__main__":
    raise SystemExit(main())
