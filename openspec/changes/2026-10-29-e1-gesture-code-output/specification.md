# 规格说明：E1 手势识别输出契约

> 本文档描述变更生效后 E1 的明确行为与验收条件。

## 1. 输出数据对象（契约）

A 侧每成功确认一次手势，输出一个 `GestureCommand`：

| 字段 | 类型 | 说明 |
|---|---|---|
| gesture_id | str | 手势名称，如 "FIST" / "OPEN_PALM"（来自 GESTURE_CODES 键） |
| gesture_code | int | 稳定整数编号 1–7，C 侧查表主键；0 表示 NONE/UNKNOWN，不下发 |
| confidence | float | 窗口峰值置信度，0–1 |
| source | str | 固定 "gesture"（与语音 "voice" 区分） |
| timestamp | str | ISO 简化时间 |
| task_id | str\|None | 由 B 统一编排层分配；A 侧可留空 |

- 编号映射（单一事实源，`src/gesture/gesture_command.py`）：
  1=FIST, 2=OPEN_PALM, 3=POINT_UP, 4=PEACE, 5=ROCK, 6=PINCH, 7=THUMBS_UP, 0=NONE/UNKNOWN。
- **NONE/UNKNOWN（code 0）绝不下发**（command_gate 已拦截，单测覆盖）。

## 2. 确认与下发规则（A 侧，已落地）

- 连续 5 帧中至少 4 帧一致才确认一次手势（防抖）。
- 同一手势确认后进入 **10 秒冷却**，冷却期内仅记录不触发。
- 门限判定用**窗口平均置信度**（默认 ≥0.5）；下发给 C 的 confidence 用**窗口峰值**（更直观，但门限仍看平均，防单帧抖动通过）。
- 可选 `--calibrate` 仅做展示校准（c→c**0.6），原始置信度仍写入日志的 raw_confidence 列，供验收复查。

## 3. 安全约束（不可放宽）

- A **不直接调用 Arm_Lib / 串口 / 舵机**；只产出 GestureCommand。
- 任何手势动作必须经 **C 的安全状态机**（RECEIVED→VALIDATING→EXECUTING→VERIFYING→SUCCEEDED / SAFE_MODE）。
- 急停类手势（草案为 PINCH=6）必须拥有**最高安全优先级**，超越其它手势与语音命令。

## 4. 验收条件

1. 7 种手势在真实摄像头下识别准确率 ≥90%（沿用 §3.1 指标）。
2. 响应 P95 ≤1 秒。
3. NONE/UNKNOWN 与冷却期内重复手势**不产生任何越界动作**（有 21 项单测 + 日志佐证）。
4. C 侧映射表就绪且急停优先级已声明。
