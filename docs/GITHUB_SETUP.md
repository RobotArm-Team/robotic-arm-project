# GitHub 平台配置清单

本文件对应仓库中已提交的模板；以下设置必须由拥有 Organization / Repository 管理权限的成员在 GitHub 页面完成。

## 1. 成员与团队

在 Organization 中邀请四位成员，并创建或等价配置四个团队：

| 团队 | 对应 PPT 职责 |
|---|---|
| `team-a` | A：E1 手势、E2 语音、数据抽检、系统测试与验收。 |
| `team-b` | B：F1 视觉、数据、YOLOv8、部署、总体集成与发布。 |
| `team-c` | C：F2、ROS2、Arm_Lib、安全边界。 |
| `team-d` | D：F3 全栈、F4、Web、自动化测试。 |

随后将 `.github/CODEOWNERS` 中的注释行去掉。若不创建 GitHub Team，则把相应位置改成真实的 GitHub 用户名，例如 `@username`。

## 2. main 分支保护

在 **Settings → Branches → Add branch ruleset**，目标为 `main`，建议开启：

- Require a pull request before merging；
- Require approvals：`1`；
- Dismiss stale approvals when new commits are pushed；
- Require review from Code Owners（仅在 CODEOWNERS 已替换真实账号后开启）；
- Block force pushes；
- Block deletions；
- Do not allow bypassing the above settings。

课程项目不需要为“看起来规范”而勾选尚未配置的 CI 必须检查；等真正有自动检查后再加入 required status checks。

## 3. 标签

创建以下标签，便于 Project 看板和答辩追溯：

| 标签 | 颜色建议 | 用途 |
|---|---|---|
| `F1`、`F2`、`F3`、`F4` | 蓝色系 | 基础功能归属。 |
| `E1`、`E2` | 紫色系 | 拓展功能归属。 |
| `api`、`docs`、`integration` | 青色系 | 横向工作。 |
| `safety` | 红色 | 急停、限位、越界、故障等问题。 |
| `bug`、`triage` | 橙色/灰色 | 缺陷与待分流事项。 |
| `A`、`B`、`C`、`D` | 绿色系 | 第一负责人。 |

## 4. 里程碑与初始 Issue

创建 4 个里程碑：

1. `M0 需求冻结`：需求、接口和协作规则评审完成；
2. `M1 模块可运行`：视觉、控制、Web 的模拟输入可独立运行；
3. `M2 集成与真机联调`：主链路、异常和安全门禁联调；
4. `M3 验收与答辩`：验收记录、演示材料与答辩完成。

首批创建以下 8 个 Issue，并使用仓库的“功能或文档任务”模板：

| 标题 | 负责人 | 标签 | 里程碑 |
|---|---|---|---|
| `[F1] 数据集版本与视觉推理服务` | B | `F1`, `B` | M1 |
| `[F2] 标定、ROS2 控制与工作区门禁` | C | `F2`, `safety`, `C` | M1 |
| `[F3] 事件服务与四页 Web 看板` | D | `F3`, `D` | M1 |
| `[F4] 错误码、降级状态与异常日志` | D | `F4`, `safety`, `D` | M2 |
| `[E1] 手势互动与安全区动作` | A | `E1`, `safety`, `A` | M2 |
| `[E2] 语音命令与低置信度拒绝` | A | `E2`, `A` | M2 |
| `[API] 实现并维护 OpenAPI 契约` | D | `api`, `D` | M1 |
| `[INT] 集成、版本标签与验收材料` | B | `integration`, `B` | M3 |

## 5. GitHub Project

创建一个 Organization Project，名称建议为 **智能机械臂垃圾分拣｜课程项目**。添加以下字段：

- `Status`：Backlog / Ready / In Progress / In Review / Done；
- `Owner`：A / B / C / D；
- `Milestone`：M0 / M1 / M2 / M3；
- `Acceptance`：填写 Issue 的验收数字；
- `Evidence`：填写 PR、版本 tag、文档或演示记录链接。

将首批 8 个 Issue 加入 Project。每周飞书周会后更新状态；重要决定回写到 Issue 或文档，而不是只停留在飞书聊天。
