# E2 语音控制模块（成员 A 侧）

A 侧语音命令来源：**识别到关键词 → 输出 `VoiceCommand`（含 `voice_code`）→ C 自定义舵机动作**。
A 不直接控制舵机，所有动作须经 C 安全状态机校验。

## 功能

- 唯一命令：**“帮我分类” → `voice_code=1`，触发一次完整分拣**。
- 低置信识别（默认 < 0.5）不触发。
- 无关语音（未命中关键词）不触发，满足 E2 误触发率 ≤ 5% 验收。
- 同命令冷却（默认 3s），防止连续语音片段重复触发。

## 运行

```bash
# 真实麦克风（需 SpeechRecognition + PyAudio，且联网走 Google Web Speech）
python -m voice.app --mic

# 离线 / 测试：从文本文件逐行读取（格式 文本|置信度，置信度可选）
python -m voice.app --text-file utterances.txt

# 交互模式：标准输入逐行
python -m voice.app --interactive

# 调参
python -m voice.app --mic --min-confidence 0.6 --cooldown-s 5 --debug
```

输出为 `VoiceCommand` 的 JSON 行（stdout），字段与 `api/openapi.yaml` 的 `VoiceCommand` 对齐。

## 后端可插拔

| 后端 | 场景 | 依赖 |
|---|---|---|
| `MockTextBackend` | 离线测试 / 演示 | 无 |
| `MicBackend` | 真实麦克风 | `SpeechRecognition` + `PyAudio` |

`MicBackend` 使用 Google Web Speech（中文 `zh-CN`），需联网；如需离线可替换为 Vosk / Whisper 后端，仅需实现同一 `RecognizerBackend` 接口。

## 测试

```bash
cd src && python run_tests.py
```

覆盖：关键词匹配（含前后缀容忍）、无关语音零误触发、低置信拦截、冷却去重。

## 验收对照（需求基线 E2）

| 指标 | 设计保证 |
|---|---|
| 40 次有效指令启动比例 ≥ 90% | 关键词匹配稳定；真正机实测留证 |
| 响应 P95 ≤ 2s | 端到端在集成阶段实测 |
| 20 条无关语音误触发 ≤ 5% | 关键词白名单 + 低置信拦截（理论 0%） |
