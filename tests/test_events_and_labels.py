from PIL import Image
import pytest

from mahjong_assistant.application.session import Session
from mahjong_assistant.domain.hand_solver import structural_waits, riichi_ron_waits
from mahjong_assistant.vision.recognizer import Detection, Observation


def frame(hand, top=(), right=(), self_river=(), *, sideways=False):
    image = Image.new("RGB", (320, 240), "white")
    detections = [Detection(seat, (0, 0, 20, 30), image, tile,
                            sideways=sideways and seat == "top" and index == len(tiles) - 1)
                  for seat, tiles in (("hand", hand), ("top", top),
                                      ("right", right), ("self", self_river))
                  for index, tile in enumerate(tiles)]
    return Observation(image, detections, "test replay")


def test_event_stream_requires_clean_start_and_stable_changes():
    session = Session(3)
    base = frame(["1p", "2p", "3p", "4p"])
    session.update(base)
    assert not session.recent_events
    session.update(base)
    assert [event.kind for event in session.recent_events] == ["round_start"]
    assert session.tracker.ready
    next_frame = frame(["1p", "2p", "3p", "4p"], ["9s"], sideways=True)
    session.update(next_frame)
    assert not session.recent_events
    session.update(next_frame)
    assert [(event.kind, event.tile) for event in session.recent_events] == [
        ("discard", "9s"), ("riichi_candidate", "9s")]


def test_event_stream_abstains_on_unknown_or_gap():
    session = Session(3)
    base = frame(["1p", "2p", "3p", "4p"])
    session.update(base); session.update(base)
    incomplete = frame(["1p", "2p", "3p", "4p"], ["?"])
    session.update(incomplete); session.update(incomplete)
    assert not session.tracker.ready
    assert session.recent_events == []
    gap = frame(["1p", "2p", "3p", "4p"], ["9s", "8s"])
    session.update(gap); session.update(gap)
    assert any(event.kind == "tracking_gap" for event in session.recent_events)
    assert not session.tracker.ready


def test_structural_waits_and_permanent_furiten():
    hand = ["1m", "2m", "3m", "4p", "5p", "6p", "1s", "2s", "3s", "7z", "7z", "4s", "5s"]
    assert {"3s", "6s"}.issubset(structural_waits(hand, 4))
    assert riichi_ron_waits(hand, ["3s"], 4) == set()


def test_sanma_removed_manzu_and_special_hands():
    with pytest.raises(ValueError):
        structural_waits(["2m"] * 13, 3)
    chiitoitsu = ["1p"] * 2 + ["2p"] * 2 + ["3p"] * 2 + ["4p"] * 2 + ["5p"] * 2 + ["6p"] * 2 + ["7z"]
    assert "7z" in structural_waits(chiitoitsu, 3)
