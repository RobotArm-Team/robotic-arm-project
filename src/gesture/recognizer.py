"""MediaPipe 手势识别封装：A 侧唯一识别来源，不控制舵机。

依赖：mediapipe>=1.0（tasks API）、opencv-python、numpy（见 requirements.txt）。

说明：
- 使用 mediapipe.tasks.vision.GestureRecognizer，这是 Google 预训练、开箱即用的
  手势分类器，直接输出语义标签（Closed_Fist/Open_Palm/Pointing_Up/Victory/
  ILoveYou/Thumb_Up/Thumb_Down/None），无需我们手写脆弱的几何规则。
- 官方模型不含 PINCH(捏合/OK)，故在官方结果为 None/低置信时，用关键点几何补判 PINCH。
- 需要模型文件 gesture_recognizer.task；首次运行自动下载到 models/ 目录（需联网一次）。
- 输出与 landmarks.py 的 GESTURE_CODES 对齐：FIST/OPEN_PALM/POINT_UP/PEACE/
  ROCK/THUMBS_UP/PINCH。
"""

from __future__ import annotations

import os
import urllib.request
from collections import namedtuple
from typing import List, Optional, Tuple

import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from . import landmarks as L
from .smoother import GestureSmoother

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float16/1/gesture_recognizer.task"
)
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "gesture_recognizer.task")

# 官方类别名 -> 本项目手势 id（与 landmarks.GESTURE_CODES 对齐）
# None=无手势(不输出)；Thumb_Down 不在指令集 -> 记为 UNKNOWN(不输出)
GESTURE_NAME_MAP = {
    "Closed_Fist": "FIST",
    "Open_Palm": "OPEN_PALM",
    "Pointing_Up": "POINT_UP",
    "Victory": "PEACE",
    "ILoveYou": "ROCK",
    "Thumb_Up": "THUMBS_UP",
    "Thumb_Down": "UNKNOWN",
    "None": "NONE",
}

# 官方结果为这些时，回退到 PINCH 关键点补判
_FALLBACK_STATES = ("NONE", "UNKNOWN")


FrameResult = namedtuple(
    "FrameResult", ["landmarks", "base_conf", "gesture_id", "confidence"]
)


def _ensure_model() -> str:
    """确保手势模型文件存在；不存在则自动下载（仅需联网一次）。"""
    if not os.path.exists(MODEL_PATH):
        os.makedirs(MODEL_DIR, exist_ok=True)
        print(f"[E1] 首次使用，下载手势模型到 {MODEL_PATH} ...", flush=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[E1] 模型下载完成。", flush=True)
    return MODEL_PATH


class HandRecognizer:
    def __init__(
        self,
        num_hands: int = 1,
        min_hand_confidence: float = 0.5,
        min_confidence: float = 0.5,
        smooth_alpha: float = 0.6,
    ) -> None:
        model_path = _ensure_model()
        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_confidence,
            min_hand_presence_confidence=min_hand_confidence,
            min_tracking_confidence=min_hand_confidence,
        )
        self.recognizer = vision.GestureRecognizer.create_from_options(options)
        self._ts = 0
        self._smoother = GestureSmoother(alpha=smooth_alpha, decay=0.6)
        # 置信度低于该值的帧视为“未确认”，不输出命令（抑制误触发）
        self.min_confidence = min_confidence

    def process_frame(self, frame_rgb: np.ndarray) -> Optional[FrameResult]:
        """输入 RGB 帧，返回 FrameResult；未检测到手时返回 None。

        FrameResult.landmarks 为 21 个归一化关键点（供调试/补判 PINCH 使用）。
        输出置信度 = 该帧经时序平滑后的模型手势置信度（直接反映模型对该手势的把握，
        不再把“左右手判定分”乘进去做无意义打折）。
        """
        self._ts += 1
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self.recognizer.recognize_for_video(mp_image, self._ts * 33)
        if not result.hand_landmarks:
            self._smoother.reset()
            return None

        lm = result.hand_landmarks[0]

        # 取模型输出的“顶层手势”原始类别与置信度
        raw_cat = "None"
        raw_score = 0.0
        if result.gestures:
            cat = result.gestures[0][0]
            raw_cat = GESTURE_NAME_MAP.get(cat.category_name, "UNKNOWN")
            raw_score = float(cat.score)

        # 时序平滑：得到（当前最佳手势, 其平滑置信度）
        best_cat, best_score = self._smoother.update(raw_cat, raw_score)

        # PINCH 补判：官方模型不含捏合，用关键点几何判定
        if best_cat in _FALLBACK_STATES or best_score < 0.5:
            if L.is_pinch(lm):
                best_cat = "PINCH"
                best_score = max(best_score, 0.85)

        # 置信度门限：非 NONE 的真实手势若低于阈值，视为未确认（不输出命令）
        if best_cat != "NONE" and best_score < self.min_confidence:
            best_cat = "UNKNOWN"

        conf = round(best_score, 3)
        return FrameResult(
            landmarks=lm, base_conf=raw_score, gesture_id=best_cat, confidence=conf
        )

    def close(self) -> None:
        self.recognizer.close()
