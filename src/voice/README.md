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

## 硬件适配（依据机械臂使用手册 §2.5 / §2.1）

手册确认：机械臂搭载 **USB 转音频模块（USB TO AUDIO）** 并明确"支持语音识别"，
该模块支持 8K/11.025K/12K/**16K**/22.05K/24K/44.1K/48K 采样率、立体声编码、USB 2.0 免驱；
Atlas 200I DK A2 另有**板载 MIC ×1**。即系统里有**两个麦克风源**，系统默认设备未必是 USB 声卡麦，
选错麦（选到离得远的板载 MIC）是识别不准的常见原因。

为此语音模块做了以下适配：

- **设备可选 + 自动优先 USB 声卡**：`VoskBackend` 会枚举输入设备，默认优先名字含
  `usb / waveshare / 声卡 / 音频` 的设备，跳过 Cast/ToDesk 等虚拟音频；也可显式指定。
- **采样率自动适配**：先按 16K（Vosk 要求）打开，设备不支持时回退到设备默认率并
  **重采样到 16K**（多数 PC 声卡默认 44.1K/48K，旧版直接按 16K 打开会失败）。
- **稳健 VAD**：用环境噪声的中位数估计噪声底（抗单次碰麦离群），门限 =
  `噪声底 × vad_sensitivity`（默认 2.0）；自由解码模式门限更保守，避免底噪被幻觉成中文碎片；
  `--grammar` 严格模式有解码约束兜底，门限自动放宽以提升召回。

### 真机上怎么选对麦克风

```bash
# 1) 先列出所有可录音设备，找到 USB 声卡对应的 index
python -m voice.app --list-mics

# 2) 用该 index 运行（把 <N> 换成上一步的 USB 声卡 index）
python -m voice.app --mic --mic-index <N> --debug

# 嘈杂展台：提高 VAD 灵敏度倍数，拦住空调/人声底噪
python -m voice.app --mic --mic-index <N> --vad-sensitivity 3.0

# 极端噪声环境：再加 grammar 严格模式（只认命令短语）
python -m voice.app --mic --mic-index <N> --grammar
```

启动时会打印实际选用的麦克风、采样率与 VAD 门限，便于确认是否选对设备。

### 新增命令行参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--list-mics` | 关 | 列出所有可录音设备（index / 名称 / 声道 / 采样率）后退出 |
| `--mic-index <N>` | 自动 | 指定麦克风 index（真机上用它锁定 USB 声卡麦） |
| `--sample-rate <Hz>` | 16000 | 录音采样率；手册模块支持 8K~48K，非 16K 会自动重采样 |
| `--vad-sensitivity <float>` | 2.0 | VAD 门限倍数；越大越不易误触发，轻声识别困难可调低 |

### 单测

新增 6 项硬件适配单测（设备筛选逻辑、USB 优先、虚拟设备排除、VAD 中位数与绝对下限、
grammar 门限放宽），总计 **45 项全过**。这些逻辑均为纯函数，无需真机即可验证。
