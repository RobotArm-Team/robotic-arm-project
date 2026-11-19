#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_i2c.py — 在 Atlas 板子上本地跑的只读验证脚本。

用途: 确认 smbus/I2C 就绪、Arm_Lib 能导入、6 舵机能回读。
      不驱动舵机运动，只做"能不能通信"的验证。

运行 (板子上):
  python3 verify_i2c.py

期望输出:
  [OK] 板子信息 + Python/Pip 版本
  [OK] Arm_Lib 导入成功
  [OK] I2C 设备存在 (/dev/i2c-1)
  [OK] 硬件版本号可读
  [OK] 每个舵机的 ping 值 (正常≈0xda) 与当前角度
"""

from __future__ import annotations

import sys


def section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def main() -> int:
    section("1. 板子基本信息")
    import os
    import platform
    print(f"  hostname : {platform.node()}")
    print(f"  platform : {platform.platform()}")
    print(f"  user     : {os.environ.get('USER', os.environ.get('HOME'))}")
    print(f"  python   : {sys.version.split()[0]}")
    try:
        import pip
        ok(f"pip 可用 ({pip.__file__})")
    except ImportError:
        try:
            import pip  # noqa: F401
            ok("pip 可用")
        except Exception:
            fail("pip 不可用 — 需要先装才能 pip install Arm_Lib")

    section("2. smbus / I2C 设备")
    I2C_DEV = "/dev/i2c-1"
    if os.path.exists(I2C_DEV):
        ok(f"{I2C_DEV} 存在")
        try:
            import smbus
            ok(f"smbus 模块可导入 (Python版本{smbus.__class__.__module__})")
        except ImportError:
            fail("smbus 模块不可导入 — 需 apt install python3-smbus / i2c-tools")
    else:
        fail(f"{I2C_DEV} 不存在 — i2c-dev 模块可能没加载或板子没启用 I2C")

    section("3. Arm_Lib 导入")
    try:
        import Arm_Lib  # noqa: F401
        from Arm_Lib import Arm_Device
        ok(f"Arm_Lib 可导入: {Arm_Lib.__file__}")
    except ImportError as exc:
        fail(f"Arm_Lib 不可导入: {exc}")
        print("\n  安装命令 (板子上):")
        print("    pip3 install Arm_Lib==1.0.0")
        print("  若板子无外网，Windows 上先 wheel 打包:")
        print("    python -m wheel Arm_Lib==1.0.0 -w .")
        print("    scp Arm_Lib-1.0.0-py3-none-any.whl <user>@<ip>:~/")
        print("    板子上: pip3 install ~/Arm_Lib-1.0.0-py3-none-any.whl")
        return 2

    section("4. 打开 Arm_Device + 读硬件版本")
    try:
        arm = Arm_Device()
        ok("Arm_Device 实例化成功 (I2C 地址 0x15, SMBus 1)")
    except Exception as exc:
        fail(f"Arm_Device 实例化失败: {exc}")
        return 3

    try:
        ver = arm.Arm_get_hardversion()
        ok(f"硬件版本: {ver}")
    except Exception as exc:
        fail(f"Arm_get_hardversion 失败: {exc}")

    section("5. 6 舵机 ping + 当前角度 (只读，不驱动)")
    problems = 0
    for sid in range(1, 7):
        try:
            ping_val = arm.Arm_ping_servo(sid)
            pos = arm.Arm_serial_servo_read(sid)
            ping_hex = f"0x{ping_val:02x}" if ping_val is not None else "None"
            if pos is None:
                fail(f"servo {sid}: ping={ping_hex} angle=None (I2C 可能掉线)")
                problems += 1
            else:
                ok(f"servo {sid}: ping={ping_hex} angle={pos}°")
        except Exception as exc:  # noqa: BLE001
            fail(f"servo {sid}: 读取异常 {exc}")
            problems += 1

    section("结果汇总")
    if problems == 0:
        print("  全部舵机可读，I2C 链路 OK —— 可以进骨架验证步骤。")
        return 0
    else:
        print(f"  {problems} 个舵机有问题，请检查:")
        print("    - 舵机板是否已上电")
        print("    - I2C 接线 (SDA/SCL/GND) 是否正确")
        print("    - 控制板 I2C 地址是否仍是 0x15 (Arm_Lib 默认)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
