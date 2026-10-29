"""纯几何手势分类：不依赖 MediaPipe / OpenCV，便于单元测试。

输入是一组带 .x/.y/.z 属性的 21 个关键点（MediaPipe Hands landmark 直接兼容）。
输出手势名称与置信度。

手指伸屈判据（对平面内任意朝向、透视均鲁棒）：
- 以手腕为原点，比较「指尖到手腕的距离」与「指节(PIP)到手腕的距离」。
- 手指伸展时，指尖在指节更外侧（离手腕更远）=> 距离比 > 1；
- 手指弯曲/握拳时，指尖收回掌心（离手腕更近）=> 距离比 < 1。
- 该判法只比距离、不依赖角度，因此手旋转、倾斜、透视压缩都不会误判。
- 阈值 EXTEND_RATIO=0.95：指尖到手腕距离 >= 0.95×指节到手腕距离 即判为伸展。

说明：本判法在手掌正对/侧对/倾斜时均稳定；仅在手严重翻转(手背朝摄像头)时失效，
如需支持需扩展本文件，不影响整体架构。
"""

from __future__ import annotations

from collections import namedtuple
from typing import List, Tuple

Landmark = namedtuple("Landmark", ["x", "y", "z"])

# MediaPipe Hands 21 关键点索引
WRIST = 0
THUMB_MCP, THUMB_IP, THUMB_TIP = 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

# 指尖到手腕距离 / 指节到手腕距离 >= 该值 判为“伸展”
EXTEND_RATIO = 0.95


def _dist(a: Landmark, b: Landmark) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5


def _finger_extended(lm: List[Landmark], tip_i: int, pip_i: int) -> bool:
    """单根手指是否伸展（以手腕为原点的距离比判法，对旋转/透视鲁棒）。"""
    wrist = lm[WRIST]
    d_tip = _dist(lm[tip_i], wrist)
    d_pip = _dist(lm[pip_i], wrist)
    if d_pip < 1e-6:
        return False
    return d_tip >= EXTEND_RATIO * d_pip


def _finger_tips_centroid(lm: List[Landmark]) -> Landmark:
    pts = [lm[INDEX_TIP], lm[MIDDLE_TIP], lm[RING_TIP], lm[PINKY_TIP]]
    n = len(pts)
    return Landmark(
        sum(p.x for p in pts) / n,
        sum(p.y for p in pts) / n,
        sum(p.z for p in pts) / n,
    )


def finger_states(lm: List[Landmark]) -> Tuple[bool, bool, bool, bool, bool]:
    """返回 (thumb, index, middle, ring, pinky) 是否伸展。"""
    thumb = _finger_extended(lm, THUMB_TIP, THUMB_IP)
    index = _finger_extended(lm, INDEX_TIP, INDEX_PIP)
    middle = _finger_extended(lm, MIDDLE_TIP, MIDDLE_PIP)
    ring = _finger_extended(lm, RING_TIP, RING_PIP)
    pinky = _finger_extended(lm, PINKY_TIP, PINKY_PIP)
    return (thumb, index, middle, ring, pinky)


def finger_ratios(lm: List[Landmark]) -> dict:
    """调试用：返回每根手指「指尖↔手腕 距离 ÷ 指节↔手腕 距离」。>1 伸展，<1 蜷缩。"""
    wrist = lm[WRIST]
    def r(tip_i, pip_i):
        dp = _dist(lm[pip_i], wrist)
        return _dist(lm[tip_i], wrist) / dp if dp > 1e-6 else 0.0
    return {
        "thb": r(THUMB_TIP, THUMB_IP),
        "idx": r(INDEX_TIP, INDEX_PIP),
        "mid": r(MIDDLE_TIP, MIDDLE_PIP),
        "rng": r(RING_TIP, RING_PIP),
        "pky": r(PINKY_TIP, PINKY_PIP),
    }


def classify_gesture(lm: List[Landmark]) -> Tuple[str, float]:
    """根据关键点判定手势 id 与置信度（0~1）。未匹配返回 ("UNKNOWN", 0.0)。"""
    thumb, index, middle, ring, pinky = finger_states(lm)
    states = (thumb, index, middle, ring, pinky)

    hand_scale = _dist(lm[WRIST], lm[MIDDLE_MCP]) + 1e-6

    # 捏合（PINCH / OK）：拇指尖与食指尖靠近，食指需伸出成圈，且其余三指收拢。
    pinch_dist = _dist(lm[THUMB_TIP], lm[INDEX_TIP]) / hand_scale
    if index and pinch_dist < 0.35 and not middle and not ring and not pinky:
        return "PINCH", 0.9

    # 握拳 vs 点赞：两者四指都收拢，仅靠拇指位置区分
    if not index and not middle and not ring and not pinky:
        if not thumb:
            return "FIST", 1.0
        # 拇指虽被几何判为“伸展”，但贴近蜷缩的四指指尖 => 实为握拳(拇指包在前面)
        d = _dist(lm[THUMB_TIP], _finger_tips_centroid(lm)) / hand_scale
        if d < 0.6:
            return "FIST", 1.0
        return "THUMBS_UP", 0.9

    if states == (True, True, True, True, True):
        return "OPEN_PALM", 1.0
    if states == (False, True, False, False, False):
        return "POINT_UP", 1.0
    if states == (False, True, True, False, False):
        return "PEACE", 1.0
    if states == (False, True, False, False, True):
        return "ROCK", 1.0
    if states == (True, False, False, False, False):
        return "THUMBS_UP", 0.9
    return "UNKNOWN", 0.0


def is_pinch(lm: List[Landmark]) -> bool:
    """判断是否为捏合/OK：拇指尖贴近食指尖、食指伸出、其余三指收拢。"""
    thumb, index, middle, ring, pinky = finger_states(lm)
    hand_scale = _dist(lm[WRIST], lm[MIDDLE_MCP]) + 1e-6
    pinch_dist = _dist(lm[THUMB_TIP], lm[INDEX_TIP]) / hand_scale
    return bool(index and pinch_dist < 0.35 and not middle and not ring and not pinky)
