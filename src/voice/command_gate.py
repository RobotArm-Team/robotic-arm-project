"""语音命令冷却门控。

E2 验收要求“帮我分类”触发一次完整分拣，且无关语音误触发率 ≤5%。
- 冷却：同一命令（按 voice_code）触发后冷却若干秒（默认 3s），防止连续语音片段
  重复触发同一命令；不同命令之间互不阻塞（说“开始”后立刻说“暂停”不会被误拦）。
- 纯逻辑（now 由调用方注入），便于单元测试。
"""

from __future__ import annotations

from typing import Dict, Optional

from .voice_command import VoiceCommand


class VoiceCommandGate:
    def __init__(self, cooldown_s: float = 3.0, min_confidence: float = 0.0) -> None:
        self.cooldown_s = cooldown_s
        self.min_confidence = min_confidence
        # 每个命令（voice_code）独立记录上次下发时间，互不影响
        self._last_emit: Dict[int, float] = {}

    def update(
        self, cmd: Optional[VoiceCommand], now: float
    ) -> Optional[VoiceCommand]:
        """喂入一个 VoiceCommand；同命令冷却期内或低置信时返回 None（不触发）。"""
        if cmd is None:
            return None
        if cmd.confidence < self.min_confidence:
            return None
        if now - self._last_emit.get(cmd.voice_code, -1e9) < self.cooldown_s:
            return None
        self._last_emit[cmd.voice_code] = now
        return cmd
