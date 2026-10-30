import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gesture.smoother import GestureSmoother


def test_smoothing_converges_to_stable_gesture():
    s = GestureSmoother(alpha=0.6, decay=0.6)
    # 持续稳定的手势：平滑置信度应逼近其原始高分
    cat, score = "OPEN_PALM", 0.0
    for _ in range(10):
        cat, score = s.update("OPEN_PALM", 0.95)
    assert cat == "OPEN_PALM"
    assert score > 0.9


def test_smoothing_suppresses_single_false_frame():
    s = GestureSmoother(alpha=0.6, decay=0.6)
    for _ in range(10):
        s.update("OPEN_PALM", 0.95)
    # 插入一帧误判为 FIST（低分）
    cat, _ = s.update("FIST", 0.3)
    # 最佳类别仍应为 OPEN_PALM（被平滑拉住）
    assert cat == "OPEN_PALM"


def test_reset_clears_state():
    s = GestureSmoother()
    for _ in range(5):
        s.update("FIST", 0.9)
    s.reset()
    assert s._ema == {}


def test_decay_lets_new_gesture_take_over():
    s = GestureSmoother(alpha=0.6, decay=0.6)
    for _ in range(10):
        s.update("OPEN_PALM", 0.95)
    # 持续切换到 FIST：若干帧后最佳类别应翻转为 FIST
    cat = "OPEN_PALM"
    for _ in range(15):
        cat, _ = s.update("FIST", 0.95)
    assert cat == "FIST"
