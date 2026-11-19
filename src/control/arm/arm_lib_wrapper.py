"""
arm_lib_wrapper — Arm_Lib 真机硬件封装。

通信: I2C (smbus.SMBus(1))，地址 0x15；仅 Linux（Atlas 200I DK A2 / 树莓派）可用。
      Windows 无 smbus，必须用 MockController。
类名: Arm_Device
源码: pip install Arm_Lib==1.0.0（PyPI 版本），或课程资料配套版本

与 ArmInterface 的对应关系:
  move_joint         → Arm_serial_servo_write(id, angle, time_ms)
  move_pose          → Arm_serial_servo_write6(s1..s6, time_ms)
  open/close_gripper → Arm_serial_servo_write(5, angle, time_ms)
  move_home          → Arm_serial_servo_write6(HOME..., time_ms)
  emergency_stop     → Arm_serial_set_torque(0) + Arm_reset() + Arm_serial_set_torque(1)
  read_servo_state   → Arm_serial_servo_read(id) 循环 1..6

Arm_Lib 内部细节（由库处理，wrapper 不再重复）:
  - id 1,6: 0–180°   id 2,3,4: 0–180°（内部镜像）  id 5: 0–270°（夹爪）
  - 2/3/4 号角度镜像（180 - angle）：Arm_Lib 内部已做，调用方给正常角度即可
  - I2C 异常全部 print 后返回 None/False

真机验证记录（#5 子 issue）:
  待在 Atlas 板子上跑；此处留空占位。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .arm_interface import ArmInterface, HOME_POSITION, MIN_DURATION_MS, MAX_DURATION_MS

logger = logging.getLogger(__name__)

# Arm_Lib 的扭矩开关：1 允许动作，0 禁止（用于急停后的保护性停臂）
_TORQUE_ON = 1
_TORQUE_OFF = 0

# 夹爪开合角度（Arm_Lib 内部做了 0–270° 线性映射）
_GRIPPER_OPEN_DEG = 200.0
_GRIPPER_CLOSE_DEG = 60.0


class ArmLibWrapper(ArmInterface):
    """把 Arm_Lib 的散装调用收敛为 7 个稳定方法。"""

    def __init__(self, device: Any = None) -> None:
        self._device = device if device is not None else self._load_device()
        # 扭矩默认开（允许动作）
        self._device.Arm_serial_set_torque(_TORQUE_ON)
        logger.info("ArmLibWrapper 就绪：扭矩打开")

    # ------------------------------------------------------------------
    # ArmInterface 实现
    # ------------------------------------------------------------------

    def move_joint(self, servo_id: int, angle: float, duration_ms: int) -> bool:
        if self._validate_single(servo_id, angle, duration_ms):
            return False
        try:
            self._device.Arm_serial_servo_write(servo_id, int(angle), int(duration_ms))
            return True
        except Exception:  # noqa: BLE001 — I2C 异常转化为拒绝，不崩溃
            logger.exception("Arm_serial_servo_write 失败 servo=%s angle=%s", servo_id, angle)
            return False

    def move_pose(self, joints: dict[int, float], duration_ms: int) -> bool:
        if self._validate_pose(joints, duration_ms):
            return False
        try:
            # Arm_serial_servo_write6 参数顺序固定 1..6，缺失的按 HOME 补齐
            s1 = int(joints.get(1, HOME_POSITION[1]))
            s2 = int(joints.get(2, HOME_POSITION[2]))
            s3 = int(joints.get(3, HOME_POSITION[3]))
            s4 = int(joints.get(4, HOME_POSITION[4]))
            s5 = int(joints.get(5, HOME_POSITION[5]))
            s6 = int(joints.get(6, HOME_POSITION[6]))
            self._device.Arm_serial_servo_write6(s1, s2, s3, s4, s5, s6, int(duration_ms))
            return True
        except Exception:  # noqa: BLE001
            logger.exception("Arm_serial_servo_write6 失败 joints=%s", joints)
            return False

    def open_gripper(self) -> bool:
        return self.move_joint(5, _GRIPPER_OPEN_DEG, 500)

    def close_gripper(self) -> bool:
        return self.move_joint(5, _GRIPPER_CLOSE_DEG, 500)

    def move_home(self) -> bool:
        return self.move_pose(HOME_POSITION, 1000)

    def emergency_stop(self) -> bool:
        """
        急停序列:
          1. 关扭矩 —— 立即禁止舵机动作
          2. Arm_reset() —— 重启驱动板，清空队列
          3. 扭矩保持关闭 —— 直到 move_home 或显式 set_torque(1)
        参考 Arm_Lib: Arm_serial_set_torque / Arm_reset
        """
        try:
            self._device.Arm_serial_set_torque(_TORQUE_OFF)
            self._device.Arm_reset()
            logger.warning("ArmLibWrapper emergency_stop: torque off + reset")
            return True
        except Exception:  # noqa: BLE001
            logger.exception("emergency_stop 下发失败")
            return False

    def read_servo_state(self) -> dict[int, float]:
        state: dict[int, float] = {}
        for sid in range(1, 7):
            try:
                pos = self._device.Arm_serial_servo_read(sid)
            except Exception:  # noqa: BLE001
                logger.exception("Arm_serial_servo_read servo=%s 失败", sid)
                return {}
            if pos is None:
                logger.warning("Arm_serial_servo_read servo=%s 返回 None，I2C 可能掉线", sid)
                return {}
            state[sid] = float(pos)
        return state

    # ------------------------------------------------------------------
    # 真机辅助（不在 ArmInterface 里，供调试用）
    # ------------------------------------------------------------------

    def set_torque(self, on: bool) -> None:
        self._device.Arm_serial_set_torque(_TORQUE_ON if on else _TORQUE_OFF)

    def hardware_version(self) -> Optional[str]:
        try:
            return self._device.Arm_get_hardversion()
        except Exception:  # noqa: BLE001
            return None

    def ping_servo(self, servo_id: int) -> Optional[int]:
        try:
            return self._device.Arm_ping_servo(servo_id)
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _load_device() -> Any:
        try:
            from Arm_Lib import Arm_Device  # type: ignore
        except ImportError as exc:  # pragma: no cover — 只在真机环境可触发
            raise RuntimeError(
                "未安装 Arm_Lib（或当前平台无 smbus）；请切换到 Atlas 板子运行，"
                "或在 Windows 上使用 MockController（ARM_BACKEND=mock）。"
            ) from exc
        logger.info("ArmLibWrapper 加载 Arm_Device（I2C 地址 0x15, SMBus 1）")
        return Arm_Device()
