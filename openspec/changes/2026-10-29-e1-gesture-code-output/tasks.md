# 任务清单：E1 手势输出语义变更

> 同一 PR 须链接本变更目录与对应 GitHub Issue。审阅通过后再实施。

## 必须同步修改的项

- [ ] **C（控制/安全）**
  - [ ] 在 ROS2 控制层实现 `gesture_code → 安全动作` 映射表
        （草案见 `docs/architecture/gesture-action-mapping.md`，C 可改动作语义，但急停优先级不可降）
  - [ ] 在 C 安全状态机中声明手势急停（PINCH=6）为最高优先级
- [ ] **B（集成/接口冻结）**
  - [ ] 统一编排层改为按 `gesture_code` 路由（原语义化命令路由）
  - [ ] 在接口文档注明 GestureCommand 现含 gesture_code 主键
- [ ] **A（手势/语音/验收）**
  - [ ] 本变更落地后，将实际 GESTURE_CODES 与映射关系更新回验收材料
  - [ ] 保持一致：src/gesture/gesture_command.py 为单一事实源，勿在别处硬编码编号
- [ ] **文档同步（合并后）**
  - [ ] `docs/requirements/requirements-baseline.md`：E1 输出语义改为"手势编号 + C 自定义"
  - [ ] `docs/architecture/system-architecture.md`：手势互动模块说明补充"输出编号而非命令"
  - [ ] `docs/PROJECT_PLAN.md` §3.1：更新 E1 描述

## 已完成的证据（无需重做）

- src/gesture/ 模块（recognizer / command_gate / smoother / gesture_command / app）
- 21 项单元测试通过（gate / smoother / landmarks）
- 两个 MediaPipe 模型已就位：models/gesture_recognizer.task、models/hand_landmarker.task
- recognition_log.csv 记录每次识别结果、置信度、是否执行（含 raw_confidence 列）

## 回滚条件

若 C 侧在合并前无法提供映射表，则保留原"语义化命令"基线，本变更作废。
