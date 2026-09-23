"""Train both variants from explicitly sourced, post-discard JSONL replays."""
import argparse
import json
from pathlib import Path

from mahjong_assistant.infrastructure.paths import data_root
from mahjong_assistant.ml.dataset import load_games, source_summary
from mahjong_assistant.ml.model import train_mode

parser = argparse.ArgumentParser()
parser.add_argument("input", type=Path, help="JSONL game records; see docs/model-data.md")
parser.add_argument("--epochs", type=int, default=35)
args = parser.parse_args()
examples = load_games(args.input)
sources = source_summary(args.input)
reports = [train_mode(examples, mode, sources, data_root() / "models", args.epochs) for mode in (3, 4)]
print(json.dumps(reports, ensure_ascii=False, indent=2))
