# 系统架构与模块边界

## 逻辑架构

```text
USB Camera
    │ image frame
    ▼
视觉服务（B：YOLOv8） ── DetectionResult ──► 标定/任务编排（B/C）
                                                │ TargetPose / PickTask
                                                ▼
                                          ROS2 控制层（C）
                                                │ PickResult
                                                ▼
事件服务与数据库（D） ── SortEvent ──► Web 看板（D）

手势服务（A） ── GestureEvent ─┐
语音服务（A） ── VoiceCommand ─┼──► 任务编排与安全门禁
                              └──► 仅能触发受限、可审计动作
```

## 责任边界

| 模块 | 负责人 | 输入 | 输出 | 不承担的职责 |
|---|---|---|---|---|
| 视觉服务 | B | 摄像头帧 | `DetectionResult` | 不直接驱动舵机。 |
| 标定/任务编排 | B、C | 识别结果、标定参数 | `TargetPose`、`PickTask` | 不绕过控制层安全门禁。 |
| ROS2 控制层 | C | `PickTask` | `PickResult` | 不决定垃圾类别。 |
| 事件服务与数据库 | D | 任务/执行结果 | `SortEvent`、查询接口 | 不伪造执行记录。 |
| Web 看板 | D | OpenAPI HTTP 接口 | 可视化与人工安全操作 | 不直接写串口或舵机指令。 |
| 手势互动 | A | 摄像头帧 | `GestureEvent` | 仅触发预设安全动作。 |
| 语音控制 | A | 音频 | `VoiceCommand` | 低置信度时不得触发分拣。 |

## 必经安全状态机

```text
RECEIVED → VALIDATING → REJECTED
                       → EXECUTING → VERIFYING → SUCCEEDED
                                                   → RETRYING（最多一次）→ FAILED / SAFE_MODE
```

## 风险与降级

| 风险 | 触发 | 首选处理 | 兜底 |
|---|---|---|---|
| 识别不稳定 | 置信度 < 0.50 或连续 3 帧不一致 | 连续 5 帧投票、调曝光重试一次 | 颜色追踪辅助定位；类别仍不可靠则跳过、留截图和日志。 |
| 标定漂移 | 验证点误差 > 10 mm，或设备位置变化 | 停止自动抓取并重新标定 | 旧 `calibration_id` 作废；仅允许回零或停机。 |
| 抓取失败/堵转 | 状态异常或抓后视觉仍见物体 | 回安全位、降速、修正抓取点，最多重试一次 | 堵转 3 秒停臂；记录 `GRIP_FAILED` 并交人工。 |
| ROS2 通信中断 | 超时 2 s 或连续 3 次心跳丢失 | 取消任务、停机、自动重连一次 | 进入安全模式，保留历史事件和错误码。 |
| 手势误检 | 连续帧不一致或冷却期内重复 | 5 帧中至少 4 帧确认 | 10 秒冷却期只记录、不触发动作。 |

## 接口边界

- 视觉、标定、控制和事件服务之间以数据对象传递；字段见 [OpenAPI 契约](../../api/openapi.yaml)。
- Web 只能通过 HTTP API 与后端交互；Swagger UI 依据 `api/openapi.yaml` 展示。
- 因硬件、接口或安全门禁导致的状态变化必须写入事件，而不是只打印到终端。
