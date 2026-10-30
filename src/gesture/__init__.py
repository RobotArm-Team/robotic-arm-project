"""E1 手势识别模块（成员 A 侧）。

职责边界：本包只负责"识别手势 -> 输出 GestureCommand（手势编号/标识）"，
绝不调用 Arm_Lib / 串口直接控制舵机。真实舵机动作由 C 读取 GestureCommand 后，
经安全校验执行。

识别方案：MediaPipe 预训练手部关键点（无需训练）+ 规则分类。
"""

from .gesture_command import GestureCommand, GESTURE_CODES, CODE_TO_GESTURE
from .command_gate import CommandGate
from .landmarks import classify_gesture, finger_states

__all__ = [
    "GestureCommand",
    "GESTURE_CODES",
    "CODE_TO_GESTURE",
    "CommandGate",
    "classify_gesture",
    "finger_states",
]
