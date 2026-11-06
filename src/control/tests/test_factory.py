"""控制器工厂选择 Mock / 真机的单元测试。"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.control.arm import MockController, create_arm_controller  # noqa: E402
from src.control.arm.factory import ENV_BACKEND                    # noqa: E402


def test_default_backend_is_mock(monkeypatch):
    monkeypatch.delenv(ENV_BACKEND, raising=False)
    assert isinstance(create_arm_controller(), MockController)


def test_explicit_mock(monkeypatch):
    monkeypatch.delenv(ENV_BACKEND, raising=False)
    assert isinstance(create_arm_controller("mock"), MockController)


def test_env_selects_mock(monkeypatch):
    monkeypatch.setenv(ENV_BACKEND, "mock")
    assert isinstance(create_arm_controller(), MockController)


def test_unknown_backend_raises():
    with pytest.raises(ValueError):
        create_arm_controller("invalid")


def test_real_without_arm_lib_raises():
    """真机后端在无 Arm_Lib 环境下必须报明确错误，而不是静默降级。"""
    try:
        import Arm_Lib  # type: ignore  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError):
            create_arm_controller("real")
