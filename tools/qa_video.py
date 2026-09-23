"""End-to-end local video import, next frame, and sanma UI smoke check."""
import json
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from mahjong_assistant.ui.main_window import MainWindow
from mahjong_assistant.ui.theme import STYLE
from mahjong_assistant.infrastructure.paths import project_root

app = QApplication([])
app.setStyleSheet(STYLE)
window = MainWindow()
window.mode.setCurrentIndex(1)
window.show()
window.open_video(Path(sys.argv[1]))
state = {"stage": 0, "polls": 0}


def check():
    state["polls"] += 1
    if window.busy and state["polls"] < 40:
        QTimer.singleShot(300, check)
        return
    if state["stage"] == 0:
        state["first_hand_count"] = len(window.session.board.hand)
        state["stage"] = 1
        window.next_video()
        QTimer.singleShot(500, check)
        return
    state["second"] = window.video_second
    state["opponents"] = [o.seat for o in window.session.board.opponents]
    state["second_hand_count"] = len(window.session.board.hand)
    state["ok"] = state["second"] == 1 and state["opponents"] == ["top", "right"] and state["second_hand_count"] > 0
    window.grab().save(str(project_root()/"artifacts"/"video-ui-preview.png"))
    (project_root()/"artifacts"/"video-ui-qa.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
    window.close()
    app.quit()


QTimer.singleShot(700, check)
app.exec()
print(json.dumps(state))
raise SystemExit(0 if state.get("ok") else 1)
