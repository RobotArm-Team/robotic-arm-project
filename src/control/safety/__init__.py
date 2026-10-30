"""safety — 舵机限位、工作区校验、安全门禁与状态机。"""

from .boundaries import (
    SERVO_LIMITS,
    WORKSPACE_BOUNDS_MM,
    ERROR_CODES,
    validate_servo_angle,
    is_in_workspace,
    can_execute,
)
from .state_machine import SafetyState, state_machine

__all__ = [
    "SERVO_LIMITS",
    "WORKSPACE_BOUNDS_MM",
    "ERROR_CODES",
    "validate_servo_angle",
    "is_in_workspace",
    "can_execute",
    "SafetyState",
    "state_machine",
]
