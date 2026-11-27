"""机器人侧语音识别 HTTP 服务。

前端「语音识别」页通过 start/stop 控制机械臂 USB 麦克风，并用 /status 轮询
最近一句识别文本与命中的命令编号。识别本身由现有 ``voice.app`` 子进程完成，
本服务只负责进程生命周期、输出解析和 HTTP 接口。

运行（机械臂，ros-arm-env）：
  python -u -m voice.service --port 5020
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

VOICE_LABELS = {
    1: "帮我分类",
    2: "开始",
    3: "暂停",
    4: "复位",
    5: "取消",
    6: "急停",
}

# 与 voice.app 共用的静音标志：存在时只收音，不上屏、不下发。
MUTE_FLAG = Path(os.environ.get("VOICE_MUTE_FLAG", "/tmp/voice_muted"))

UTTERANCE_RE = re.compile(r"^(.*) 置信=([0-9.]+) (命中→下发|无关语音\(不触发\))$")
DEBUG_RE = re.compile(r"^text=(.*) conf=([0-9.]+) code=(\d+)$")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class VoiceService:
    """管理 voice.app 子进程，并把识别输出整理成前端需要的结构。"""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.voice_dir = Path(__file__).resolve().parent
        self.work_dir = Path(args.work_dir).resolve() if args.work_dir else self.voice_dir.parent
        default_model = self.voice_dir / "models" / "paraformer-large" / "model.int8.onnx"
        default_tokens = self.voice_dir / "models" / "paraformer-large" / "tokens.txt"
        self.model_path = Path(args.sherpa_model).resolve() if args.sherpa_model else default_model
        self.tokens_path = Path(args.sherpa_tokens).resolve() if args.sherpa_tokens else default_tokens

        self.lock = threading.Lock()
        self.proc: Optional[subprocess.Popen] = None
        self.reader: Optional[threading.Thread] = None
        self.state = "stopped"  # stopped / starting / listening / error
        self.error: Optional[str] = None
        self.mic: Optional[str] = None
        self.sequence = 0
        self.latest: Optional[dict[str, Any]] = None
        self.history: list[dict[str, Any]] = []
        self.log_tail: list[str] = []

    # ------------------------------------------------------------------ status
    def _snapshot(self) -> dict[str, Any]:
        running = self.proc is not None and self.proc.poll() is None
        return {
            "running": running,
            "state": self.state,
            "error": self.error,
            "mic": self.mic,
            "model": str(self.model_path),
            "muted": MUTE_FLAG.exists(),
            "pid": self.proc.pid if running and self.proc is not None else None,
            "latest": dict(self.latest) if self.latest else None,
            "history": [dict(item) for item in self.history[:10]],
            "log_tail": self.log_tail[-10:],
        }

    def status(self) -> dict[str, Any]:
        with self.lock:
            return self._snapshot()

    # ----------------------------------------------------------------- lifecycle
    def start(self) -> dict[str, Any]:
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                return {"status": "ALREADY_RUNNING", **self._snapshot()}
            self.state = "starting"
            self.error = None
            self.mic = None
            self.latest = None
            self.log_tail = []

        # 默认静音启动：前端按住「按住说话」时才解除静音，避免电视/旁人说话上屏。
        MUTE_FLAG.touch(exist_ok=True)
        # 释放可能被旧 notebook / 旧 CLI 占用的麦克风。
        subprocess.run(["pkill", "-f", "python.*voice.app"], capture_output=True)

        cmd = [
            sys.executable,
            "-u",
            "-m",
            "voice.app",
            "--mic",
            "--asr",
            "sherpa",
            "--sherpa-model",
            str(self.model_path),
            "--sherpa-tokens",
            str(self.tokens_path),
            "--mic-index",
            str(self.args.mic_index),
            "--vad-sensitivity",
            str(self.args.vad_sensitivity),
            "--debug",
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except OSError as exc:
            with self.lock:
                self.state = "error"
                self.error = str(exc)
            return {"status": "ERROR", "error": str(exc)}

        with self.lock:
            self.proc = proc
        self.reader = threading.Thread(target=self._read_output, args=(proc,), daemon=True)
        self.reader.start()
        return {"status": "STARTING", "pid": proc.pid}

    def stop(self) -> dict[str, Any]:
        with self.lock:
            proc = self.proc
            # 先标记为 stopped，避免读线程把 SIGTERM 误报成“进程退出错误”。
            self.state = "stopped"
            self.error = None
        MUTE_FLAG.touch(exist_ok=True)
        if proc is None or proc.poll() is not None:
            with self.lock:
                self.proc = None
            return {"status": "STOPPED"}
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        with self.lock:
            if self.proc is proc:
                self.proc = None
        return {"status": "STOPPED"}

    def mute(self) -> dict[str, Any]:
        MUTE_FLAG.touch(exist_ok=True)
        return {"status": "MUTED", "muted": True}

    def unmute(self) -> dict[str, Any]:
        try:
            MUTE_FLAG.unlink()
        except FileNotFoundError:
            pass
        return {"status": "UNMUTED", "muted": False}

    # --------------------------------------------------------------- output parse
    def _read_output(self, proc: subprocess.Popen) -> None:
        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    self._handle_line(line.rstrip("\n"))
        finally:
            rc = proc.wait()
            with self.lock:
                if self.proc is proc:
                    self.proc = None
                if self.state not in ("stopped", "error"):
                    if rc in (0, -15, 143):
                        self.state = "stopped"
                    else:
                        self.state = "error"
                        tail = [
                            line for line in reversed(self.log_tail)
                            if line.strip()
                            and not line.startswith("[识别]")
                            and not line.startswith("[dbg]")
                        ]
                        detail = tail[0][:300] if tail else f"exit code {rc}"
                        self.error = f"语音识别进程退出：{detail}"

    def _handle_line(self, line: str) -> None:
        if not line:
            return
        with self.lock:
            self.log_tail.append(line)
            del self.log_tail[:-20]

        if line.startswith("[E2] 使用麦克风："):
            with self.lock:
                self.mic = line.split("：", 1)[1].strip()
            return

        if "麦克风监听中" in line:
            with self.lock:
                self.state = "listening"
                self.error = None
            return

        if line.startswith("[E2]") and any(word in line for word in ("不可用", "未找到", "需要", "失败")):
            with self.lock:
                self.state = "error"
                self.error = line
            return

        if line.startswith("[识别] "):
            match = UTTERANCE_RE.match(line[len("[识别] "):])
            if not match:
                return
            text_literal, confidence_text, verdict = match.groups()
            text = self._literal(text_literal)
            matched = verdict == "命中→下发"
            with self.lock:
                self.sequence += 1
                entry = {
                    "text": text,
                    "confidence": float(confidence_text),
                    "voice_code": None,
                    "command": None,
                    "matched": matched,
                    "timestamp": _now(),
                    "sequence": self.sequence,
                    "raw": line,
                }
                self.latest = entry
                self.history.insert(0, entry)
                del self.history[10:]
            return

        if line.startswith("[dbg] "):
            match = DEBUG_RE.match(line[len("[dbg] "):])
            if not match:
                return
            text_literal, confidence_text, code_text = match.groups()
            text = self._literal(text_literal)
            code = int(code_text)
            with self.lock:
                entry = self.history[0] if self.history else None
                if entry is None:
                    self.sequence += 1
                    entry = {
                        "text": text,
                        "confidence": float(confidence_text),
                        "voice_code": None,
                        "command": None,
                        "matched": True,
                        "timestamp": _now(),
                        "sequence": self.sequence,
                        "raw": line,
                    }
                    self.history.insert(0, entry)
                entry.update({
                    "text": text,
                    "confidence": float(confidence_text),
                    "voice_code": code,
                    "command": VOICE_LABELS.get(code, f"code {code}"),
                    "matched": True,
                    "raw": line,
                })
                self.latest = entry
            return

        if line.startswith("{"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                return
            code = payload.get("voice_code")
            if not isinstance(code, int):
                return
            with self.lock:
                entry = self.history[0] if self.history else None
                if entry is None:
                    return
                entry["voice_code"] = code
                entry["command"] = VOICE_LABELS.get(code, f"code {code}")
                entry["matched"] = True
                entry["raw"] = line
                self.latest = entry

    @staticmethod
    def _literal(value: str) -> str:
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, str) else str(parsed)
        except (ValueError, SyntaxError):
            return value.strip("'\"")


SERVICE: Optional[VoiceService] = None


class Handler(BaseHTTPRequestHandler):
    server_version = "VoiceService/1.0"

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        assert SERVICE is not None
        if path in ("/", "/health"):
            self._send(200, {"status": "READY"})
        elif path == "/status":
            self._send(200, SERVICE.status())
        elif path == "/latest":
            self._send(200, SERVICE.status().get("latest") or {})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        assert SERVICE is not None
        if path == "/start":
            self._send(200, SERVICE.start())
        elif path == "/stop":
            self._send(200, SERVICE.stop())
        elif path == "/mute":
            self._send(200, SERVICE.mute())
        elif path == "/unmute":
            self._send(200, SERVICE.unmute())
        else:
            self._send(404, {"error": "not found"})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[voice-service] {self.address_string()} {fmt % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Robot-side voice recognition HTTP service")
    parser.add_argument("--port", type=int, default=5020)
    parser.add_argument("--mic-index", type=int, default=1)
    parser.add_argument("--vad-sensitivity", type=float, default=2.0)
    parser.add_argument("--sherpa-model", default=None)
    parser.add_argument("--sherpa-tokens", default=None)
    parser.add_argument("--work-dir", default=None)
    args = parser.parse_args()

    global SERVICE
    SERVICE = VoiceService(args)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)

    def _shutdown(signum: int, frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _shutdown)
    print(f"[voice-service] listening on 0.0.0.0:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        SERVICE.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
