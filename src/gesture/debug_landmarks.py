"""调试脚本：把真实摄像头帧里的手指伸展比例打出来，用于校准手势阈值。

用法（PyCharm 直接 Run，或命令行）：
    python debug_landmarks.py --camera 0
    python debug_landmarks.py --video demo.mp4

按下对应数字键可给当前手势打标签并写入 debug_samples.jsonl（可选）。
按 q 退出。

输出说明（每帧一行）：
    GESTURE | states=(T/F x5) | 五指 tip/wrist 距离比 | pinch(拇指尖-食指尖/手大小)
    - 手指“伸直”时 距离比 通常 > 1；弯曲/握拳时 < 1
    - 据此可看出真实数据下每个手势的阈值该设多少
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2

# 兼容两种运行方式（脚本模式需把 src 加入路径，按 gesture 包导入）
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from gesture.recognizer import HandRecognizer
    from gesture import landmarks as L
else:
    from .recognizer import HandRecognizer
    from . import landmarks as L


def _d(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def analyze(lm):
    """返回每根手指 tip-wrist / pip-wrist 距离比 + 拇指尖-食指尖归一化距离。"""
    wrist = lm[L.WRIST]
    fingers = [
        ("idx", L.INDEX_TIP, L.INDEX_PIP),
        ("mid", L.MIDDLE_TIP, L.MIDDLE_PIP),
        ("rng", L.RING_TIP, L.RING_PIP),
        ("pky", L.PINKY_TIP, L.PINKY_PIP),
        ("thb", L.THUMB_TIP, L.THUMB_IP),
    ]
    ratios = {}
    for name, tip_i, pip_i in fingers:
        dt = _d(lm[tip_i], wrist)
        dp = _d(lm[pip_i], wrist)
        ratios[name] = dt / dp if dp > 1e-6 else 0.0
    hand_scale = _d(wrist, lm[L.MIDDLE_MCP]) + 1e-6
    pinch = _d(lm[L.THUMB_TIP], lm[L.INDEX_TIP]) / hand_scale
    states = L.finger_states(lm)
    gid, conf = L.classify_gesture(lm)
    return ratios, pinch, states, gid, conf


def frame_to_list(lm):
    return [{"x": round(p.x, 4), "y": round(p.y, 4), "z": round(p.z, 4)} for p in lm]


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--camera", type=int, help="摄像头索引")
    src.add_argument("--video", type=str, help="视频文件路径")
    ap.add_argument("--out", type=str, default=None, help="采样输出 jsonl（按键打标签）")
    args = ap.parse_args()

    rec = HandRecognizer()
    cap = cv2.VideoCapture(args.camera if args.camera is not None else args.video)
    if not cap.isOpened():
        print(f"无法打开视频源: {args.camera if args.camera is not None else args.video}")
        return

    samples = []
    label_map = {
        "1": "FIST", "2": "OPEN_PALM", "3": "POINT_UP",
        "4": "PEACE", "5": "ROCK", "6": "PINCH", "7": "THUMBS_UP",
    }

    print("调试模式：做手势，终端会打印每帧分析；按 1-7 给当前帧打标签并保存；按 q 退出。\n")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        lm, base_conf = rec.process_frame(rgb)
        if lm is None:
            print("NO_HAND")
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            continue

        ratios, pinch, states, gid, conf = analyze(lm)
        rstr = " ".join(f"{k}={v:.2f}" for k, v in ratios.items())
        sstr = "".join("T" if s else "F" for s in states)
        line = f"{gid:10s} conf={conf:.2f} states=({sstr}) {rstr} pinch={pinch:.2f}"
        print(line)

        if args.out:
            # 自动每帧缓存最近一帧，按键时打标签
            _last = {"landmarks": frame_to_list(lm), "auto_gesture": gid}

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        ch = chr(key) if 32 <= key < 127 else ""
        if ch in label_map and args.out:
            samples.append({"label": label_map[ch], "landmarks": frame_to_list(lm)})
            print(f"  >> 已记录样本: {label_map[ch]} (共 {len(samples)} 个)")

    cap.release()
    cv2.destroyAllWindows()
    if args.out and samples:
        with open(args.out, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"已保存 {len(samples)} 个样本到 {args.out}")


if __name__ == "__main__":
    main()
