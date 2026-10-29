"""E2 语音识别入口：麦克风/文本 -> 识别 -> 关键词匹配 -> 冷却 -> 输出 VoiceCommand。

用法：
  python -m voice.app --mic
  python -m voice.app --text-file utterances.txt
  python -m voice.app --interactive

说明：
- A 侧不依赖真实机械臂；只产出 VoiceCommand（语音命令编号）。
- C 读取 VoiceCommand 后，自行决定舵机运动序列并做安全校验。
- 无麦克风/离线环境用 --text-file 或 --interactive 验证；纯逻辑可用 tests/ 单元测试。
"""

from __future__ import annotations

import argparse
import sys
import time

# 兼容三种运行方式（PyCharm 右键 Run 走第 2 种）：
#   1) 作为模块：python -m voice.app
#   2) 直接运行文件：python app.py 或 PyCharm 右键 Run（__package__ 为空）
#   3) 被其它包导入
if __package__ in (None, ""):
    import os

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    from voice.command_gate import VoiceCommandGate
    from voice.recognizer import MicBackend, MockTextBackend, VoiceRecognizer
    from voice.voice_command import VoiceCommand
else:
    from .command_gate import VoiceCommandGate
    from .recognizer import MicBackend, MockTextBackend, VoiceRecognizer
    from .voice_command import VoiceCommand


def _read_text_file(path: str):
    """读取 文本|置信度 逐行文件；置信度可选，默认 1.0。"""
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                text, conf = line.rsplit("|", 1)
                out.append((text.strip(), float(conf.strip())))
            else:
                out.append((line, 1.0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="E2 语音控制（成员 A 侧）")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--mic", action="store_true", help="使用麦克风（需 speech_recognition）")
    src.add_argument("--text-file", type=str, default=None,
                     help="从文本文件逐行读取（格式：文本|置信度，置信度可选）")
    src.add_argument("--interactive", action="store_true", help="从标准输入逐行读取")
    ap.add_argument("--min-confidence", type=float, default=0.5,
                    help="置信度门限：低于此值不触发（默认 0.5）")
    ap.add_argument("--cooldown-s", type=float, default=3.0, help="同命令冷却秒数（默认 3.0）")
    ap.add_argument("--debug", action="store_true", help="打印每次识别原始文本与置信度")
    args = ap.parse_args()

    if args.mic:
        try:
            backend = MicBackend(min_confidence=args.min_confidence)
        except ImportError as e:
            print(f"[E2] {e}", file=sys.stderr)
            return 1
    elif args.text_file:
        backend = MockTextBackend(
            _read_text_file(args.text_file), min_confidence=args.min_confidence
        )
    else:
        print("[E2] 交互模式：每行输入一句，Ctrl+C 退出", file=sys.stderr)

        def _stdin_iter():
            for line in sys.stdin:
                line = line.strip()
                if line:
                    yield (line, 1.0)

        backend = MockTextBackend(_stdin_iter(), min_confidence=args.min_confidence)

    recognizer = VoiceRecognizer(backend, min_confidence=args.min_confidence)
    gate = VoiceCommandGate(cooldown_s=args.cooldown_s, min_confidence=args.min_confidence)

    print("[E2] 语音控制启动，输出 VoiceCommand（Ctrl+C 退出）", file=sys.stderr)
    try:
        for cmd in recognizer.iter_commands():
            if args.debug:
                print(
                    f"[dbg] text={cmd.text!r} conf={cmd.confidence} code={cmd.voice_code}",
                    file=sys.stderr,
                )
            now = time.time()
            emitted = gate.update(cmd, now)
            if emitted is not None:
                print(emitted.to_json())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
