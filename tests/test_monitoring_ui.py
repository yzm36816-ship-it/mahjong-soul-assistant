import os
import time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from mahjong_assistant.ui.main_window import MainWindow
from mahjong_assistant.vision.recognizer import Observation, Detection


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        QTest.qWait(50)
    return predicate()


def test_monitor_timer_updates_cards_and_keeps_running_with_details_open(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("MAHJONG_ASSISTANT_DATA", str(tmp_path))
    monkeypatch.setattr("mahjong_assistant.ui.main_window.game_windows", lambda: [])
    monkeypatch.setattr("mahjong_assistant.infrastructure.gpu_capture.stop", lambda: None)
    image = Image.new("RGB", (640, 360))
    calls = []

    def capture(_):
        calls.append(1)
        return image

    monkeypatch.setattr("mahjong_assistant.ui.main_window.capture", capture)
    window = MainWindow()
    window.windows.clear()
    window.windows.addItem("雀魂测试窗口", 123)

    def read(image, source):
        river = ["1p"] + (["3p"] if len(calls) >= 3 else [])
        tiles = [Detection(s, (0,0,30,40), image, t, .95, t)
                 for s, values in (("hand", ["1p","2p","4p","6p"]),("top",river)) for t in values]
        return Observation(image, tiles, source)

    window.recognizer.read = read
    window.timer.setInterval(60)
    window.toggle_live()
    assert wait_until(lambda: any(o.seat == "top" and "3p" in o.discards
                                  for o in window.session.board.opponents)
                      and "识别现物" in window.cards["top"][3].text())
    assert len(calls) >= 3
    assert window.session.board.auto_hand_ready
    assert "识别现物" in window.cards["top"][3].text()
    assert "3p" in next(o for o in window.session.board.opponents if o.seat == "top").discards
    window.show_risks("top")
    window.show_preview()
    before = len(calls)
    assert wait_until(lambda: len(calls) > before)
    assert window.timer.isActive()
    window.stop_live()
    QTest.qWait(100)
    after = len(calls)
    QTest.qWait(100)
    assert len(calls) == after
    window.close()
