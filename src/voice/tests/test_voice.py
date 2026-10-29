"""E2 语音模块单元测试（纯逻辑，无需麦克风/外网）。"""

from voice.command_gate import VoiceCommandGate
from voice.recognizer import MockTextBackend, VoskBackend, VoiceRecognizer
from voice.voice_command import VoiceCommand


def test_match_command_exact():
    assert VoiceRecognizer.match_command("帮我分类") == "SORT_ONE"


def test_match_command_with_prefix_suffix():
    assert VoiceRecognizer.match_command("请帮我分类一下") == "SORT_ONE"
    assert VoiceRecognizer.match_command("帮我分类吧谢谢") == "SORT_ONE"


def test_match_command_no_trigger():
    assert VoiceRecognizer.match_command("帮我") is None
    assert VoiceRecognizer.match_command("今天天气不错") is None
    assert VoiceRecognizer.match_command("分类") is None
    assert VoiceRecognizer.match_command("") is None


def test_voice_command_to_event_dict_keys():
    cmd = VoiceCommand(text="帮我分类", confidence=0.9, voice_code=1)
    ev = cmd.to_event_dict()
    # 与 api/openapi.yaml 的 VoiceCommand 字段对齐
    assert set(ev.keys()) == {"command_id", "text", "confidence", "captured_at", "latency_ms"}
    assert ev["text"] == "帮我分类"
    assert ev["confidence"] == 0.9


def test_iter_commands_filters_irrelevant():
    # 无关语音不应产生命令（误触发率考核项）
    items = [("今天天气不错", 0.95), ("帮我倒杯水", 0.95), ("随便说点什么", 0.9)]
    rec = VoiceRecognizer(MockTextBackend(items))
    out = list(rec.iter_commands())
    assert out == []


def test_iter_commands_filters_low_confidence():
    items = [("帮我分类", 0.3)]  # 置信度低于默认 0.5
    rec = VoiceRecognizer(MockTextBackend(items), min_confidence=0.5)
    assert list(rec.iter_commands()) == []


def test_iter_commands_emits_on_match():
    items = [("帮我分类", 0.9), ("无关语音", 0.95), ("帮我分类", 0.8)]
    rec = VoiceRecognizer(MockTextBackend(items), min_confidence=0.5)
    out = list(rec.iter_commands())
    assert len(out) == 2
    assert all(c.voice_code == 1 for c in out)
    assert out[0].text == "帮我分类"


def test_false_trigger_rate_over_irrelevant_set():
    # E2 验收：20 条无关语音，误触发率 ≤5%（此处为 0%）
    irrelevant = [
        "打开灯", "今天星期几", "播放音乐", "现在几点", "讲个笑话",
        "帮我查天气", "关闭窗口", "翻译这段话", "导航回家", "计时五分钟",
        "设置闹钟", "读这条消息", "音量调大", "搜索资料", "发送微信",
        "提醒我开会", "切换应用", "截图保存", "计算总和", "拨打电话",
    ]
    items = [(t, 0.9) for t in irrelevant]
    rec = VoiceRecognizer(MockTextBackend(items), min_confidence=0.5)
    out = list(rec.iter_commands())
    assert len(out) == 0


def test_gate_cooldown_blocks_retrigger():
    gate = VoiceCommandGate(cooldown_s=3.0)
    cmd = VoiceCommand(text="帮我分类", confidence=0.9, voice_code=1)
    # 第一次触发
    assert gate.update(cmd, now=0.0) is not None
    # 冷却期内（now=2.0 < 3.0）不触发
    assert gate.update(cmd, now=2.0) is None
    # 冷却结束后（now=3.0）可再次触发
    assert gate.update(cmd, now=3.0) is not None


def test_gate_low_confidence_blocked():
    gate = VoiceCommandGate(cooldown_s=0.0, min_confidence=0.5)
    cmd = VoiceCommand(text="帮我分类", confidence=0.2, voice_code=1)
    assert gate.update(cmd, now=0.0) is None


def test_vosk_backend_raises_when_missing():
    # 沙箱未安装 vosk：构造即应抛 ImportError（不静默失败），由 app 上层引导安装。
    try:
        import vosk  # noqa: F401
        return  # 本地已装则跳过该断言
    except ImportError:
        pass
    be = VoskBackend(model_path="__nonexistent_model_dir__")
    raised = False
    try:
        list(be.__iter__())
    except ImportError:
        raised = True
    assert raised, "VoskBackend 在缺失依赖时应抛出 ImportError"
