"""把 GestureCommand 交给 C 的传输层。A 不直连舵机，只产出命令。

目前提供 stdout（演示）与 file（jsonl，便于 C 读取/联调）两种实现。
真实部署可由 C 侧决定传输方式（ROS2 topic / socket / 共享内存等），
只要消费同样的 JSON schema 即可。
"""

from __future__ import annotations

import abc
from typing import Optional

from .gesture_command import GestureCommand


class CommandSink(abc.ABC):
    @abc.abstractmethod
    def emit(self, command: GestureCommand) -> None: ...


class StdoutSink(CommandSink):
    def emit(self, command: GestureCommand) -> None:
        print(command.to_json(), flush=True)


class FileSink(CommandSink):
    def __init__(self, path: str) -> None:
        self.path = path

    def emit(self, command: GestureCommand) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(command.to_json() + "\n")
