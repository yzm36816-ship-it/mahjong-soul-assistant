"""Train both variants from explicitly sourced, post-discard JSONL replays."""
import argparse
import hashlib
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
digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
dataset_info = {"sha256": digest, "file": args.input.name}
manifest_path = args.input.with_suffix(".manifest.json")
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha256") != digest:
        raise ValueError("dataset manifest SHA256 does not match the training file")
    dataset_info.update({key: manifest[key] for key in
                         ("generator", "generator_version", "policy", "rule", "game_length",
                          "seed_start", "seed_note", "games_per_mode", "data_kind",
                          "human_game_records", "event_log_sha256")
                         if key in manifest})
reports = [train_mode(examples, mode, source_summary(args.input, mode), data_root() / "models", args.epochs,
                      dataset_info=dataset_info) for mode in (3, 4)]
print(json.dumps(reports, ensure_ascii=False, indent=2))
