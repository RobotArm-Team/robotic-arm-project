# 变更提案：E1 手势输出改为「手势编号 + C 自定义舵机动作」

- 提案人：A（手势/语音/验收）
- 日期：2026-10-29
- 状态：**草案，待 B（集成/接口冻结）、C（控制/安全）审阅**
- 关联基线：docs/PROJECT_PLAN.md §3.1、docs/architecture/system-architecture.md

## 1. 当前基线（被冻结的内容）

PROJECT_PLAN §3.1 原文要求 E1 实现「启动、暂停、复位、取消、急停等有限命令」，
手势模块**直接输出统一命令**（隐含语义化命令，如 start/pause/reset/cancel/estop）。

## 2. 拟议变化

将 E1 的输出语义从「语义化高层命令」改为「**手势编号（gesture_id + gesture_code）+ 置信度**」：

- A 侧**只负责识别并输出"用户打了哪个手势"**（编号 1–7，见 gesture_command.GESTURE_CODES）。
- **不**在 A 侧绑定任何舵机动作；具体某个手势对应什么机械臂运动，由 **C 在其安全控制边界内自定义**。
- A 与 C 之间通过 `GestureCommand`（gesture_id / gesture_code / confidence / source / timestamp）解耦，
  与 system-architecture.md 中「手势只触发受限、可审计动作」「经 C 安全校验」完全一致。

## 3. 为什么要改

1. **职责清晰**：A 不决定机械臂如何动，避免"绕过 C 安全边界直接控舵机"的合规风险。
2. **可扩展**：新增手势只需在 GESTURE_CODES 加编号，C 侧映射表同步即可，不改接口契约。
3. **与现状一致**：实际实现（src/gesture/）已按此架构落地并通过 21 项单元测试；本变更是把"已落地的实现"反向同步回冻结文档。

## 4. 影响方

- A：输出契约不变（仍是 GestureCommand），仅语义从"命令"变为"手势编号"。
- B：统一编排层消费 GestureCommand 时，按 gesture_code 路由给 C（原语义化路由改为编号路由）。
- C：新增 `gesture_code → 安全动作` 映射表（见 tasks.md / docs/architecture/gesture-action-mapping.md 草案），
  且急停手势必须保留最高安全优先级。
- 文档：requirements-baseline.md、system-architecture.md 的 E1 描述需同步。

## 5. 风险与缓解

- 风险：C 未定义映射时手势无动作。缓解：提供草案映射表（默认安全动作），并在合并前由 C 确认。
- 风险：编号漂移导致跨模块误解。缓解：GESTURE_CODES 作为单一事实源，C 侧以 gesture_code 为主键查表。
