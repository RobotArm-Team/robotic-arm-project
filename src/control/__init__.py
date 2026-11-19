"""
control — 机械臂控制、标定与安全边界模块。

负责人: C
运行方式见本目录 README.md。
"""

from .arm.arm_interface import ArmInterface
from .safety.boundaries import (
    SERVO_LIMITS,
    WORKSPACE_BOUNDS_MM,
    ERROR_CODES,
    validate_servo_angle,
    is_in_workspace,
    can_execute,
)
from .safety.state_machine import SafetyState, state_machine

__all__ = [
    "ArmInterface",
    "SERVO_LIMITS",
    "WORKSPACE_BOUNDS_MM",
    "ERROR_CODES",
    "validate_servo_angle",
    "is_in_workspace",
    "can_execute",
    "SafetyState",
    "state_machine",
]
