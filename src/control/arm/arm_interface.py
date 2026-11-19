"""
arm_interface — 机械臂控制抽象接口。

所有业务模块（ROS2 节点、动作序列、扩展控制）必须通过此接口与机械臂交互，
严禁直接散布调用 Arm_Lib.Arm_Device 或串口指令。

真实硬件实现见 ArmLibWrapper（留待有硬件时编写）；无硬件时使用 MockController。

负责人: C
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..safety.boundaries import SERVO_LIMITS, validate_servo_angle

logger = logging.getLogger(__name__)

# 舵机编号约定: 1-4、6 为 0°–180°；5 号为 0°–270°。
# HOME_POSITION 为安全待机位，具体数值在真机标定后填入。
HOME_POSITION: dict[int, float] = {
    1: 90.0,
    2: 90.0,
    3: 90.0,
    4: 90.0,
    5: 135.0,
    6: 90.0,
}

# 舵机编号 5 为夹爪（开合控制），其余为关节
GRIPPER_SERVO_ID = 5

# 运动最小/最大时长 (ms)
MIN_DURATION_MS = 50
MAX_DURATION_MS = 5000


class ArmInterface(ABC):
    """稳定的机械臂控制接口。子类必须实现全部 7 个方法。"""

    @abstractmethod
    def move_joint(self, servo_id: int, angle: float, duration_ms: int) -> bool:
        """
        让单个舵机运动到目标角度。

        Args:
            servo_id: 舵机编号 (1-6)。
            angle: 目标角度 (°)，需在 SERVO_LIMITS 范围内。
            duration_ms: 运动时长 (ms)。

        Returns:
            True 表示动作已下发且通过本地安全校验；False 表示被拒绝或下发失败。
        """

    @abstractmethod
    def move_pose(self, joints: dict[int, float], duration_ms: int) -> bool:
        """
        多舵机同步运动。先做角度校验，全部通过后一次性下发。

        Args:
            joints: {servo_id: angle}。
            duration_ms: 运动时长 (ms)。
        """

    @abstractmethod
    def open_gripper(self) -> bool:
        """打开夹爪（向安全方向张开）。"""

    @abstractmethod
    def close_gripper(self) -> bool:
        """关闭夹爪。返回 True 不代表夹紧成功，抓后需视觉复检。"""

    @abstractmethod
    def move_home(self) -> bool:
        """所有舵机回到 HOME_POSITION 安全待机位。"""

    @abstractmethod
    def emergency_stop(self) -> bool:
        """
        急停 —— 所有舵机立即停止当前动作。
        最高优先级，不受任何业务状态影响。
        """

    @abstractmethod
    def read_servo_state(self) -> dict[int, float]:
        """
        回读 6 个舵机的当前角度。

        Returns:
            {servo_id: angle}。通信异常时返回空 dict 或上次有效值。
        """

    # ------------------------------------------------------------------
    # 非抽象的通用辅助方法 —— 子类不需要覆盖
    # ------------------------------------------------------------------

    def _validate_single(self, servo_id: int, angle: float, duration_ms: int) -> Optional[str]:
        """返回 None 表示合法；否则返回错误码。"""
        if servo_id not in SERVO_LIMITS:
            return "INVALID_SERVO_ID"
        lo, hi = SERVO_LIMITS[servo_id]
        if not (lo <= angle <= hi):
            return "ANGLE_OUT_OF_RANGE"
        if not (MIN_DURATION_MS <= duration_ms <= MAX_DURATION_MS):
            return "DURATION_OUT_OF_RANGE"
        return None

    def _validate_pose(self, joints: dict[int, float], duration_ms: int) -> Optional[str]:
        if not joints:
            return "EMPTY_POSE"
        if not (MIN_DURATION_MS <= duration_ms <= MAX_DURATION_MS):
            return "DURATION_OUT_OF_RANGE"
        for sid, ang in joints.items():
            err = self._validate_single(sid, ang, MIN_DURATION_MS)
            if err and err != "DURATION_OUT_OF_RANGE":
                return err
        return None
