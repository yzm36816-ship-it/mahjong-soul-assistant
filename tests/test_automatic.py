from PIL import Image
from mahjong_assistant.domain.models import Board, Opponent
from mahjong_assistant.domain.analysis import assess
from mahjong_assistant.domain.waits import possible_ron_waits
from mahjong_assistant.vision.recognizer import Detection, Observation
from mahjong_assistant.application.session import Session


def frame(hand=None, river=None, sideways=False):
    image = Image.new("RGB", (640, 360))
    hand = hand if hand is not None else ["1p", "2p", "3p", "4p"]
    river = river if river is not None else ["1p", "5m"]
    detections = [Detection(s, (10, 10, 30, 40), image, t, .95, t, sideways and s == "top")
                  for s, tiles in (("hand", hand), ("top", river)) for t in tiles]
    return Observation(image, detections)


def test_no_manual_click_needed_after_two_frames():
    session = Session()
    observation = frame()
    session.update(observation)
    assert not session.board.auto_hand_ready
    session.update(observation)
    assert session.board.auto_hand_ready
    assert not session.board.hand_confirmed
    top = next(o for o in session.board.opponents if o.seat == "top")
    assert top.auto_observed and not top.confirmed
    result = next(a for a in assess(session.board) if a.seat == "top")
    assert result.status != "证据待确认"
    assert any(r.level == "识别现物" and r.score > 0 for r in result.risks)


def test_new_discard_automatically_recovers_without_clicks():
    session = Session()
    for _ in range(2):
        session.update(frame())
    session.update(frame(river=["1p", "5m", "2p"]))
    top = next(o for o in session.board.opponents if o.seat == "top")
    assert not top.auto_observed
    session.update(frame(river=["1p", "5m", "2p"]))
    top = next(o for o in session.board.opponents if o.seat == "top")
    assert top.auto_observed
    assert "2p" in top.discards


def test_single_image_is_explicitly_allowed_to_offer_conditional_analysis():
    session = Session()
    session.update(frame(), require_stability=False)
    assert session.board.auto_hand_ready
    assert not session.board.hand_confirmed


def test_conflicting_counts_cannot_become_auto_safe():
    session = Session()
    for _ in range(3):
        session.update(frame(["1p"] * 4, ["1p"]))
    assert not session.board.auto_hand_ready
    assert not any(o.auto_observed for o in session.board.opponents)


def test_no_hand_on_settlement_clears_automatic_analysis():
    session = Session()
    for _ in range(2):
        session.update(frame())
    session.update(frame([], ["1p"]))
    assert not session.board.auto_hand_ready
    assert all(not result.risks for result in assess(session.board))


def test_sideways_is_only_candidate_not_confirmed_riichi():
    session = Session()
    for _ in range(2):
        session.update(frame(sideways=True))
    top = next(o for o in session.board.opponents if o.seat == "top")
    assert top.riichi_candidate and not top.riichi
    result = next(a for a in assess(session.board) if a.seat == "top")
    assert "疑似立直" in result.status
    assert result.waits


def test_furiten_removes_ron_candidates_but_suji_does_not_remove_all_waits():
    opponent = Opponent("top", ["1m", "7m"], riichi=True, confirmed=True)
    candidates = {c.tile:c for c in possible_ron_waits(Board(), opponent)}
    assert "1m" not in candidates and "7m" not in candidates
    assert "4m" in candidates
    assert not any("两面" in s for s in candidates["4m"].shapes)
    assert "单骑 / 七对子" in candidates["4m"].shapes


def test_visible_wall_removes_only_impossible_shapes():
    opponent = Opponent("top", riichi=True, confirmed=True)
    candidates = {c.tile:c for c in possible_ron_waits(Board(visible_counts={"2p": 4}), opponent)}
    assert not any("两面" in s for s in candidates["1p"].shapes)
    assert "单骑 / 七对子" in candidates["1p"].shapes


def test_sanma_candidates_never_include_removed_manzu():
    candidates = possible_ron_waits(Board(mode=3), Opponent("top", riichi=True, confirmed=True))
    assert not any(c.tile in {f"{i}m" for i in range(2, 9)} for c in candidates)


def test_no_riichi_no_wait_prediction_and_no_implicit_confidence():
    assert possible_ron_waits(Board(), Opponent("top", confirmed=True)) == []

