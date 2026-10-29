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

    def iter_commands(self) -> Iterator[VoiceCommand]:
        """遍历后端结果，产出应下发的 VoiceCommand（无关语音被过滤）。"""
        for utt in self.backend:
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
