"""E1 手势识别入口：摄像头/视频 -> 识别 -> 确认/冷却 -> 输出给 C。

用法：
  python -m gesture.app --camera 0 --sink stdout --display
  python -m gesture.app --video demo.mp4 --sink file --out commands.jsonl

说明：
- A 侧不依赖真实机械臂；只产出 GestureCommand（手势编号/标识）。
- C 读取 GestureCommand 后，自行决定舵机运动序列并做安全校验。
- 无摄像头环境可用 --video 读取视频文件验证；纯逻辑可用 tests/ 单元测试。
"""

from __future__ import annotations

import argparse
import sys
import time

import cv2

# 兼容三种运行方式（PyCharm 右键 Run 走的是第 2 种）：
#   1) 作为模块：python -m gesture.app
#   2) 直接运行文件：python app.py 或 PyCharm 右键 Run（__package__ 为空）
#   3) 被其它包导入
if __package__ in (None, ""):
    # 直接以脚本方式运行：把 src 加入搜索路径，按包名导入，保证子模块相对导入可用
    import os

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    from gesture.command_gate import CommandGate
    from gesture.logger import RecognitionLogger
    from gesture.recognizer import HandRecognizer
    from gesture.sink import FileSink, StdoutSink
    from gesture import landmarks as L
else:
    from .command_gate import CommandGate
    from .logger import RecognitionLogger
    from .recognizer import HandRecognizer
    from .sink import FileSink, StdoutSink
    from . import landmarks as L


def main() -> int:
    ap = argparse.ArgumentParser(description="E1 手势识别（成员 A 侧）")
    ap.add_argument("--camera", type=int, default=0, help="摄像头索引")
    ap.add_argument("--video", type=str, default=None, help="用视频文件代替摄像头")
    ap.add_argument("--sink", choices=["stdout", "file"], default="stdout")
    ap.add_argument("--out", type=str, default="commands.jsonl", help="file sink 路径")
    ap.add_argument("--log", type=str, default="recognition_log.csv")
    ap.add_argument("--display", action="store_true", help="显示摄像头画面")
    ap.add_argument("--debug", action="store_true", help="每帧打印手指伸展比例（调试校准用）")
    ap.add_argument("--min-confidence", type=float, default=0.5,
                    help="置信度门限：平均置信度低于此值的命令视为未确认，不下发（默认 0.5）")
    ap.add_argument("--smooth-alpha", type=float, default=0.6,
                    help="EMA 平滑系数：越大越跟手，越小越平滑（默认 0.6）")
    ap.add_argument("--calibrate", action="store_true",
                    help="对下发给 C 的置信度做单调显示校准（c->c**0.6），原始值仍记日志；默认关闭")
    args = ap.parse_args()

    sink = StdoutSink() if args.sink == "stdout" else FileSink(args.out)
    logger = RecognitionLogger(args.log)
    recognizer = HandRecognizer(
        min_confidence=args.min_confidence, smooth_alpha=args.smooth_alpha
    )
    gate = CommandGate(min_confidence=args.min_confidence, use_calibration=args.calibrate)

    src = args.video if args.video else args.camera
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"[E1] 无法打开视频源: {src}", file=sys.stderr)
        return 1

    print("[E1] 手势识别启动，输出 GestureCommand 给 C（Ctrl+C 退出）")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = recognizer.process_frame(rgb)
            if res is not None:
                gid, conf, lm = res.gesture_id, res.confidence, res.landmarks
                raw_conf = res.base_conf  # 模型原始置信度（校准前的真值，仅用于日志）
                if args.debug:
                    states = L.finger_states(lm)
                    ratios = L.finger_ratios(lm)
                    sstr = "".join("T" if s else "F" for s in states)
                    rstr = " ".join(f"{k}={v:.2f}" for k, v in ratios.items())
                    print(f"[dbg] {gid:10s} states=({sstr}) {rstr}", flush=True)
            else:
                gid, conf, lm, raw_conf = "NONE", 0.0, None, 0.0

            now = time.time()
            cmd = gate.update(gid, conf, now)
            emitted = cmd is not None
            logger.log(gid, conf, emitted, raw_confidence=raw_conf)
            if cmd is not None:
                sink.emit(cmd)

            if args.display:
                cv2.imshow("E1 gesture", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        recognizer.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
