"""GestureCommand：A 交给 C 的接口契约。

A 只输出"识别到的手势是什么"（gesture_id + gesture_code），
C 读取 gesture_code（或 gesture_id）后，自行决定对应的舵机运动序列。
A 不直接控制舵机。

字段说明：
- gesture_id : 手势名称，如 "FIST" / "OPEN_PALM"
- gesture_code: 稳定整数编号（C 侧查找表的主键），见 GESTURE_CODES
- confidence : 识别置信度 0~1
- source     : 固定 "gesture"（与语音命令 "voice" 区分）
- timestamp  : 识别时间（ISO 简化格式）
- task_id    : 由 B 的统一编排层分配；A 侧可留空
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

# 规范化手势 -> 编号映射（C 侧据此决定舵机动作）
GESTURE_CODES: dict[str, int] = {
    "FIST": 1,        # 握拳
    "OPEN_PALM": 2,   # 张开手掌
    "POINT_UP": 3,    # 食指 pointing up
    "PEACE": 4,       # 剪刀手（食中）
    "ROCK": 5,        # 摇滚（食小）
    "PINCH": 6,       # 捏合（OK）
    "THUMBS_UP": 7,   # 点赞
}

CODE_TO_GESTURE: dict[int, str] = {v: k for k, v in GESTURE_CODES.items()}


@dataclass
class GestureCommand:
    gesture_id: str
    confidence: float
    gesture_code: int = field(default=0)
    source: str = "gesture"
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    task_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.gesture_code == 0:
            self.gesture_code = GESTURE_CODES.get(self.gesture_id.upper(), 0)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def to_event_dict(self, event_id: str, latency_ms: float) -> dict:
        """产出与 api/openapi.yaml 的 GestureEvent 兼容的字典，供集成层上报事件服务。

        字段对齐说明：
        - gesture_type <- gesture_id（如 "FIST"）
        - gesture_code <- gesture_code（整数编号，C 侧主键）
        - captured_at  <- timestamp（ISO 文本）
        - event_id / latency_ms 由集成层/控制层提供（端到端耗时与事件唯一标识）
        """
        return {
            "event_id": event_id,
            "gesture_type": self.gesture_id,
            "gesture_code": self.gesture_code,
            "confidence": self.confidence,
            "captured_at": self.timestamp,
            "latency_ms": latency_ms,
        }

    @classmethod
    def from_json(cls, s: str) -> "GestureCommand":
        return cls(**json.loads(s))
