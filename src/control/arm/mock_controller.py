"""
mock_controller — 无硬件时联调用的 Mock 机械臂控制器。

模拟 6 个舵机状态、运动延时，并支持可配置的故障注入：
  - stall_servo_ids: 模拟堵转的舵机集合 (3 秒保护)
  - heartbeat_loss: 连续丢失心跳计数
  - estop_active: 模拟急停按下

A、B、D 三方均可直接 import MockController 进行独立开发，
无需等待真机联通。真实硬件实现见 arm_lib_wrapper.py（待有硬件时编写）。
"""

from __future__ import annotations

import time
import logging
from typing import Optional

from .arm_interface import ArmInterface, HOME_POSITION
from ..safety.boundaries import SERVO_LIMITS

logger = logging.getLogger(__name__)


class MockController(ArmInterface):
    """可配置的 Mock 控制器。默认无故障、未急停。"""

    def __init__(
        self,
        *,
        stall_servo_ids: Optional[set[int]] = None,
        heartbeat_loss: int = 0,
        estop_active: bool = False,
        seed_home: Optional[dict[int, float]] = None,
    ) -> None:
        # 内部状态
        self._angles: dict[int, float] = dict(seed_home or HOME_POSITION)
        self._estop_active = estop_active
        self._stall_servos: set[int] = set(stall_servo_ids or [])
        self._heartbeat_loss_count: int = heartbeat_loss
        self._last_motion_started_at: Optional[float] = None

    # ------------------------------------------------------------------
    # ArmInterface 实现
    # ------------------------------------------------------------------

    def move_joint(self, servo_id: int, angle: float, duration_ms: int) -> bool:
        if self._estop_active:
            logger.warning("[Mock] move_joint REJECTED: estop active")
            return False
        err = self._validate_single(servo_id, angle, duration_ms)
        if err:
            logger.warning("[Mock] move_joint REJECTED: %s", err)
            return False

        # 堵转模拟：指定舵机永远不运动
        if servo_id in self._stall_servos:
            logger.info("[Mock] servo %d stalled — skipping motion", servo_id)
            return False

        self._simulate_delay(duration_ms)
        self._angles[servo_id] = float(angle)
        logger.debug("[Mock] servo %d → %.1f°", servo_id, angle)
        return True

    def move_pose(self, joints: dict[int, float], duration_ms: int) -> bool:
        if self._estop_active:
            logger.warning("[Mock] move_pose REJECTED: estop active")
            return False
        err = self._validate_pose(joints, duration_ms)
        if err:
            logger.warning("[Mock] move_pose REJECTED: %s", err)
            return False

        self._simulate_delay(duration_ms)
        for sid, ang in joints.items():
            if sid in self._stall_servos:
                logger.info("[Mock] servo %d stalled — skipping", sid)
                continue
            self._angles[sid] = float(ang)
        return True

    def open_gripper(self) -> bool:
        return self.move_joint(5, 200.0, 500)

    def close_gripper(self) -> bool:
        return self.move_joint(5, 60.0, 500)

    def move_home(self) -> bool:
        return self.move_pose(HOME_POSITION, 1000)

    def emergency_stop(self) -> bool:
        self._estop_active = True
        # 立即停臂：不回到 HOME，保持当前角度但标记为急停
        logger.warning("[Mock] EMERGENCY STOP triggered — all motion halted")
        return True

    def read_servo_state(self) -> dict[int, float]:
        if self._heartbeat_loss_count >= 3:
            logger.warning("[Mock] heartbeat lost — returning empty state")
            return {}
        return dict(self._angles)

    # ------------------------------------------------------------------
    # Mock 专用控制方法（真实 ArmInterface 不应暴露这些）
    # ------------------------------------------------------------------

    def clear_estop(self) -> None:
        """解除急停（人工复位）。"""
        self._estop_active = False
        logger.info("[Mock] estop cleared")

    def set_stall(self, servo_ids: set[int]) -> None:
        self._stall_servos = set(servo_ids)

    def set_heartbeat_loss(self, count: int) -> None:
        self._heartbeat_loss_count = count

    @property
    def estop_active(self) -> bool:
        return self._estop_active

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _simulate_delay(self, duration_ms: int) -> None:
        # 不真的 sleep —— 避免测试被拖慢。只记录起始时间。
        self._last_motion_started_at = time.perf_counter()
