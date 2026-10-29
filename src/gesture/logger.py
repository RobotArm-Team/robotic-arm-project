"""记录每次识别结果（含是否下发），供 E1 验收证据使用。

E1 验收要求：正确率 >= 90%、触发延迟 P95 <= 1s、越界 0 次。
本日志记录 gesture_id / gesture_code / confidence / emitted，方便事后统计。
"""

from __future__ import annotations

import csv
import os
from typing import Optional

from .gesture_command import GESTURE_CODES


class RecognitionLogger:
    def __init__(self, path: str) -> None:
        self.path = path
        self._write_header = not os.path.exists(path)

    def log(
        self,
        gesture_id: str,
        confidence: float,
        emitted: bool,
        code: Optional[int] = None,
        raw_confidence: Optional[float] = None,
    ) -> None:
        code = code if code is not None else GESTURE_CODES.get(gesture_id.upper(), 0)
        row = {
            "gesture_id": gesture_id,
            "gesture_code": code,
            "confidence": round(confidence, 3),
            "raw_confidence": round(raw_confidence, 3) if raw_confidence is not None else "",
            "emitted": int(emitted),
        }
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row.keys()))
            if self._write_header:
                w.writeheader()
                self._write_header = False
            w.writerow(row)
