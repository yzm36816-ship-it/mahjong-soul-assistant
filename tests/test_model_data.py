import json
import numpy as np
import pytest

from mahjong_assistant.ml.dataset import (FEATURE_SIZE, PublicPosition, example_from_turn,
                                          features, load_games, split_for_game, target_vectors)


def example_turn():
    return {"turn": 2, "event_type": "discard", "observer_hand": ["1p"],
            "rivers": {"self": [], "top": ["9s"], "right": []}, "target_seat": "top",
            "target_discard_history": ["9s"],
            "target_concealed": "1p 2p 3p 4p 5p 6p 7p 8p 9p 1s 2s 3s 7z".split(),
            "target_meld_count": 0, "target_riichi": True, "temporary_furiten": False}


def test_training_features_never_consume_hidden_hand():
    turn = example_turn()
    first = example_from_turn("game-1", 3, turn)
    vector = features(first.public)
    assert vector.shape == (FEATURE_SIZE,)
    assert "7z" in first.waits and "7z" in first.ron_waits
    second = dict(turn, target_concealed="1p 1p 2p 2p 3p 3p 4p 4p 5p 5p 6p 6p 6z".split())
    changed = example_from_turn("game-1", 3, second)
    assert np.array_equal(vector, features(changed.public))
    assert first.waits != changed.waits


def test_furiten_keeps_shape_wait_but_removes_ron():
    turn = example_turn()
    turn["rivers"]["top"] = ["7z", "9s"]
    turn["target_discard_history"] = ["7z", "9s"]
    example = example_from_turn("game-1", 3, turn)
    assert "7z" in example.waits
    assert example.ron_waits == ()


def test_unverified_data_is_rejected_and_split_is_by_game(tmp_path):
    game = {"game_id": "a", "mode": 3, "source": {"provenance": "downloaded", "description": "public"},
            "turns": [example_turn()]}
    path = tmp_path / "games.jsonl"
    path.write_text(json.dumps(game) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unverified"):
        load_games(path)
    game["source"]["provenance"] = "self_recorded"
    path.write_text(json.dumps(game) + "\n", encoding="utf-8")
    assert len(load_games(path)) == 1
    assert split_for_game("a") == split_for_game("a")
