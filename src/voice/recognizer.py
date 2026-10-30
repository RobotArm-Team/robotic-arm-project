"""语音识别封装：A 侧 E2 命令来源，不控制舵机。

设计：
- 后端可插拔：MicBackend（真实麦克风，需 speech_recognition）与 MockTextBackend（离线/测试）。
- 关键词匹配：仅当识别文本命中白名单关键词且置信度达标，才产出 VoiceCommand。
  当前唯一命令：“帮我分类” -> SORT_ONE (voice_code=1)，触发一次完整分拣。
- 低置信或不命中的文本视为“无关语音”，返回 None（不触发），满足 E2 误触发率 ≤5% 验收。

依赖：
- 可选：speech_recognition（仅 MicBackend 需要；离线环境可缺失，自动降级到 MockTextBackend）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Tuple

from .voice_command import VOICE_CODES, VoiceCommand

# 关键词 -> 命令名（再经 VOICE_CODES 映射为整数编号）。
# 关键词做包含匹配（容忍“请帮我分类一下”等前后缀）。
COMMAND_KEYWORDS: dict[str, str] = {
    "帮我分类": "SORT_ONE",
}


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
    ) -> None:
        super().__init__(min_confidence)
        self.model_path = model_path or self.DEFAULT_MODEL_DIR
        self.sample_rate = sample_rate
        self.phrase_time_limit = phrase_time_limit
        # wav_path 非空 = 从音频文件识别（离线验证/回归用，无需麦克风）
        self.wav_path = wav_path
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

    def _iter_stream(self, data_iter: Iterable[bytes]) -> Iterator[Utterance]:
        """通用流式识别：data_iter 产出 16k/单声道/16bit 音频块。

        混合两种切句策略，确保任何情况下都能周期性输出识别结果：
        1) Vosk 句末检测（AcceptWaveform 返回 True）-> 立即取完整句 Result；
        2) 否则每 phrase_time_limit 秒（约 blocks_per_phrase 块）强制取一次
           FinalResult，避免短句/嘈杂环境因无句末静音而漏识别（此前麦克风
           模式只依赖句末检测，导致“说了话却永远没输出”）。
        """
        model = self._Model(self.model_path)
        rec = self._KaldiRecognizer(model, self.sample_rate)
        # 每块 4000 字节 ≈ 125ms（16k * 2Bytes）；据此换算一个短语的块数。
        blocks_per_phrase = max(
            1, int(self.phrase_time_limit * self.sample_rate * 2 / 4000)
        )
        n = 0
        for data in data_iter:
            if not data:
                continue
            is_end = rec.AcceptWaveform(data)
            n += 1
            if is_end:
                # Vosk 判定一句话结束：立即出完整句
                text = json.loads(rec.Result()).get("text", "").strip()
                if text:
                    yield Utterance(text=text, confidence=1.0)
                rec = self._KaldiRecognizer(model, self.sample_rate)
                n = 0
            elif n >= blocks_per_phrase:
                # 超时强制切句：Vosk 未判定句末时也输出这一段累积识别。
                text = json.loads(rec.FinalResult()).get("text", "").strip()
                if text:
                    yield Utterance(text=text, confidence=1.0)
                rec = self._KaldiRecognizer(model, self.sample_rate)
                n = 0
        # 流结束（如 WAV 文件耗尽）：取最后一段剩余识别。
        # 短句/无句末静音时整段都累积在此，必须 FinalResult 才能取出。
        text = json.loads(rec.FinalResult()).get("text", "").strip()
        if text:
            yield Utterance(text=text, confidence=1.0)

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

    def _iter_mic(self) -> Iterator[Utterance]:
        """从麦克风流式识别（PyAudio 提供 16k/单声道/16bit 音频块）。"""
        p = self._pyaudio.PyAudio()
        stream = p.open(
            format=self._pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=8000,
        )
        stream.start_stream()

        def _mic_chunks() -> Iterator[bytes]:
            while True:
                yield stream.read(4000, exception_on_overflow=False)

        try:
            yield from self._iter_stream(_mic_chunks())
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
