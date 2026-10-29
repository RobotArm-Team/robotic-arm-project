import os
import sys
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gesture.landmarks import Landmark, classify_gesture

# 基础手骨架（正对、手指朝上，归一化坐标，y 向下）
_THUMB_MCP = (0.42, 0.70)
_THUMB_DIR = (-0.4472, -0.8944)
_MCS = {
    5: (0.46, 0.58),   # INDEX
    9: (0.50, 0.56),   # MIDDLE
    13: (0.54, 0.58),  # RING
    17: (0.58, 0.62),  # PINKY
}
_WRIST = (0.50, 0.90)
_FDIR = (0.0, -1.0)


def _mk(fingers, pinch=False):
    """构造 21 个关键点；fingers = (thumb, index, middle, ring, pinky) 是否伸展。

    伸展：指尖到掌指关节(MCP)距离 ≈ 两段骨骼长度和（近似共线）。
    收拢：指尖折回掌心，远离 MCP（几何折叠判据，对朝向鲁棒）。
    pinch=True 时食指伸出成圈且指尖与拇指尖相触（OK 手势）。
    """
    th, ix, mi, ri, pi = fingers
    pts = {i: list(_WRIST) for i in range(21)}

    # 四指
    for mcp_i, ext in ((5, ix), (9, mi), (13, ri), (17, pi)):
        mx, my = _MCS[mcp_i]
        pip_i, tip_i = {5: (6, 8), 9: (10, 12), 13: (14, 16), 17: (18, 20)}[mcp_i]
        if ext:
            pts[pip_i] = [mx + _FDIR[0] * 0.13, my + _FDIR[1] * 0.13]
            pts[tip_i] = [mx + _FDIR[0] * 0.26, my + _FDIR[1] * 0.26]
        else:
            pts[pip_i] = [mx + _FDIR[0] * 0.10, my + _FDIR[1] * 0.10]
            pts[tip_i] = [mx + _FDIR[0] * 0.02, my + _FDIR[1] * 0.02]
        pts[mcp_i] = [mx, my]

    # 拇指
    mx, my = _THUMB_MCP
    pts[2] = list(_THUMB_MCP)
    if th:
        pts[3] = [mx + _THUMB_DIR[0] * 0.13, my + _THUMB_DIR[1] * 0.13]
        pts[4] = [mx + _THUMB_DIR[0] * 0.26, my + _THUMB_DIR[1] * 0.26]
    else:
        pts[3] = [mx, my - 0.10]
        pts[4] = [mx + 0.04, my - 0.04]

    # 捏合：食指伸出成圈，指尖与拇指尖相触
    if pinch:
        ix_mx, ix_my = _MCS[5]
        idx_tip = [ix_mx, ix_my - 0.26]
        pts[8] = list(idx_tip)
        pts[4] = list(idx_tip)
        pts[3] = [(idx_tip[0] + pts[2][0]) / 2, (idx_tip[1] + pts[2][1]) / 2]

    return [Landmark(x, y, 0.0) for x, y in (pts[i] for i in range(21))]


def test_fist():
    gid, _ = classify_gesture(_mk((False, False, False, False, False)))
    assert gid == "FIST"


def test_open_palm():
    gid, _ = classify_gesture(_mk((True, True, True, True, True)))
    assert gid == "OPEN_PALM"


def test_point_up():
    gid, _ = classify_gesture(_mk((False, True, False, False, False)))
    assert gid == "POINT_UP"


def test_peace():
    gid, _ = classify_gesture(_mk((False, True, True, False, False)))
    assert gid == "PEACE"


def test_rock():
    gid, _ = classify_gesture(_mk((False, True, False, False, True)))
    assert gid == "ROCK"


def test_thumbs_up():
    gid, _ = classify_gesture(_mk((True, False, False, False, False)))
    assert gid == "THUMBS_UP"


def test_pinch():
    gid, _ = classify_gesture(_mk((False, False, False, False, False), pinch=True))
    assert gid == "PINCH"


def test_unknown_pattern():
    # 仅中指伸展（非常见手势）应落入 UNKNOWN
    gid, conf = classify_gesture(_mk((False, False, True, False, False)))
    assert gid == "UNKNOWN"
    assert conf == 0.0
