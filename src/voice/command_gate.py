"""语音命令冷却门控。

E2 验收要求“帮我分类”触发一次完整分拣，且无关语音误触发率 ≤5%。
- 冷却：同一命令触发后冷却若干秒（默认 3s），防止连续语音片段重复触发。
- 纯逻辑（now 由调用方注入），便于单元测试。
"""

from __future__ import annotations

from typing import Optional

from .voice_command import VoiceCommand


class VoiceCommandGate:
    def __init__(self, cooldown_s: float = 3.0, min_confidence: float = 0.0) -> None:
        self.cooldown_s = cooldown_s
        self.min_confidence = min_confidence
        self._last_emit_time: float = -1e9
        self._last_command_id: Optional[str] = None

    def update(
        self, cmd: Optional[VoiceCommand], now: float
    ) -> Optional[VoiceCommand]:
        """喂入一个 VoiceCommand；冷却期内或低置信时返回 None（不触发）。"""
        if cmd is None:
            return None
        if cmd.confidence < self.min_confidence:
            return None
        if now - self._last_emit_time < self.cooldown_s:
            return None
        self._last_emit_time = now
        self._last_command_id = cmd.command_id
        return cmd
