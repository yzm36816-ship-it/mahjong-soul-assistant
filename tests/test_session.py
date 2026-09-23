from PIL import Image
from mahjong_assistant.application.session import Session
from mahjong_assistant.domain.models import Board, Opponent
from mahjong_assistant.vision.recognizer import Detection, Observation, TemplateBank
from mahjong_assistant.infrastructure.storage import History
import json


def observation(hand, river):
    image = Image.new("RGB", (640, 360), "white")
    detections = [Detection(seat, (0, 0, 30, 40), image, tile)
                  for seat, tiles in (("hand", hand), ("top", river)) for tile in tiles]
    return Observation(image, detections)


def test_changed_river_invalidates_manual_safety_and_riichi():
    session = Session()
    session.confirm(Board(hand=["1m"], hand_confirmed=True,
        opponents=[Opponent("top", ["2p"], riichi=True, confirmed=True)]))
    session.update(observation(["1m"], ["2p"]))
    top = next(o for o in session.board.opponents if o.seat == "top")
    assert top.confirmed and top.riichi
    session.update(observation(["1m"], ["?"]))
    top = next(o for o in session.board.opponents if o.seat == "top")
    assert not top.confirmed and not top.riichi


def test_reset_clears_previous_round_confirmation():
    session = Session()
    session.confirm(Board(hand=["1m"], hand_confirmed=True))
    session.reset()
    session.update(observation(["1m"], []))
    assert not session.board.hand_confirmed


def test_five_visible_copies_invalidate_analysis():
    session = Session()
    session.confirm(Board(hand=["5p"] * 3, hand_confirmed=True,
        opponents=[Opponent("top", ["0p", "5p"], confirmed=True)]))
    session.update(observation(["5p"] * 3, ["0p", "5p"]))
    assert not session.board.hand_confirmed
    assert "冲突" in session.board.warnings[0]


def test_sanma_does_not_create_a_phantom_third_opponent():
    session = Session(mode=3)
    session.update(observation(["1p"], []))
    assert {o.seat for o in session.board.opponents} == {"top", "right"}


def test_empty_template_bank_abstains(tmp_path):
    bank = TemplateBank(tmp_path)
    assert bank.classify(Image.new("RGB", (30, 40), "white"))[0] == "?"


def test_repeated_snapshot_not_recorded_as_new_event():
    session = Session()
    assert session.update(observation(["1p"], ["2p"]))
    assert not session.update(observation(["1p"], ["2p"]))
    assert session.changes == 1


def test_history_exports_unicode_json(tmp_path):
    history = History(tmp_path / "history.db")
    history.record(Board(source="截图示例"))
    target = tmp_path / "导出.json"
    history.export(target)
    assert json.loads(target.read_text(encoding="utf-8"))[0]["board"]["source"] == "截图示例"

