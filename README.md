# 智能机械臂垃圾分拣与管理系统

> 以彩色方块模拟四类垃圾的视觉识别、固定工作区抓取、事件记录与 Web 管理系统。
> 课程项目仓库；当前处于需求冻结与工程骨架阶段，尚未宣称功能已实现。

## 项目目标

系统完成一条可审计的闭环：

`USB 摄像头 → YOLOv8 识别 → 手眼标定换算 → ROS2 / Arm_Lib 控制机械臂 → 事件落库 → Web 看板展示`

课程实验用四种彩色方块分别代表可回收垃圾（蓝）、有害垃圾（红）、厨余垃圾（绿）和其他垃圾（黄）；模型识别与机械臂分拣的对象是这些方块。具体图文面与标签说明见[视觉数据集说明](docs/vision/COURSE_DATASET_NOTES.md)。

除基础链路外，项目包含两个独立、可关闭的拓展：

- **E1 手势互动：** 特定手势触发机械臂在安全区执行预设动作并回到安全位。
- **E2 语音控制：** 识别“帮我分类”后触发一次完整分拣；低置信度不触发。

详细需求基线见 [docs/requirements/requirements-baseline.md](docs/requirements/requirements-baseline.md)，模块关系见 [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md)。

## 验收摘要

| 功能 | 数字化通过标准 |
|---|---|
| F1 视觉识别 | mAP@0.5 ≥ 0.80；每类 Recall ≥ 0.75；单帧推理 P95 ≤ 150 ms。 |
| F2 任意位置分拣 | 3×3 网格、10 个未预置位置；一次成功率 ≥ 85%；含一次重试完成率 ≥ 95%；单点周期 P95 ≤ 15 s；越界拒绝率 100%。 |
| F3 管理看板 | 总览、实时事件、分类统计、异常日志 4 页；事件展示延迟 P95 ≤ 1 s；字段完整率 100%。 |
| F4 兜底机制 | 五类异常均有可观测响应；10 次演示至少成功 8 次；不安全动作 0 次。 |
| E1 手势互动 | 正确率 ≥ 90%；触发延迟 P95 ≤ 1 s；动作越界 0 次。 |
| E2 语音控制 | 40 次有效指令中启动比例 ≥ 90%；响应 P95 ≤ 2 s；20 条无关语音误触发率 ≤ 5%。 |

这些是**待验证的验收阈值**，最终结论以版本化的测试记录为准。

## 范围边界

为保证固定工作区内的安全与稳定，本项目不做：

1. 动态传送带上的连续追踪与分拣；
2. 任意高度、堆叠或严重遮挡下的三维抓取；
3. 透明、柔性、液体或超出夹爪能力物体的处理。

## 快速导航

| 内容 | 入口 |
|---|---|
| 需求基线与验收 | [docs/requirements/requirements-baseline.md](docs/requirements/requirements-baseline.md) |
| 系统架构与安全门禁 | [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) |
| Web 接口契约 | [api/openapi.yaml](api/openapi.yaml) |
| 需求—任务—交付物追溯 | [docs/TRACEABILITY.md](docs/TRACEABILITY.md) |
| 协作规则与 PR 流程 | [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) |
| 课程资料盘点与使用边界 | [docs/course-reference/COURSE_PLATFORM_MATERIALS.md](docs/course-reference/COURSE_PLATFORM_MATERIALS.md) |
| 彩色方块与四类垃圾映射 | [docs/vision/COURSE_DATASET_NOTES.md](docs/vision/COURSE_DATASET_NOTES.md) |
| OpenSpec 变更流程 | [openspec/README.md](openspec/README.md) |

## 目录结构

```text
.
├── api/                    # OpenAPI 3.0 契约；Swagger UI 的唯一来源
├── docs/
│   ├── architecture/       # 架构、安全门禁和模块边界
│   ├── requirements/       # 需求基线与验收标准
│   ├── CONTRIBUTING.md     # 协作约定
│   └── TRACEABILITY.md     # 需求、Issue、PR、证据的映射
├── openspec/               # 需求、接口和安全变更的规格审查记录
├── src/                    # 后续按 vision/control/backend/web 放置实现
└── .github/                # Issue、PR 和代码所有者模板
```

## 四人职责与交付物

贡献以 Issue、PR、测试证据和可点验交付物核定；B 作为组长额外负责总体集成与发布。

| 成员 | 职责 | 主要可点验交付物 |
|---|---|---|
| A | E1 手势控制、E2 语音控制、数据标注抽检、系统测试与验收材料 | 双模态控制服务、数据质量记录、测试证据、验收报告。 |
| B | F1 视觉识别、数据标注、YOLOv8 训练、模型部署、总体集成与发布 | 数据集版本、模型权重、推理服务、mAP/Recall/耗时报告、集成脚本与发布记录。 |
| C | F2 动作分拣、ROS2 控制、Arm_Lib 适配、安全边界 | 标定参数、控制节点、舵机限位记录、随机位置抓取记录。 |
| D | F3 全栈管理平台（Java 后端、数据库、Web 看板）、F4 异常日志、自动化测试 | 数据库模型、4 页看板、事件对账、延迟报告、JUnit 与前端测试脚本。 |

## 协作与质量规则

- 每项可交付工作先创建 GitHub Issue，写明负责人、验收数字、截止时间和关联需求编号。
- 任何代码、接口或文档变更均从功能分支经 Pull Request 合并；`main` 仅保留可演示版本。
- 需求、接口、风险或安全门禁变化，先在 `openspec/changes/` 提出规格变更，再实施代码修改。
- 前后端 HTTP 接口以 `api/openapi.yaml` 为单一事实来源；不得仅通过口头或聊天记录改字段。
- 未通过工作区、角度限位、急停和故障状态检查的机械臂任务不得下发。

## 硬件与安全

- 平台：Atlas 200I DK A2（4 核 CPU、4 GB 内存、8 TOPS INT8）。
- 机械臂：6 个舵机；1/2/3/4/6 号为 0°–180°，5 号为 0°–270°。
- 控制：UART 115200，经 Arm_Lib 控制；K2 急停必须保持可用。
- 成功定义：舵机状态回读正常，且抓后视觉二次确认通过。

不提交原始语音、手势或其他含个人信息的数据；仅保留经同意的脱敏统计和必要的事件证据。

## 当前状态

- [x] 需求基线、接口契约和协作规则入库。
- [ ] 视觉、控制、后端和 Web 实现。
- [ ] 硬件联调与验收记录。

项目原创内容许可证：Apache-2.0，见 [LICENSE](LICENSE)。`docs/course-reference/` 中的课程原始资料另见其[来源与使用说明](docs/course-reference/COURSE_PLATFORM_MATERIALS.md)，不自动适用 Apache-2.0。
