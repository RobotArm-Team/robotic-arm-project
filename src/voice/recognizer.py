"""语音识别封装：A 侧 E2 命令来源，不控制舵机。

设计：
- 后端可插拔：MicBackend（真实麦克风，需 speech_recognition）与 MockTextBackend（离线/测试）。
- 默认「自由解码 + 关键词过滤」：Vosk 自由解码能听清任意话语，仅当文本命中白名单
  命令关键词且置信度达标，才产出 VoiceCommand 并下发；其它话语（闲聊/噪声）只显示、
  不触发，满足 E2 误触发率 ≤5% 验收。
- 可选「受限 grammar 严格模式」（--grammar）：把解码锁死到已知命令短语，用于嘈杂展台
  等极端环境，进一步压噪声；日常默认自由解码即可。

依赖：
- 可选：speech_recognition（仅 MicBackend 需要；离线环境可缺失，自动降级到 MockTextBackend）。
"""

from __future__ import annotations

import json
import os
import struct
import sys
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Tuple

from .voice_command import VOICE_CODES, VoiceCommand

# 关键词 -> 命令名（再经 VOICE_CODES 映射为整数编号）。
# 关键词做包含匹配（容忍“请帮我分类一下”“开始分拣吧”等前后缀）。
# 系统能识别任意话语，但只有命中这里的关键词才会下发命令。
COMMAND_KEYWORDS: dict[str, str] = {
    "帮我分类": "SORT_ONE",  # -> voice_code 1
    "开始": "START",         # -> 2（也覆盖“开始分拣”等）
    "暂停": "PAUSE",         # -> 3
    "复位": "RESET",         # -> 4
    "取消": "CANCEL",        # -> 5
    "急停": "ESTOP",         # -> 6（与手势急停对齐，最高优先级）
}

# 受限语法（grammar，--grammar 严格模式用）：把 Vosk 解码限制到已知命令短语，
# 从根本上消除小模型把噪声/底噪幻觉成中文碎片的问题。
# 注意：vosk-model-small-cn 按“字”建词表，整词短语会被判为
# “missing in vocabulary”而失效，必须以空格分词（"帮 我 分 类"）。
# 必须与上方 COMMAND_KEYWORDS 同步扩充；新增命令时同步在此登记。
DEFAULT_GRAMMAR: List[str] = [
    "帮 我 分 类",                  # 帮我分类
    "开 始", "开 始 分 拣",         # 开始 / 开始分拣
    "暂 停",                        # 暂停
    "复 位",                        # 复位
    "取 消",                        # 取消
    "急 停",                        # 急停
]


def _normalize(text: str) -> str:
    """归一化：去全/半角空格，转小写（中文无大小写，保留以防英文混用）。"""
    return text.replace(" ", "").replace("　", "").lower()


@dataclass
class Utterance:
    text: str
    confidence: float


class RecognizerBackend:
    """后端接口：逐条产出识别结果。"""

    def __init__(self, min_confidence: float = 0.5) -> None:
        self.min_confidence = min_confidence

    def __iter__(self) -> Iterator[Utterance]:
        raise NotImplementedError


class MockTextBackend(RecognizerBackend):
    """离线/测试后端：从预设或可迭代文本产出识别结果，无需麦克风或外网。

    items 为可迭代的 (text, confidence) 元组；支持列表或按需生成的迭代器（如 stdin）。
    """

    def __init__(
        self,
        items: Iterable[Tuple[str, float]],
        min_confidence: float = 0.5,
    ) -> None:
        super().__init__(min_confidence)
        self._items = items

    def __iter__(self) -> Iterator[Utterance]:
        for text, conf in self._items:
            yield Utterance(text=text, confidence=conf)


class MicBackend(RecognizerBackend):
    """真实麦克风后端：依赖 speech_recognition（可选安装）。

    未安装时 __iter__ 会抛出 ImportError，由上层捕获并提示降级。
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        language: str = "zh-CN",
        phrase_time_limit: float = 4.0,
    ) -> None:
        super().__init__(min_confidence)
        self.language = language
        self.phrase_time_limit = phrase_time_limit

    def validate(self) -> None:
        """提前校验依赖是否存在（缺失即抛错，避免迭代时才崩栈）。"""
        try:
            import speech_recognition  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "MicBackend 需要 speech_recognition（且麦克风需 PyAudio）："
                "pip install SpeechRecognition PyAudio；国内建议改用 --asr vosk。"
            ) from e

    def __iter__(self) -> Iterator[Utterance]:
        try:
            import speech_recognition as sr
        except ImportError as e:
            raise ImportError(
                "MicBackend 需要 speech_recognition：pip install SpeechRecognition "
                "（麦克风还需 PyAudio）。当前环境缺失，已降级到 MockTextBackend。"
            ) from e
        r = sr.Recognizer()
        with sr.Microphone() as src:
            r.adjust_for_ambient_noise(src)
            while True:
                try:
                    audio = r.listen(src, phrase_time_limit=self.phrase_time_limit)
                    text = r.recognize_google(audio, language=self.language)
                    # Google Web Speech 不返回置信度，给默认 1.0（接本地模型可取真值）
                    yield Utterance(text=text, confidence=1.0)
                except sr.UnknownValueError:
                    yield Utterance(text="", confidence=0.0)
                except sr.RequestError:
                    # 网络/服务异常：视为无有效识别
                    yield Utterance(text="", confidence=0.0)


class VoskBackend(RecognizerBackend):
    """离线中文识别后端：基于 Vosk + 本地模型，全程不联网（适合国内/展台环境）。

    默认自由解码（grammar=None）：能听清任意话语，由上层关键词匹配决定哪些
    触发命令；仅 --grammar 才进入受限严格模式。配合内置能量 VAD，可把噪声/静音
    挡在命令之外（详见 _iter_mic）。

    依赖（可选安装，未装时自动退回 Google/文本后端）：
      pip install vosk PyAudio
    并需下载中文模型（约 40MB），解压到 models/vosk-cn（见 docs 与 download 脚本）：
      https://alphacephei.com/vosk/models  ->  vosk-model-small-cn-0.22（约 44MB）
      （无 0.15 版本；也可用更新的 vosk-model-small-cn-0.3，约 33MB）
    """

    DEFAULT_MODEL_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "models", "vosk-cn"
    )

    def __init__(
        self,
        model_path: Optional[str] = None,
        min_confidence: float = 0.5,
        sample_rate: int = 16000,
        phrase_time_limit: float = 4.0,
        wav_path: Optional[str] = None,
        grammar: Optional[List[str]] = None,
        mic_index: Optional[int] = None,
        vad_sensitivity: float = 2.0,
        prefer_usb: bool = True,
    ) -> None:
        super().__init__(min_confidence)
        self.model_path = model_path or self.DEFAULT_MODEL_DIR
        self.sample_rate = sample_rate
        self.phrase_time_limit = phrase_time_limit
        # wav_path 非空 = 从音频文件识别（离线验证/回归用，无需麦克风）
        self.wav_path = wav_path
        # grammar 默认 None = 自由解码（能识别任意话语，仅命令关键词触发）；
        # 传 DEFAULT_GRAMMAR 则进入受限严格模式（--grammar，用于嘈杂展台）。
        self.grammar = grammar
        # 麦克风选择：None=自动（优先 USB 声卡，见 _pick_input_device）；
        # 显式 index 用 --mic-index 指定，避免默认设备选到 DK 板载 MIC。
        self.mic_index = mic_index
        # VAD 灵敏度倍数：自由解码下取更保守的值，避免底噪被幻觉成中文碎片。
        # 门限 = max(噪声底 × vad_sensitivity, 绝对下限)，越大越不易误触发。
        self.vad_sensitivity = vad_sensitivity
        self.prefer_usb = prefer_usb
        self._Model = None
        self._KaldiRecognizer = None
        self._pyaudio = None

    def _load(self) -> None:
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
            import pyaudio
        except ImportError as e:
            raise ImportError(
                "VoskBackend 需要 vosk 与 PyAudio：pip install vosk PyAudio；"
                "并把中文模型放到 models/vosk-cn（或 --vosk-model 指定）。"
            ) from e
        # Kaldi 默认会把大量加载日志打到 stderr，淹没识别结果；静音只保留我们的输出。
        try:
            SetLogLevel(-1)
        except Exception:  # 老版本 vosk 无此接口，忽略
            pass
        if not os.path.isdir(self.model_path):
            raise FileNotFoundError(
                f"未找到 Vosk 中文模型目录：{self.model_path}\n"
                "请下载 vosk-model-small-cn-0.22 并解压到该路径，"
                "或运行 tools/download_vosk_model.py，或用 --vosk-model 指定。"
            )
        self._Model = Model
        self._KaldiRecognizer = KaldiRecognizer
        self._pyaudio = pyaudio

    def _extract(self, raw_json: str) -> Tuple[str, float]:
        """解析 Vosk 结果 JSON：返回 (文本, 平均词置信度)。

        文本为空（静音/未匹配 grammar）返回 ('', 0.0)，调用方据此跳过，
        从而把噪声/无关语音挡在命令之外；同时用真实 token 置信度替代写死的 1.0。
        """
        try:
            obj = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            return "", 0.0
        text = (obj.get("text") or "").strip()
        if not text:
            return "", 0.0
        # Vosk 中文以空格分词（"帮 我 分 类"）；命令领域直接拼接回成词更直观。
        text = text.replace(" ", "")
        parts = obj.get("result") or []
        if parts:
            conf = sum(float(p.get("conf", 1.0)) for p in parts) / len(parts)
        else:
            conf = 1.0
        return text, float(conf)

    def _make_recognizer(self, model):
        """构造 KaldiRecognizer；启用了 grammar 则把解码限制到已知命令短语。"""
        if self.grammar:
            return self._KaldiRecognizer(
                model, self.sample_rate,
                json.dumps(self.grammar, ensure_ascii=False),
            )
        return self._KaldiRecognizer(model, self.sample_rate)

    @staticmethod
    def _frame_rms(data: bytes) -> float:
        """计算 16bit 单声道 PCM 块的 RMS 能量（用于轻量 VAD）。"""
        if not data:
            return 0.0
        count = len(data) // 2
        if count == 0:
            return 0.0
        shorts = struct.unpack(f"<{count}h", data)
        return (sum(s * s for s in shorts) / count) ** 0.5

    @staticmethod
    def list_input_devices(p) -> List[dict]:
        """列出所有可录音设备（供 --list-mics 与自动选择使用）。

        每项：index / name / max_input_channels / default_sample_rate。
        硬件依据（机械臂使用手册 §2.5）：系统里有两类麦克风源——
        Atlas DK 板载 MIC 与 USB 转音频模块的板载麦，默认设备未必是后者。
        """
        devices = []
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
            except Exception:
                continue
            if int(info.get("maxInputChannels", 0)) > 0:
                devices.append({
                    "index": i,
                    "name": info.get("name", ""),
                    "channels": int(info.get("maxInputChannels", 0)),
                    "sample_rate": int(info.get("defaultSampleRate", 0)),
                })
        return devices

    @staticmethod
    def pick_input_index(devices: List[dict], default_index: Optional[int] = None,
                         prefer_usb: bool = True) -> int:
        """选择录音设备索引（纯逻辑，可单测）。

        规则：
        - 显式指定（mic_index）由调用方直接用，不进本函数；
        - prefer_usb=True 时优先选名字里含 usb / audio / waveshare / 声卡 的设备
          （USB 转音频模块），避开 DK 板载 MIC；
        - 否则用 PyAudio 报的默认输入设备；
        - 都没有则退回第一个可录音设备；无设备返回 -1。
        """
        if not devices:
            return -1
        usb_keys = ("usb", "waveshare", "声卡", "音频", "usbaudio", "usb to audio")
        # 明显是虚拟/远程音频的设备跳过（Cast/ToDesk/虚拟/Steam 等），它们录不到真实麦克风
        virtual_keys = ("cast audio", "todesk", "virtual", "虚拟", "steam", "映射器")
        if prefer_usb:
            for d in devices:
                low = d["name"].lower()
                if any(v in low for v in virtual_keys):
                    continue
                if any(k in low for k in usb_keys):
                    return d["index"]
        if default_index is not None and any(d["index"] == default_index for d in devices):
            return default_index
        return devices[0]["index"]

    def _open_input_stream(self, p):
        """按设备实际能力打开输入流，返回 (stream, actual_rate)。

        USB 转音频模块支持 8K/16K/48K 等多采样率、立体声编码（手册 §2.5）。
        这里先尝试项目要求的 sample_rate（16k，Vosk 需要），若设备不支持则
        回退到设备默认采样率并告知上层——上层据此对音频做重采样到 16k。
        声道固定按单声道打开（Vosk 要求），设备若只给立体声由后续转换处理。
        """
        devices = self.list_input_devices(p)
        try:
            default_idx = p.get_default_input_device_info()["index"]
        except Exception:
            default_idx = None
        idx = (self.mic_index if self.mic_index is not None
               else self.pick_input_index(devices, default_idx, self.prefer_usb))
        if idx < 0:
            raise RuntimeError("未找到任何可录音设备；请检查 USB 转音频模块是否插好（手册 §2.5）")

        chosen = next((d for d in devices if d["index"] == idx), None)
        name = chosen["name"] if chosen else f"index={idx}"
        print(f"[E2] 使用麦克风：index={idx} {name}", file=sys.stderr)

        # 先按目标采样率（16k）打开；设备不支持时回退到其默认采样率。
        for rate in dict.fromkeys([self.sample_rate,
                                   chosen["sample_rate"] if chosen else self.sample_rate]):
            if not rate:
                continue
            try:
                stream = p.open(
                    format=self._pyaudio.paInt16, channels=1, rate=rate,
                    input=True, input_device_index=idx,
                    frames_per_buffer=4000,
                )
                return stream, rate, name
            except Exception:
                continue
        raise RuntimeError(
            f"麦克风 {name} 无法以 16k 或默认采样率打开；"
            "可在手册支持列表（8K/11.025K/12K/16K/22.05K/24K/44.1K/48K）内调整 --sample-rate"
        )

    def _iter_stream(self, data_iter: Iterable[bytes]) -> Iterator[Utterance]:
        """通用流式识别：data_iter 产出 16k/单声道/16bit 音频块（或 None 切句哨兵）。

        混合三种切句策略，确保任何情况下都能周期性输出识别结果：
        1) Vosk 句末检测（AcceptWaveform 返回 True）-> 立即取完整句 Result；
        2) 超时（约 phrase_time_limit 秒）强制 FinalResult，避免短句漏识别；
        3) data_iter 产出 None 哨兵 -> 立即 FinalResult 切句（由 VAD 在静音间隙发出）。

        仅当文本非空（命中 grammar 且确为语音，conf 由 Vosk 真实给出）才产出；
        噪声/静音/无关语音被自动过滤，不再污染命令流。
        """
        model = self._Model(self.model_path)
        rec = self._make_recognizer(model)
        # 每块 4000 帧 ≈ 0.25s（16k）；据此换算一个短语的块数。
        blocks_per_phrase = max(
            1, int(self.phrase_time_limit * self.sample_rate * 2 / 4000)
        )
        n = 0
        for data in data_iter:
            if data is None:  # VAD 静音切句哨兵
                text, conf = self._extract(rec.FinalResult())
                if text:
                    yield Utterance(text=text, confidence=conf)
                rec = self._make_recognizer(model)
                n = 0
                continue
            if not data:
                continue
            is_end = rec.AcceptWaveform(data)
            n += 1
            if is_end:
                # Vosk 判定一句话结束：立即出完整句
                text, conf = self._extract(rec.Result())
                if text:
                    yield Utterance(text=text, confidence=conf)
                rec = self._make_recognizer(model)
                n = 0
            elif n >= blocks_per_phrase:
                # 超时强制切句：Vosk 未判定句末时也输出这一段累积识别。
                text, conf = self._extract(rec.FinalResult())
                if text:
                    yield Utterance(text=text, confidence=conf)
                rec = self._make_recognizer(model)
                n = 0
        # 流结束（如 WAV 文件耗尽）：取最后一段剩余识别。
        # 短句/无句末静音时整段都累积在此，必须 FinalResult 才能取出。
        text, conf = self._extract(rec.FinalResult())
        if text:
            yield Utterance(text=text, confidence=conf)

    def _iter_wav(self) -> Iterator[Utterance]:
        """从 WAV 文件识别：自动转单声道/16bit/16kHz，无需麦克风即可端到端验证。"""
        import wave

        try:
            import audioop  # Python 3.12 及以下自带；3.13 已移除
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "WAV 识别需要 audioop（Python ≤3.12 自带）。"
                "Python 3.13+ 请改用麦克风模式或自行安装 audioop 兼容包。"
            ) from e

        if not os.path.isfile(self.wav_path):
            raise FileNotFoundError(f"未找到音频文件：{self.wav_path}")

        wf = wave.open(self.wav_path, "rb")
        rate, channels, sampwidth = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()

        def _wav_chunks() -> Iterator[bytes]:
            while True:
                raw = wf.readframes(4000)
                if not raw:
                    break
                if channels != 1:  # 多声道 -> 单声道
                    raw = audioop.tomono(raw, sampwidth, 0.5, 0.5)
                if sampwidth != 2:  # 8/24/32bit -> 16bit
                    raw = audioop.lin2lin(raw, sampwidth, 2)
                if rate != self.sample_rate:  # 采样率 -> 16kHz
                    raw, _ = audioop.ratecv(raw, 2, 1, rate, self.sample_rate, None)
                yield raw

        try:
            yield from self._iter_stream(_wav_chunks())
        finally:
            wf.close()

    @staticmethod
    def calibrate_vad_threshold(ambient_rms: List[float], sensitivity: float,
                                has_grammar: bool = False) -> float:
        """由环境噪声样本算 VAD 门限（纯逻辑，可单测）。

        - 用中位数而非最大值估计噪声底：偶发的一次 cough/碰麦不会抬高门限。
        - 自由解码（无 grammar）时底噪也可能被 Vosk 幻觉成中文，门限取更保守值；
          有 grammar 兜底时解码器只认命令短语，可放宽以提升召回。
        - 设绝对下限，避免安静环境门限过低把电子底噪当语音。
        """
        if not ambient_rms:
            base = 0.0
        else:
            ordered = sorted(ambient_rms)
            mid = len(ordered) // 2
            base = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
        mult = max(1.0, sensitivity) * (0.7 if has_grammar else 1.0)
        return max(base * mult, 200.0)

    def _iter_mic(self) -> Iterator[Utterance]:
        """从麦克风流式识别。

        硬件依据（机械臂使用手册 §2.5）：USB 转音频模块支持多采样率与立体声，
        Atlas DK 另有板载 MIC。本实现：
        - 优先选 USB 声卡的麦（--mic-index 可覆盖），避开板载 MIC；
        - 按设备能力开流，必要时重采样到 16k（Vosk 要求）；
        - 稳健 VAD：中位数噪声底 × 灵敏度门限，自由解码下更保守，
          把底噪/空调/翻书声挡在 Vosk 之外，减少中文幻觉碎片。
        """
        p = self._pyaudio.PyAudio()
        stream, actual_rate, mic_name = self._open_input_stream(p)
        stream.start_stream()

        need_resample = actual_rate != self.sample_rate
        if need_resample:
            try:
                import audioop
            except ImportError as e:  # pragma: no cover - Python 3.13+
                stream.stop_stream(); stream.close(); p.terminate()
                raise ImportError(
                    "设备采样率非 16k，重采样需要 audioop（Python ≤3.12 自带）；"
                    "请换支持 16k 的 USB 声卡，或用 Python 3.11。"
                ) from e
            print(f"[E2] 设备采样 {actual_rate}Hz，重采样到 {self.sample_rate}Hz（Vosk 要求）",
                  file=sys.stderr)

        # 校准环境噪声底：采 ~0.7s，用中位数估计，避免单次碰麦抬高门限。
        block_ms = 4000.0 / actual_rate * 1000
        noise_blocks = max(2, int(700 / block_ms))
        ambient = [stream.read(4000, exception_on_overflow=False) for _ in range(noise_blocks)]
        noise_rms = [self._frame_rms(b) for b in ambient]
        threshold = self.calibrate_vad_threshold(
            noise_rms, self.vad_sensitivity, has_grammar=bool(self.grammar)
        )
        print(f"[E2] 噪声底={max(noise_rms):.0f} VAD门限={threshold:.0f}"
              f"（灵敏度={self.vad_sensitivity}{'，grammar模式' if self.grammar else ''}）",
              file=sys.stderr)
        silence_limit = max(1, int(0.5 * actual_rate / 4000))  # 0.5s 静音判定句尾

        def _to_vosk(data: bytes) -> bytes:
            if not need_resample:
                return data
            return audioop.ratecv(data, 2, 1, actual_rate, self.sample_rate, None)[0]

        def _vad_chunks() -> Iterator[Optional[bytes]]:
            speaking = False
            silent = 0
            while True:
                data = stream.read(4000, exception_on_overflow=False)
                if self._frame_rms(data) >= threshold:
                    speaking = True
                    silent = 0
                    yield _to_vosk(data)
                elif speaking:
                    # 句尾拖尾静音也喂给 Vosk 帮助断句，积累到间隙则切句
                    silent += 1
                    yield _to_vosk(data)
                    if silent >= silence_limit:
                        yield None  # 触发切句
                        speaking = False
                # 否则纯静音：不喂给 Vosk

        try:
            yield from self._iter_stream(_vad_chunks())
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def validate(self) -> None:
        """提前校验依赖与模型是否存在（缺失即抛错，避免迭代时才崩栈）。"""
        self._load()

    def __iter__(self) -> Iterator[Utterance]:
        self._load()
        if self.wav_path:
            yield from self._iter_wav()
            return
        yield from self._iter_mic()


class VoiceRecognizer:
    """关键词匹配 + 命令封装。

    逐条消费后端识别结果；仅当命中白名单关键词且置信度达标才返回 VoiceCommand。
    """

    def __init__(self, backend: RecognizerBackend, min_confidence: float = 0.5) -> None:
        self.backend = backend
        self.min_confidence = min_confidence

    @staticmethod
    def match_command(text: str) -> Optional[str]:
        """返回命中的命令名；未命中返回 None。纯函数，便于单元测试。"""
        norm = _normalize(text)
        for kw, cmd in COMMAND_KEYWORDS.items():
            if _normalize(kw) in norm:
                return cmd
        return None

    def iter_commands(self, on_utterance=None) -> Iterator[VoiceCommand]:
        """遍历后端结果，产出应下发的 VoiceCommand（无关语音被过滤）。

        on_utterance: 可选回调，每识别到一句原始文本即调用（便于 debug
        区分“没听清”与“听清但未命中关键词”）。
        """
        for utt in self.backend:
            if on_utterance is not None:
                on_utterance(utt)
            if utt.confidence < self.min_confidence:
                continue
            cmd_name = self.match_command(utt.text)
            if cmd_name is None:
                continue
            code = VOICE_CODES.get(cmd_name, 0)
            if code == 0:
                continue
            # latency_ms 留 0.0：端到端识别耗时由集成层/控制层实测，
            # 离线模块无法代表真实延迟（避免粉饰指标）。
            yield VoiceCommand(
                text=utt.text,
                confidence=round(utt.confidence, 3),
                voice_code=code,
            )
