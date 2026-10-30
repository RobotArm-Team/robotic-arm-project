"""
boundaries — 舵机限位、工作区边界、安全门禁校验函数。

所有机械臂动作在下发前必须通过 can_execute() 函数的串行检查；
任一门禁不满足，控制层拒绝执行并返回对应 ERROR_CODES。

硬约束来源:
  - docs/requirements/requirements-baseline.md（舵机范围、工作区）
  - docs/architecture/system-architecture.md（安全门禁）
  - api/openapi.yaml（错误码 WORKSPACE_REJECTED 等）
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 舵机角度硬限制 (°)。1-4、6 为 0–180；5 号为 0–270。
SERVO_LIMITS: dict[int, tuple[float, float]] = {
    1: (0.0, 180.0),
    2: (0.0, 180.0),
    3: (0.0, 180.0),
    4: (0.0, 180.0),
    5: (0.0, 270.0),
    6: (0.0, 180.0),
}

# 工作台有效工作区 (mm)。以机械臂基座为原点。
# 具体数值需在真机标定后填入；此处为占位值。
WORKSPACE_BOUNDS_MM: tuple[float, float, float, float] = (50.0, -150.0, 200.0, 150.0)
# (x_min, y_min, x_max, y_max)

# 可观测错误码 —— 必须与 openapi.yaml 的 ErrorResponse.code 对齐
ERROR_CODES = {
    "WORKSPACE_REJECTED": "目标点超出有效工作区",
    "ANGLE_OUT_OF_RANGE": "舵机目标角度超出物理限位",
    "ESTOP_ACTIVE": "急停已按下，禁止执行任何动作",
    "FAULT_NOT_CLEARED": "存在未清除故障",
    "IDEMPOTENCY_COLLISION": "重复 task_id，幂等冲突",
    "SERVO_NOT_FOUND": "舵机编号不存在",
    "DURATION_OUT_OF_RANGE": "运动时长超出允许范围",
    "EMPTY_POSE": "目标姿态为空",
}


# ---------------------------------------------------------------------------
# 校验函数
# ---------------------------------------------------------------------------


def validate_servo_angle(servo_id: int, angle: float) -> bool:
    """检查单个舵机的目标角度是否在合法范围内。"""
    if servo_id not in SERVO_LIMITS:
        return False
    lo, hi = SERVO_LIMITS[servo_id]
    return lo <= angle <= hi


def is_in_workspace(x_mm: float, y_mm: float) -> bool:
    """
    判断目标点是否位于有效工作区内。
    越界拒绝率必须 100%（验收硬指标）。
    """
    x_min, y_min, x_max, y_max = WORKSPACE_BOUNDS_MM
    return x_min <= x_mm <= x_max and y_min <= y_mm <= y_max


def can_execute(
    *,
    workspace_ok: bool,
    estop_active: bool,
    fault_cleared: bool,
    joint_angles: Optional[dict[int, float]] = None,
) -> tuple[bool, Optional[str]]:
    """
    串行执行全部安全门禁检查。

    Args:
        workspace_ok: 目标点是否在有效工作区内。
        estop_active: 急停是否被按下（K2 或软件急停）。
        fault_cleared: 是否存在未清除故障（堵转、通信超时等）。
        joint_angles: 可选；舵机目标角度字典，会逐一校验限位。

    Returns:
        (通过与否, 错误码或 None)。
        门禁检查按顺序短路，返回第一个未通过的错误码。
    """
    # 1. 急停 —— 最高优先级，直接拒绝
    if estop_active:
        return False, "ESTOP_ACTIVE"

    # 2. 故障未清除
    if not fault_cleared:
        return False, "FAULT_NOT_CLEARED"

    # 3. 工作区
    if not workspace_ok:
        return False, "WORKSPACE_REJECTED"

    # 4. 舵机角度（如果有目标角度）
    if joint_angles:
        for sid, ang in joint_angles.items():
            if not validate_servo_angle(sid, ang):
                return False, "ANGLE_OUT_OF_RANGE"

    return True, None
