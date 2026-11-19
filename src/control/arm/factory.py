"""
factory — 控制器工厂：按环境变量选择 Mock 或真实硬件。

用法:
    ARM_BACKEND=mock  (默认) → MockController，任何机器可运行
    ARM_BACKEND=real          → ArmLibWrapper，需要 Arm_Lib 与串口

A / B / D 联调时无需改代码，只切换环境变量即可。
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .arm_interface import ArmInterface
from .mock_controller import MockController

logger = logging.getLogger(__name__)

ENV_BACKEND = "ARM_BACKEND"


def create_arm_controller(backend: Optional[str] = None) -> ArmInterface:
    """创建控制器实例。backend 缺省时读取环境变量 ARM_BACKEND（默认 mock）。"""
    resolved = (backend or os.getenv(ENV_BACKEND, "mock")).strip().lower()

    if resolved == "mock":
        logger.info("使用 MockController")
        return MockController()
    if resolved == "real":
        from .arm_lib_wrapper import ArmLibWrapper

        logger.info("使用 ArmLibWrapper（真实硬件）")
        return ArmLibWrapper()

    raise ValueError(f"未知 {ENV_BACKEND}={resolved!r}，可选值: mock / real")
