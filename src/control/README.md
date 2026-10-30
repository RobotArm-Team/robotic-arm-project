# control — 机械臂控制、标定与安全边界模块

> 负责人：**C**
> 主责：F2 任意位置分拣、ROS2 控制层、Arm_Lib 适配、安全边界。

## 目录结构

```
control/
├── README.md               # 本文件
├── requirements.txt
├── arm/
│   ├── arm_interface.py    # 稳定抽象接口 —— 所有动作必须通过此接口
│   ├── factory.py          # create_arm_controller()：按 ARM_BACKEND 选择 Mock / 真机
│   ├── arm_lib_wrapper.py  # Arm_Lib 真实封装（方法名待真机确认）
│   └── mock_controller.py  # 无硬件时联调用的 Mock 控制器 ← 现在就能用
├── safety/
│   ├── boundaries.py       # SERVO_LIMITS、WORKSPACE_BOUNDS、can_execute()
│   └── state_machine.py    # 控制侧安全状态机 + 超时/故障阈值
├── calibration/            # 3×3 标定网格 + pixel_to_world（第 2 周实现）
├── ros2/                   # ROS2 节点 + 状态发布（第 2 周实现）
├── actions/                # 动作序列 + 抓-复检-重试流程（第 3 周实现）
└── tests/                  # pytest：Mock 行为、安全门禁、状态机、工厂
```

## 选择 Mock 或真实硬件（ARM_BACKEND）

业务代码统一调用工厂，不直接 new 具体实现：

```python
from src.control.arm import create_arm_controller

arm = create_arm_controller()   # 读取 ARM_BACKEND，默认 mock
```

| ARM_BACKEND | 使用的实现 | 前提 |
|---|---|---|
| `mock`（默认） | `MockController` | 无，任何机器可跑 |
| `real` | `ArmLibWrapper` | 已安装 `Arm_Lib`、UART 115200 已连通 |

设置方式（PowerShell）：

```powershell
$env:ARM_BACKEND = "real"   # 切真机
$env:ARM_BACKEND = "mock"   # 切回 Mock
```

## 快速开始：用 Mock 控制器联调

Mock 控制器不依赖任何硬件，A / B / D 三方都可以直接用：

```python
from src.control.arm import MockController

arm = MockController()

# 安全待机位
arm.move_home()

# 单舵机运动（自动校验角度限位）
arm.move_joint(1, 120.0, 500)

# 多舵机同步运动
arm.move_pose({1: 90.0, 2: 100.0}, 800)

# 夹爪
arm.close_gripper()
arm.open_gripper()

# 急停（最高优先级，立即停止）
arm.emergency_stop()

# 舵机状态回读
state = arm.read_servo_state()  # → {1: 90.0, 2: 100.0, ...}
```

### 故障注入（用于测试异常路径）

```python
arm = MockController(
    estop_active=False,          # 模拟 K2 急停按下
    stall_servo_ids={3},         # 模拟 3 号舵机堵转
    heartbeat_loss=0,            # 连续丢失心跳计数；≥3 时 read_servo_state() 返回 {}
)

# 或者运行时动态设置
arm.set_stall({3})
arm.set_heartbeat_loss(3)
arm.clear_estop()
```

## 安全门禁（can_execute）

任何动作下发前必须通过以下串行校验，任一门禁不满足立即返回对应错误码：

| 顺序 | 检查项 | 错误码 |
|---|---|---|
| 1 | 急停是否按下 | `ESTOP_ACTIVE` |
| 2 | 故障是否未清除（堵转 / 通信超时 / 心跳丢失） | `FAULT_NOT_CLEARED` |
| 3 | 目标点是否在工作区内 | `WORKSPACE_REJECTED` |
| 4 | 舵机目标角度是否在限位内 | `ANGLE_OUT_OF_RANGE` |

```python
from src.control.safety import can_execute, is_in_workspace, SERVO_LIMITS

ok, err = can_execute(
    workspace_ok=is_in_workspace(150.0, 0.0),
    estop_active=False,
    fault_cleared=True,
)
if not ok:
    print(f"Rejected: {err}")
```

## 舵机角度硬限制

| 舵机编号 | 角度范围 | 说明 |
|---|---|---|
| 1, 2, 3, 4, 6 | 0° – 180° | 关节 |
| **5** | **0° – 270°** | 夹爪（特殊！） |

## 与其他模块的接口契约

### ← 接收自 B（视觉服务）

```json
{
  "task_id": "task-001",
  "class_id": "plastic",
  "pixelX": 426,
  "pixelY": 237,
  "confidence": 0.91
}
```

C 调用 `calibrator.pixel_to_world(pixelX, pixelY)` → `(x_mm, y_mm)` → 构造 `TargetPose` → 执行抓取。

### → 交付给 B / D（PickResult）

严格对齐 `api/openapi.yaml` 的 `PickResult` schema：

```json
{
  "task_id": "task-001",
  "status": "SUCCEEDED",
  "servo_state": {"1": 90.0, "2": 100.0, "3": 85.0, "4": 90.0, "5": 60.0, "6": 90.0},
  "vision_verified": true,
  "retry_count": 0,
  "duration_ms": 3200.0,
  "error_code": null
}
```

`status` 枚举值：`RECEIVED / REJECTED / EXECUTING / RETRYING / SUCCEEDED / FAILED / SAFE_MODE`

## 运行环境

- Python ≥ 3.10
- 无硬件时：仅需 `numpy`、`pytest`
- 有硬件时：安装 `Arm_Lib`（UART 115200）+ ROS 2 `rclpy`

Arm_Lib 与 rclpy 均采用可选导入，Mock 控制器可在任何机器上独立运行。

## 安全红线（绝对不能绕过）

1. 急停最高优先级 —— K2 或软件急停触发后，任何手势/语音/视觉命令都不能覆盖
2. 未知状态 = 停止 —— 通信超时 (2s)、堵转 (3s)、心跳丢失 (≥3) → 立即停臂
3. 真机测试必须有人值守 —— 旁边必须有能按急停的人
4. 严禁业务模块直接调用 `Arm_Lib.Arm_Device` —— 必须走 `ArmInterface`

## 测试

```powershell
python -m pytest src/control/tests/ -q
```

当前 28 个用例覆盖：角度限位、急停优先级、堵转跳过、心跳丢失、安全门禁短路、状态机转换与重试上限、控制器工厂。

## 本周（第 1 周）完成状态

| 文件 | 状态 | 说明 |
|---|---|---|
| `arm/arm_interface.py` | ✅ 已完成 | 7 方法抽象接口 + 参数校验 |
| `arm/mock_controller.py` | ✅ 已完成 | Mock 舵机 + 4 种故障注入 |
| `arm/factory.py` | ✅ 已完成 | `ARM_BACKEND` 选 Mock / 真机 |
| `arm/arm_lib_wrapper.py` | ⚠️ 待真机 | 结构完成，`Arm_serial_servo_*` 方法名需真机确认 |
| `safety/boundaries.py` | ✅ 已完成 | 舵机限位 + 工作区 + 安全门禁 |
| `safety/state_machine.py` | ✅ 已完成 | 状态机 + 超时常量 |
| `calibration/calibrator.py` | ⏳ 第 2 周 | 3×3 网格标定 |
| `ros2/arm_node.py` | ⏳ 第 2 周 | ROS2 节点（topic 名待与 B 确认） |
| `actions/sequences.py` | ⏳ 第 3 周 | 动作序列 + 抓-复检-重试 |
