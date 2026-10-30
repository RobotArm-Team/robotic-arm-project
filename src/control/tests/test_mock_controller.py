"""
test_mock_controller — MockController 基础安全校验单元测试。

运行: pytest src/control/tests/ -v

覆盖场景:
  1. 合法角度 → 下发成功
  2. 超限角度 → 被拒绝
  3. 急停激活 → 所有动作被拒绝
  4. 堵转舵机 → 动作被跳过
  5. 心跳丢失 ≥ 3 → read_servo_state 返回空
  6. 安全门禁 can_execute 串行短路
  7. 状态机合法/非法转换
"""

from __future__ import annotations

import os
import sys

import pytest

# 让 src 目录可被 import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.control.arm import MockController                  # noqa: E402
from src.control.safety import (                             # noqa: E402
    SERVO_LIMITS,
    can_execute,
    is_in_workspace,
    validate_servo_angle,
)
from src.control.safety.state_machine import (               # noqa: E402
    SafetyState,
    StateMachine,
)


# ---------------------------------------------------------------------------
# MockController 行为
# ---------------------------------------------------------------------------

class TestMockControllerMotion:
    def test_move_joint_within_limits(self):
        arm = MockController()
        assert arm.move_joint(1, 90.0, 300) is True
        assert arm.read_servo_state()[1] == 90.0

    def test_move_joint_over_limit_rejected(self):
        arm = MockController()
        # 1 号舵机上限 180
        assert arm.move_joint(1, 200.0, 300) is False

    def test_servo_5_range_270(self):
        arm = MockController()
        # 5 号舵机特殊: 0–270
        assert arm.move_joint(5, 250.0, 300) is True
        # 超过 270 拒绝
        assert arm.move_joint(5, 280.0, 300) is False

    def test_move_pose_atomic_rejects_any_bad_angle(self):
        arm = MockController()
        # 2 号舵机上限 180
        assert arm.move_pose({1: 90.0, 2: 200.0}, 300) is False

    def test_gripper_open_close(self):
        arm = MockController()
        assert arm.close_gripper() is True
        assert arm.open_gripper() is True

    def test_move_home(self):
        arm = MockController()
        assert arm.move_home() is True


class TestMockControllerFaultInjection:
    def test_estop_rejects_all_motion(self):
        arm = MockController(estop_active=True)
        assert arm.move_joint(1, 90.0, 300) is False
        assert arm.move_home() is False
        # 解除急停后恢复
        arm.clear_estop()
        assert arm.move_joint(1, 90.0, 300) is True

    def test_emergency_stop_is_high_priority(self):
        arm = MockController()
        arm.emergency_stop()
        assert arm.estop_active is True
        assert arm.move_joint(1, 90.0, 300) is False

    def test_stalled_servo_skips_motion(self):
        arm = MockController(stall_servo_ids={3})
        # 其他舵机正常
        assert arm.move_joint(1, 120.0, 300) is True
        # 3 号舵机堵转
        assert arm.move_joint(3, 60.0, 300) is False

    def test_heartbeat_loss_gives_empty_state(self):
        arm = MockController(heartbeat_loss=0)
        assert len(arm.read_servo_state()) == 6
        arm.set_heartbeat_loss(3)
        assert arm.read_servo_state() == {}


# ---------------------------------------------------------------------------
# 安全门禁
# ---------------------------------------------------------------------------

class TestSafetyBoundaries:
    def test_can_execute_all_pass(self):
        ok, err = can_execute(workspace_ok=True, estop_active=False, fault_cleared=True)
        assert ok is True and err is None

    def test_can_execute_estop_rejected(self):
        ok, err = can_execute(workspace_ok=True, estop_active=True, fault_cleared=True)
        assert ok is False and err == "ESTOP_ACTIVE"

    def test_can_execute_fault_rejected(self):
        ok, err = can_execute(workspace_ok=True, estop_active=False, fault_cleared=False)
        assert ok is False and err == "FAULT_NOT_CLEARED"

    def test_can_execute_workspace_rejected(self):
        ok, err = can_execute(workspace_ok=False, estop_active=False, fault_cleared=True)
        assert ok is False and err == "WORKSPACE_REJECTED"

    def test_can_execute_angle_rejected(self):
        ok, err = can_execute(
            workspace_ok=True, estop_active=False, fault_cleared=True,
            joint_angles={1: 90.0, 99: 90.0},  # 99 不是合法舵机
        )
        assert ok is False and err == "ANGLE_OUT_OF_RANGE"

    def test_can_execute_short_circuit_estop_first(self):
        """急停优先级最高 —— 即使其他门禁也失败，先返回 ESTOP_ACTIVE。"""
        ok, err = can_execute(workspace_ok=False, estop_active=True, fault_cleared=False)
        assert err == "ESTOP_ACTIVE"

    def test_validate_servo_angle(self):
        assert validate_servo_angle(1, 90.0) is True
        assert validate_servo_angle(1, 180.0) is True
        assert validate_servo_angle(1, 180.1) is False
        assert validate_servo_angle(5, 270.0) is True
        assert validate_servo_angle(99, 90.0) is False

    def test_workspace_bounds(self):
        # 默认 WORKSPACE_BOUNDS_MM = (50, -150, 200, 150)
        assert is_in_workspace(100.0, 0.0) is True
        assert is_in_workspace(10.0, 0.0) is False   # x < 50
        assert is_in_workspace(210.0, 0.0) is False  # x > 200
        assert is_in_workspace(100.0, -200.0) is False


# ---------------------------------------------------------------------------
# 状态机
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_initial_state(self):
        sm = StateMachine()
        assert sm.state == SafetyState.RECEIVED
        assert sm.is_terminal() is False

    def test_valid_transitions(self):
        sm = StateMachine()
        assert sm.transition_to(SafetyState.VALIDATING) is True
        assert sm.transition_to(SafetyState.EXECUTING) is True

    def test_invalid_transition_rejected(self):
        sm = StateMachine()
        # 不能从 RECEIVED 直接跳到 EXECUTING
        assert sm.transition_to(SafetyState.EXECUTING) is False
        # 终态不可再转
        sm.transition_to(SafetyState.VALIDATING)
        sm.transition_to(SafetyState.REJECTED)
        assert sm.is_terminal() is True
        assert sm.transition_to(SafetyState.SUCCEEDED) is False

    def test_retry_limit(self):
        sm = StateMachine()
        sm.transition_to(SafetyState.VALIDATING)
        sm.transition_to(SafetyState.EXECUTING)
        sm.transition_to(SafetyState.VERIFYING)
        sm.request_retry()        # retry_count = 1
        assert sm.state == SafetyState.RETRYING
        # 超过上限自动 FAILED
        sm2 = StateMachine()
        sm2.transition_to(SafetyState.VALIDATING)
        sm2.transition_to(SafetyState.EXECUTING)
        sm2.transition_to(SafetyState.VERIFYING)
        sm2.request_retry()
        sm2.request_retry()       # 第二次 → 超限
        assert sm2.state == SafetyState.FAILED

    def test_emergency_stop_any_state(self):
        for _ in range(3):
            sm = StateMachine()
            sm.emergency_stop()
            assert sm.state == SafetyState.SAFE_MODE
