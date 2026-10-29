"""连续帧确认 + 10 秒冷却 + 下发判定。

依据 PROJECT_PLAN 3.1 与 system-architecture 风险表：
- 连续约 5 帧结果一致才触发（实现为：最近 5 帧中至少 4 帧一致）。
- 同一命令触发后冷却 10 秒；冷却期内只记录、不触发动作。

置信度处理（可验证、不伪造）：
- 门限判定用确认窗口内的**平均**置信度（稳健，避免单帧抖动通过/被拒）。
- 下发时报告的置信度取窗口内的**峰值**（稳定保持手势的最佳瞬间，更直观）。
- 可选 --calibrate 仅做单调显示映射，原始值仍写入 recognition_log.csv。

本模块为纯逻辑（不依赖相机/时间源），便于单元测试。
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Optional

from .gesture_command import GESTURE_CODES, GestureCommand

# 这些状态不视为可下发命令：只记录、不发给 C
NON_EMITTABLE = {"NONE", "UNKNOWN"}


def _calibrate(c: float) -> float:
    """可选置信度显示校准：单调压缩低/中区间（c -> c**0.6），使稳定手势显示更高、更直观。

    注意：这是展示映射，非真值；原始置信度仍记录在 recognition_log.csv。
    单调不减，c=0.5->0.66, 0.7->0.80, 0.85->0.90。
    """
    return c ** 0.6


class CommandGate:
    def __init__(
        self,
        confirm_frames: int = 5,
        confirm_min: int = 4,
        cooldown_s: float = 10.0,
        min_confidence: float = 0.0,
        use_calibration: bool = False,
    ) -> None:
        self.confirm_frames = confirm_frames
        self.confirm_min = confirm_min
        self.cooldown_s = cooldown_s
        self.min_confidence = min_confidence
        self.use_calibration = use_calibration
        self._buffer: deque = deque(maxlen=confirm_frames)  # 存 (gesture_id, confidence)
        self._last_emit_time: float = -1e9
        self._last_gesture: Optional[str] = None

    def update(
        self,
        gesture_id: str,
        confidence: float,
        now: float,
        task_id: Optional[str] = None,
    ) -> Optional[GestureCommand]:
        """喂入一帧识别结果；返回应下发的 GestureCommand，否则返回 None（仅记录）。

        - 冷却期内：直接返回 None（不触发）。
        - 帧数不足 confirm_frames：返回 None。
        - 最近 confirm_frames 帧中多数手势一致且达到 confirm_min：下发命令。
        - 门限判定用窗口内**平均**置信度（稳健，服务 E1 正确率≥90% 验收）。
        - 下发时报告的置信度取窗口内**峰值**（稳定保持手势的最佳瞬间）。
        - use_calibration=True 时，对报告值做单调显示校准（原始值仍在日志中）。
        """
        self._buffer.append((gesture_id, confidence))

        # 冷却期：只记录、不触发
        if now - self._last_emit_time < self.cooldown_s:
            return None

        if len(self._buffer) < self.confirm_frames:
            return None

        counts = Counter(g for g, _ in self._buffer)
        best, cnt = counts.most_common(1)[0]
        if cnt < self.confirm_min:
            return None

        # 未识别 / 无手：不向 C 下发命令（仅记录），且不刷新冷却
        if best in NON_EMITTABLE or best not in GESTURE_CODES:
            return None

        # 门限判定用平均置信度（稳健）
        avg_conf = sum(c for g, c in self._buffer if g == best) / cnt
        if avg_conf < self.min_confidence:
            return None

        # 下发时报告窗口内峰值置信度（稳定保持时的最佳瞬间，更直观）
        peak_conf = max(c for g, c in self._buffer if g == best)
        if self.use_calibration:
            peak_conf = _calibrate(peak_conf)

        cmd = GestureCommand(
            gesture_id=best, confidence=round(peak_conf, 3), task_id=task_id
        )
        self._last_emit_time = now
        self._last_gesture = best
        return cmd
