import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from gesture.command_gate import CommandGate


def test_needs_confirm_frames():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=10)
    outs = [g.update("FIST", 0.9, float(t)) for t in range(4)]
    assert all(o is None for o in outs)  # 不足 5 帧不下发


def test_emit_after_confirm():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=10)
    emitted = []
    for t in range(6):
        c = g.update("FIST", 0.9, float(t))
        if c:
            emitted.append(c)
    assert any(c.gesture_id == "FIST" for c in emitted)
    # 首次下发应在第 5 帧附近（t=4）
    assert emitted[0].gesture_code == 1  # FIST -> code 1


def test_cooldown_blocks_retrigger():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=10)
    first = None
    for t in range(5):
        c = g.update("FIST", 0.9, float(t))
        if c:
            first = c
    assert first is not None
    # 冷却期内（t=4.1）即使仍是 FIST 也不下发
    assert g.update("FIST", 0.9, 4.1) is None
    # 冷却结束后（t=15）稳定 FIST 可再次下发
    assert g.update("FIST", 0.9, 15.0) is not None


def test_majority_confirm_required():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=0)
    # 5 帧里只有 3 帧 FIST，达不到 confirm_min=4 -> 不下发
    seq = ["FIST", "FIST", "FIST", "OPEN_PALM", "OPEN_PALM"]
    outs = [g.update(s, 0.9, float(t)) for t, s in enumerate(seq)]
    assert all(o is None for o in outs)


def test_emit_reports_peak_confidence():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=0)
    # 4 帧 FIST 置信度差异明显，1 帧 OPEN_PALM
    confs = [0.6, 0.9, 0.8, 1.0, 0.7]
    seq = ["FIST", "FIST", "FIST", "FIST", "OPEN_PALM"]
    cmd = None
    for t, (s, c) in enumerate(zip(seq, confs)):
        c2 = g.update(s, c, float(t))
        if c2:
            cmd = c2
    assert cmd is not None
    # 报告窗口内峰值置信度 = max(0.6,0.9,0.8,1.0) = 1.0
    assert abs(cmd.confidence - 1.0) < 1e-6


def test_gate_uses_average_for_threshold():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=0, min_confidence=0.9)
    # 平均 = (0.6+0.9+0.8+1.0)/4 = 0.825 < 0.9 -> 不下发
    # （峰值 1.0 不用于门限判定，避免单帧抖动通过）
    confs = [0.6, 0.9, 0.8, 1.0, 0.7]
    seq = ["FIST", "FIST", "FIST", "FIST", "OPEN_PALM"]
    outs = [g.update(s, c, float(t)) for t, (s, c) in enumerate(zip(seq, confs))]
    assert all(o is None for o in outs)


def test_calibration_lifts_reported_confidence():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=0, use_calibration=True)
    # 4 帧 FIST 峰值 0.7，校准后 ~0.7**0.6 = 0.806
    confs = [0.5, 0.7, 0.6, 0.7, 0.4]
    seq = ["FIST", "FIST", "FIST", "FIST", "OPEN_PALM"]
    cmd = None
    for t, (s, c) in enumerate(zip(seq, confs)):
        c2 = g.update(s, c, float(t))
        if c2:
            cmd = c2
    assert cmd is not None
    assert cmd.confidence > 0.8  # 校准后高于原始峰值 0.7


def test_min_confidence_gate():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=0, min_confidence=0.9)
    # 虽多数一致，但平均置信度 0.825 < 0.9 -> 不下发
    confs = [0.6, 0.9, 0.8, 1.0, 0.7]
    seq = ["FIST", "FIST", "FIST", "FIST", "OPEN_PALM"]
    outs = [g.update(s, c, float(t)) for t, (s, c) in enumerate(zip(seq, confs))]
    assert all(o is None for o in outs)


def test_low_confidence_frame_not_emitted():
    g = CommandGate(confirm_frames=5, confirm_min=4, cooldown_s=0, min_confidence=0.5)
    # 全部为低置信度 FIST，平均 < 0.5 -> 不下发
    seq = ["FIST"] * 5
    confs = [0.2, 0.3, 0.1, 0.4, 0.2]
    outs = [g.update(s, c, float(t)) for t, (s, c) in enumerate(zip(seq, confs))]
    assert all(o is None for o in outs)

