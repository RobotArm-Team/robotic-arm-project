# E1 手势识别模块（成员 A 侧）

本目录是「智能机械臂垃圾分拣与管理系统」中 **E1 手势互动** 的实现，由成员 A 负责。

## 职责边界（重要）

- **A 只识别手势并输出 `GestureCommand`（手势编号/标识），不调用 `Arm_Lib`、不直连舵机。**
- 真实舵机动作由 **C** 读取 `GestureCommand` 后，经安全校验（角度限位、workspace_ok、急停）执行。
- 这满足 `PROJECT_PLAN` 第 23 行「手势不得绕过安全边界直接控制舵机」的要求。

## 是否需要训练模型？

**不需要。** 采用 **MediaPipe 官方预训练 `GestureRecognizer`**（Google 训练好、
开箱即用，直接输出 Closed_Fist/Open_Palm/Pointing_Up/Victory/ILoveYou/Thumb_Up
等语义标签）：

```
摄像头帧 -> MediaPipe GestureRecognizer(官方模型) -> 类别映射 -> GestureCommand
```

- 官方模型覆盖 6 种手势；**捏合 PINCH(OK) 官方模型不含**，故在官方结果为
  None/低置信时用关键点几何补判（见 `landmarks.is_pinch`）。
- 识别结果再经**时序平滑（EMA）**抑制单帧抖动，并做**置信度门限**过滤，
  最终由 `command_gate` 做「连续 5 帧中至少 4 帧一致 + 10 秒冷却」确认后下发。
- 若后续需要 MediaPipe 覆盖不了的特殊手势，再考虑收集数据集训练自定义分类器
  （届时需单独评估，不属于当前基线）。

## 手势 -> 编号映射（C 侧查找表的主键）

| gesture_id  | gesture_code | 含义       |
|-------------|--------------|------------|
| FIST        | 1            | 握拳       |
| OPEN_PALM   | 2            | 张开手掌   |
| POINT_UP    | 3            | 食指向上   |
| PEACE       | 4            | 剪刀手     |
| ROCK        | 5            | 摇滚(食小) |
| PINCH       | 6            | 捏合(OK)   |
| THUMBS_UP   | 7            | 点赞       |

> 注意：原 `PROJECT_PLAN` 3.1 的 E1 命令集为「启动/暂停/复位/取消/急停」，
> 当前已改为「手势编号 + C 自定义舵机动作」语义。**该改动属于需求冻结内容的变更，
> 需走 OpenSpec 变更流程并经 B/C 确认**（见下方"待办"）。

## C 侧对接契约（JSON schema）

A 通过 `CommandSink` 输出如下 JSON（stdout 或 jsonl 文件），C 读取后映射为舵机动作：

```json
{
  "gesture_id": "FIST",
  "confidence": 0.91,
  "gesture_code": 1,
  "source": "gesture",
  "timestamp": "2026-10-23T15:11:00",
  "task_id": null
}
```

C 侧示例（伪代码）：

```python
GESTURE_TO_MOTION = {
    1: ("servo", 2, "up", 10),     # FIST -> 2 号舵机抬升 10°
    2: ("servo", 2, "down", 10),   # OPEN_PALM -> 2 号舵机下降 10°
    3: ("home",),                  # POINT_UP -> 回安全位
    7: ("estop",),                 # THUMBS_UP -> 急停（最高优先级）
    # ... 由 C 按安全边界定义
}
```

## 运行方式

```bash
cd src/gesture
pip install -r requirements.txt

# 摄像头实时识别（需本地有摄像头）
python -m gesture.app --camera 0 --sink stdout --display

# 用视频文件验证（无摄像头环境）
python -m gesture.app --video demo.mp4 --sink file --out commands.jsonl
```

### 可调参数（优化识别质量）

| 参数 | 默认 | 说明 |
|---|---|---|
| `--min-confidence` | 0.5 | 置信度门限（基于窗口**平均**，稳健）：平均低于此值的命令视为未确认，不下发（服务 E1 正确率≥90%）。可调高到 0.7 更稳、但可能漏识别。 |
| `--smooth-alpha` | 0.6 | EMA 平滑系数：越大越跟手、越小越平滑。手抖明显可调小（如 0.4）。 |
| `--calibrate` | off | 对下发给 C 的置信度做单调显示校准（`c -> c**0.6`），稳定手势显示更高、更直观；原始值仍写入 `recognition_log.csv` 的 `raw_confidence` 列，便于复核。 |
| `--debug` | off | 每帧打印手指伸展比例，用于校准判定。 |

约束（来自规格）：连续 5 帧中至少 4 帧一致才下发；同一命令触发后冷却 10 秒
（冷却期内只记录、不触发）。每次识别都会写入 `recognition_log.csv` 供验收统计。

### 置信度语义（可验证、不伪造）
- **门限判定**用确认窗口内的**平均**置信度（稳健，避免单帧抖动通过/被拒）。
- **下发时报告**窗口内的**峰值**置信度（稳定保持手势的最佳瞬间，更直观）。
- 模型原始置信度是 Google 官方 `gesture_recognizer.task` 的真实输出：
  `OPEN_PALM`/`POINT_UP` 等姿势该模型本身输出就偏低（约 0.5~0.7），属正常；
  握拳/捏合/点赞通常更高。提升**真实**置信度的根本办法是更好的取景与打光、稳定保持手势。
- 不要用"调高数字"替代"提升真实识别质量"——验收以 `recognition_log.csv` 原始值为准。

## 单元测试（无需摄像头 / MediaPipe）

```bash
python -m pytest tests -v
```

覆盖：手势几何分类与 PINCH 补判（`test_landmarks.py`）、连续帧确认与 10 秒冷却
及置信度门限（`test_gate.py`）、时序平滑（`test_smoother.py`）。

## 待办

- [ ] 走 OpenSpec 变更：将 E1 命令语义从「启动/暂停/复位/取消/急停」更新为
      「手势编号 + C 自定义舵机动作」，并与 B/C 对齐。
- [ ] 与 C 确认 `gesture_code -> 舵机动作` 的最终映射表。
- [ ] 在 Atlas 200I DK A2 上测真实延迟（目标 P95 <= 1s）。
- [ ] E1 验收测试：正确率 >= 90%、越界 0 次（见 `recognition_log.csv`）。
