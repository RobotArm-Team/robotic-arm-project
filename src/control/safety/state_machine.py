"""
state_machine — 机械臂控制侧的必经安全状态机。

与 B 的编排层共享同一套状态枚举（RECEIVED / VALIDATING / EXECUTING / ...）。
C 在此维护硬件执行状态的转换逻辑、超时检测与急停响应。

状态转移图:
    RECEIVED → VALIDATING → REJECTED（安全门禁未通过）
                          → EXECUTING → VERIFYING → SUCCEEDED
                                                   → RETRYING（最多 1 次）
                                                      → SUCCEEDED / FAILED / SAFE_MODE
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class SafetyState(str, Enum):
    """机械臂控制侧状态枚举 —— 必须与 openapi.yaml 的 PickResult.status 对齐。"""

    RECEIVED = "RECEIVED"
    REJECTED = "REJECTED"
    VALIDATING = "VALIDATING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RETRYING = "RETRYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SAFE_MODE = "SAFE_MODE"


# 合法的下一状态映射
_TRANSITIONS: dict[SafetyState, set[SafetyState]] = {
    SafetyState.RECEIVED: {SafetyState.VALIDATING, SafetyState.REJECTED},
    SafetyState.VALIDATING: {SafetyState.EXECUTING, SafetyState.REJECTED},
    SafetyState.EXECUTING: {SafetyState.VERIFYING, SafetyState.SAFE_MODE},
    SafetyState.RETRYING: {SafetyState.SUCCEEDED, SafetyState.FAILED, SafetyState.SAFE_MODE},
    SafetyState.VERIFYING: {SafetyState.SUCCEEDED, SafetyState.RETRYING, SafetyState.SAFE_MODE},
    # 终态
    SafetyState.REJECTED: set(),
    SafetyState.SUCCEEDED: set(),
    SafetyState.FAILED: set(),
    SafetyState.SAFE_MODE: set(),
}


class StateMachine:
    """简单的状态机实例；可被多个任务独立持有。"""

    def __init__(self) -> None:
        self._state = SafetyState.RECEIVED
        self._retry_count = 0
        self._retry_limit = 1  # 最多重试一次（需求基线硬性规定）

    @property
    def state(self) -> SafetyState:
        return self._state

    @property
    def retry_count(self) -> int:
        return self._retry_count

    def transition_to(self, target: SafetyState) -> bool:
        """尝试状态转换，不合法时返回 False。"""
        allowed = _TRANSITIONS.get(self._state, set())
        if target not in allowed:
            return False
        self._state = target
        return True

    def request_retry(self) -> bool:
        """请求进入 RETRYING 状态；超过上限则拒绝。"""
        if self._retry_count >= self._retry_limit:
            self._state = SafetyState.FAILED
            return False
        self._retry_count += 1
        self._state = SafetyState.RETRYING
        return True

    def emergency_stop(self) -> None:
        """急停 —— 任何状态下都直接进入 SAFE_MODE。"""
        self._state = SafetyState.SAFE_MODE

    def is_terminal(self) -> bool:
        return self._state in {SafetyState.REJECTED, SafetyState.SUCCEEDED,
                               SafetyState.FAILED, SafetyState.SAFE_MODE}


# 模块级便捷实例 —— 简单单例；多任务时应由调用方各自创建 StateMachine()
state_machine = StateMachine()


# ---------------------------------------------------------------------------
# 超时/故障阈值常量 —— 来自 system-architecture.md 风险表
# ---------------------------------------------------------------------------

COMMUNICATION_TIMEOUT_MS = 2000   # ROS2 通信超时 2s
STALL_DETECTION_MS = 3000         # 堵转约 3 秒保护
MAX_HEARTBEAT_LOSS = 3            # 连续丢失 3 个心跳 → SAFE_MODE
MAX_RETRY = 1                     # 最多一次重试（需求基线硬约束）
