"""Check that simulator labels and public positions remain separate."""

import hashlib
import gzip
import json
from pathlib import Path
import subprocess
import sys

import pytest

from mahjong_assistant.ml.dataset import example_from_turn, features
from mahjong_assistant.ml.simulation import game_from_log, simulate_game


@pytest.mark.parametrize("mode", (3, 4))
def test_simulated_game_has_valid_private_labels_and_public_features(mode):
    pytest.importorskip("riichienv")
    log = simulate_game(mode, 41, "single")
    game = game_from_log(log, mode, f"test-{mode}", simulator_version="test")
    assert game["source"]["provenance"] == "synthetic_demo"
    assert game["turns"]
    examples = [example_from_turn(game["game_id"], mode, turn) for turn in game["turns"]]
    assert all(example.public.target_seat != "self" for example in examples)
    assert all(len(features(example.public)) > 0 for example in examples)
    if mode == 3:
        assert all(tile not in {f"{n}m" for n in range(2, 9)}
                   for turn in game["turns"] for tile in turn["target_concealed"])


def test_accepted_riichi_marks_the_declaration_discard():
    events = [
        {"type": "start_kyoku", "tehais": [
            ["1m", "1m", "9m", "9m", "1p", "2p", "E", "S", "W", "N", "P", "F", "C"],
            ["1p", "1p", "2p", "2p", "3p", "3p", "4p", "4p", "5p", "5p", "6p", "6p", "7p"],
            ["1s", "1s", "2s", "2s", "3s", "3s", "4s", "4s", "5s", "5s", "6s", "6s", "7s"]]},
        {"type": "tsumo", "actor": 1, "pai": "8p"},
        {"type": "reach", "actor": 1},
        {"type": "dahai", "actor": 1, "pai": "8p"},
        {"type": "reach_accepted", "actor": 1},
    ]
    game = game_from_log(events, 3, "riichi-test")
    assert game["turns"][0]["target_riichi"] is True
    assert example_from_turn(game["game_id"], 3, game["turns"][0]).waits is not None


def test_calls_are_rejected_instead_of_fabricating_labels():
    with pytest.raises(ValueError, match="unsupported self-play call"):
        game_from_log([{"type": "chi", "actor": 1}], 4, "invalid")


@pytest.mark.parametrize("compressed", (False, True))
def test_archived_event_log_rebuilds_identical_training_bytes(tmp_path, compressed):
    pytest.importorskip("riichienv")
    events = simulate_game(3, 7, "single")
    game = game_from_log(events, 3, "rebuild-test", simulator_version="test")
    encode = lambda value: (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    dataset_bytes = encode(game)
    event_log = tmp_path / "sample.events.jsonl"
    event_log.write_bytes(encode({"game_id": "rebuild-test", "mode": 3,
                                  "simulator_version": "test", "events": events}))
    manifest = {"sha256": hashlib.sha256(dataset_bytes).hexdigest(),
                "event_log_sha256": hashlib.sha256(event_log.read_bytes()).hexdigest()}
    (tmp_path / "sample.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if compressed:
        archive = tmp_path / "sample.events.jsonl.gz"
        archive.write_bytes(gzip.compress(event_log.read_bytes(), mtime=0))
        event_log = archive
    output = tmp_path / "rebuilt.jsonl"
    script = Path(__file__).resolve().parents[1] / "tools" / "rebuild_simulations.py"
    subprocess.run([sys.executable, str(script), str(event_log), "--output", str(output)],
                   check=True, capture_output=True)
    assert output.read_bytes() == dataset_bytes
