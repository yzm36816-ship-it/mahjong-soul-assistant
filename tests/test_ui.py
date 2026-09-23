import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from mahjong_assistant.domain.models import Board, Opponent
from mahjong_assistant.ui.dialogs import BoardDialog
from mahjong_assistant.vision.recognizer import Recognizer


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_manual_confirmation_round_trip(app):
    dialog = BoardDialog(Board(opponents=[Opponent("top")]))
    dialog.hand.setText("123m456p789s東東白白")
    _, river, melds, riichi = dialog.fields[0]
    river.setText("9m 1p")
    riichi.setChecked(True)
    dialog.commit()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.result_board.hand_confirmed
    assert dialog.result_board.opponents[0].riichi
    dialog.close()


def test_invalid_open_riichi_cannot_be_confirmed(app, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _, title, message: messages.append(message))
    dialog = BoardDialog(Board(opponents=[Opponent("top")]))
    dialog.hand.setText("123m456p789s東")
    _, river, melds, riichi = dialog.fields[0]
    melds.setValue(1)
    riichi.setChecked(True)
    dialog.commit()
    assert dialog.result_board is None
    assert any("不能立直" in text for text in messages)
    dialog.close()


def test_profile_calibration_is_isolated_and_persistent(tmp_path, monkeypatch):
    monkeypatch.setenv("MAHJONG_ASSISTANT_DATA", str(tmp_path))
    recognizer = Recognizer()
    original = list(recognizer.regions["hand"])
    recognizer.use_profile("video")
    recognizer.regions["hand"] = [.1, .8, .7, .99]
    recognizer.save_regions()
    second = Recognizer()
    assert second.regions["hand"] == original
    second.use_profile("video")
    assert second.regions["hand"] == [.1, .8, .7, .99]

