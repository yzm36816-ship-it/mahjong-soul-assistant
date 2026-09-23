import pytest
from mahjong_assistant.domain.tiles import parse_tiles, normalize
from mahjong_assistant.domain.models import Board, Opponent
from mahjong_assistant.domain.analysis import assess, tile_risk


def test_compact_input_and_red_five_identity():
    assert parse_tiles("123m 05p 东白") == ["1m", "2m", "3m", "0p", "5p", "1z", "5z"]
    assert normalize("0p") == "5p"


@pytest.mark.parametrize("text", ["11111m", "5550p5p", "0z", "8z", "abc", "1mxxx"])
def test_invalid_tiles_rejected(text):
    with pytest.raises(ValueError):
        parse_tiles(text)


def test_sanma_rejects_removed_tiles():
    with pytest.raises(ValueError):
        parse_tiles("2m", mode=3)
    assert parse_tiles("19m東白", mode=3) == ["1m", "9m", "1z", "5z"]


def test_only_confirmed_river_can_establish_genbutsu():
    opponent = Opponent("top", ["5p"])
    assert tile_risk("0p", opponent).level == "待核对"
    opponent.confirmed = True
    assert tile_risk("0p", opponent).level == "现物"
    assert "自摸" in tile_risk("0p", opponent).reason


def test_suji_middle_requires_both_sides_and_never_absolute_safety():
    opponent = Opponent("right", ["1m"], confirmed=True)
    assert tile_risk("4m", opponent).level == "优先警戒"
    opponent.discards.append("7m")
    risk = tile_risk("4m", opponent)
    assert risk.level == "筋·仍有险"
    assert risk.score > 0
    assert "单骑" in risk.reason


def test_riichi_is_known_tenpai_but_waits_stay_unknown():
    board = Board(hand=["1p"], hand_confirmed=True,
                  opponents=[Opponent("top", riichi=True, confirmed=True)])
    result = assess(board)[0]
    assert result.status == "已确认立直"
    assert "等待未知" in result.detail


def test_melds_are_heuristics_not_proof():
    board = Board(opponents=[Opponent("left", melds=3, confirmed=True)])
    result = assess(board)[0]
    assert result.status == "听牌倾向较高"
    assert "仍未听牌" in result.detail


def test_safety_is_per_opponent():
    one = Opponent("top", ["1p"], confirmed=True)
    two = Opponent("right", [], confirmed=True)
    assert tile_risk("1p", one).score == 0
    assert tile_risk("1p", two).score > 0


def test_unconfirmed_hand_never_produces_tile_recommendations():
    board = Board(hand=["1p"], opponents=[Opponent("top", ["1p"], confirmed=True)])
    assert assess(board)[0].risks == []


def test_unconfirmed_riichi_is_not_a_fact():
    board = Board(opponents=[Opponent("top", riichi=True, confirmed=False)])
    assert assess(board)[0].status == "证据待确认"
