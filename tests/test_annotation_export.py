import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mahjong_assistant.application.events import GameEvent
from mahjong_assistant.domain.models import Board, Opponent
from mahjong_assistant.infrastructure.storage import History
from mahjong_assistant.ml.dataset import load_games


def test_exported_replay_sheet_requires_human_truth(tmp_path):
    root = tmp_path / "private-data"
    history = History(root / "sessions" / "history.sqlite3")
    at = datetime.now(timezone.utc) - timedelta(seconds=2)
    events = [GameEvent("review-1", 1, 1, "round_start", None, None, "视频 · test.mp4", at.isoformat(), "observed"),
              GameEvent("review-1", 2, 1, "discard", "top", "9s", "视频 · test.mp4",
                        (at + timedelta(seconds=1)).isoformat(), "observed")]
    history.record_events(events)
    history.record(Board(mode=3, hand=["1p"] * 13,
                         opponents=[Opponent("top", ["9s"]), Opponent("right", [])], source="视频 · test.mp4"),
                   "review-1")
    env = dict(os.environ, MAHJONG_ASSISTANT_DATA=str(root))
    script = Path(__file__).resolve().parents[1] / "tools" / "export_annotation_template.py"
    subprocess.run([sys.executable, str(script), "review-1"], cwd=script.parents[1], env=env,
                   check=True, capture_output=True, text=True)
    sheet = root / "annotations" / "review-1.jsonl"
    payload = json.loads(sheet.read_text(encoding="utf-8"))
    assert payload["turns"][0]["needs_review"] is True
    assert payload["turns"][0]["target_concealed"] == []
    with pytest.raises(ValueError, match="requires human"):
        load_games(sheet)
