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
# 真实麦克风（默认 vosk 离线中文，推荐；国内/展台无需外网）
python -m voice.app --mic --debug

# 指定 Vosk 模型路径（默认 src/voice/models/vosk-cn）
python -m voice.app --mic --vosk-model /path/to/vosk-cn

# 备选：Google Web Speech（需外网，国内不推荐）
python -m voice.app --mic --asr google

# 离线 / 测试：从文本文件逐行读取（格式 文本|置信度，置信度可选）
python -m voice.app --text-file utterances.txt

# 离线验证：从 WAV 音频识别（无需麦克风，结果可复现，适合回归/统计）
python -m voice.app --wav-file sample.wav --debug

# 交互模式：标准输入逐行
python -m voice.app --interactive

# 调参
python -m voice.app --mic --min-confidence 0.6 --cooldown-s 5 --debug
```

> 调试提示：麦克风模式会用 `[识别] '<文本>' 命中→下发 / 无关语音(不触发)` 实时打印
> 每一句的原始识别结果。若只看到“无关语音”说明**听清了但没命中关键词**（可调整说法）；
> 若长时间无任何 `[识别]` 输出，说明**没听清/环境噪声过大**（靠近麦克风、安静环境重试）。
> 短句或嘈杂环境下，程序最多每 4 秒（phrase_time_limit）强制输出一次识别，不会“石沉大海”。
```

输出为 `VoiceCommand` 的 JSON 行（stdout），字段与 `api/openapi.yaml` 的 `VoiceCommand` 对齐。

## Vosk 离线模型（国内推荐）

`--mic` 默认使用 **Vosk 离线中文识别**，全程不联网：

```bash
# 1) 安装依赖
pip install vosk PyAudio

# 2) 下载并解压中文模型到 src/voice/models/vosk-cn
python -m voice.tools.download_vosk_model
# 若脚本下载被墙，手动从 https://alphacephei.com/vosk/models
# 下载 vosk-model-small-cn-0.22.zip，解压后把内容放到 src/voice/models/vosk-cn
```

## 后端可插拔

| 后端 | 场景 | 依赖 | 联网 |
|---|---|---|---|
| `VoskBackend` | 真实麦克风（默认） | `vosk` + `PyAudio` + 本地模型 | 否 |
| `MicBackend` | 真实麦克风（备选） | `SpeechRecognition` + `PyAudio` | 是（Google） |
| `MockTextBackend` | 离线测试 / 演示 | 无 | 否 |

`VoskBackend` 默认启用（`--asr vosk`），识别不依赖任何外部服务，适合国内与展台环境；
如需切换回 Google，用 `--asr google`（需外网）。新增后端只需实现同一 `RecognizerBackend` 接口。

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
