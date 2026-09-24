"""Rebuild exact labelled data from archived, omniscient RiichiEnv MJAI logs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from mahjong_assistant.ml.dataset import example_from_turn
from mahjong_assistant.ml.simulation import game_from_log


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_log", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest or args.event_log.with_name(
        args.event_log.name.removesuffix(".gz").replace(".events.jsonl", ".manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = args.event_log.read_bytes()
    if args.event_log.suffix == ".gz":
        payload = gzip.decompress(payload)
    event_digest = hashlib.sha256(payload).hexdigest()
    if event_digest != manifest["event_log_sha256"]:
        raise ValueError("archived event log SHA256 does not match manifest")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with io.StringIO(payload.decode("utf-8")) as logs, \
            args.output.open("w", encoding="utf-8", newline="\n") as dataset:
        for line_number, line in enumerate(logs, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            game = game_from_log(record["events"], record["mode"], record["game_id"],
                                 simulator_version=record["simulator_version"])
            for turn in game["turns"]:
                example_from_turn(game["game_id"], game["mode"], turn)
            dataset.write(json.dumps(game, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"rebuild hash mismatch: expected {manifest['sha256']}, got {digest}")
    args.output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"games": count, "sha256": digest, "matches_expected": True}, indent=2))


if __name__ == "__main__":
    main()
