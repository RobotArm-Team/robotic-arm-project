"""VoiceCommand：A 交给 B 编排层 / C 控制层的语音命令契约。

E2 语音控制（成员 A 侧）：识别到“帮我分类”等关键词时，输出 VoiceCommand（含 voice_code）。
A 不直接控制舵机；C 读取 voice_code 后自定义舵机动作，并经过安全状态机校验。

字段与 api/openapi.yaml 的 VoiceCommand 对齐：
- command_id : 命令唯一标识（A 侧生成；编排层可覆盖）
- text       : 识别到的原始文本（如 “帮我分类”）
- confidence : 识别置信度 0~1
- captured_at: 识别时间（ISO 格式，date-time）
- latency_ms : 端到端识别耗时（毫秒）
- voice_code : 稳定整数编号（C 侧查找表主键），见 VOICE_CODES
- source     : 固定 "voice"（与手势命令 "gesture" 区分）
- task_id    : 由 B 的统一编排层分配；A 侧可留空
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

# 规范化语音命令 -> 编号映射（C 侧据此决定舵机动作）
VOICE_CODES: dict[str, int] = {
    "SORT_ONE": 1,   # “帮我分类”：触发一次完整分拣
}

CODE_TO_VOICE: dict[int, str] = {v: k for k, v in VOICE_CODES.items()}


@dataclass
class VoiceCommand:
    text: str
    confidence: float
    command_id: str = field(default_factory=lambda: f"vc_{uuid.uuid4().hex[:12]}")
    voice_code: int = field(default=0)
    source: str = "voice"
    captured_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    latency_ms: float = 0.0
    task_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def to_event_dict(self) -> dict:
        """产出与 api/openapi.yaml VoiceCommand 兼容的字典（供集成层上报事件服务）。"""
        return {
            "command_id": self.command_id,
            "text": self.text,
            "confidence": self.confidence,
            "captured_at": self.captured_at,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_json(cls, s: str) -> "VoiceCommand":
        return cls(**json.loads(s))
