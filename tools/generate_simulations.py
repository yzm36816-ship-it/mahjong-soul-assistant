"""Generate reproducible, fully labelled *synthetic* Mahjong self-play games."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

from mahjong_assistant.infrastructure.paths import data_root
from mahjong_assistant.ml.dataset import example_from_turn, split_for_game
from mahjong_assistant.ml.simulation import game_from_log, simulate_game


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games-per-mode", type=int, default=150)
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--length", choices=("single", "east", "half"), default="east")
    parser.add_argument("--output", type=Path, default=data_root() / "simulations" / "riichienv-greedy-v2.jsonl")
    args = parser.parse_args()
    if args.games_per_mode < 3 or args.seed < 0:
        parser.error("games-per-mode must be at least 3 and seed must be nonnegative")

    simulator_version = version("riichienv")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    logs_path = args.output.with_suffix(".events.jsonl")
    game_counts = {str(mode): {"train": 0, "validation": 0, "test": 0} for mode in (3, 4)}
    turn_counts = {str(mode): {"train": 0, "validation": 0, "test": 0} for mode in (3, 4)}
    tenpai_counts = {str(mode): 0 for mode in (3, 4)}
    riichi_counts = {str(mode): 0 for mode in (3, 4)}
    with args.output.open("w", encoding="utf-8", newline="\n") as stream, \
            logs_path.open("w", encoding="utf-8", newline="\n") as logs:
        for mode in (3, 4):
            for index in range(args.games_per_mode):
                seed = args.seed + index
                game_id = f"riichienv-{simulator_version}-{args.length}-{mode}p-{seed}"
                events = simulate_game(mode, seed, args.length)
                logs.write(json.dumps({"game_id": game_id, "mode": mode,
                                       "simulator_version": simulator_version,
                                       "events": events}, ensure_ascii=False, separators=(",", ":")) + "\n")
                game = game_from_log(events, mode, game_id, simulator_version=simulator_version)
                examples = [example_from_turn(game_id, mode, turn) for turn in game["turns"]]
                split = split_for_game(game_id)
                game_counts[str(mode)][split] += 1
                turn_counts[str(mode)][split] += len(examples)
                tenpai_counts[str(mode)] += sum(example.tenpai for example in examples)
                riichi_counts[str(mode)] += sum(example.waits is not None for example in examples)
                stream.write(json.dumps(game, ensure_ascii=False, separators=(",", ":")) + "\n")
            print(f"{mode}p: {args.games_per_mode} simulated matches, "
                  f"{sum(turn_counts[str(mode)].values())} post-discard samples")

    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    manifest = {
        "generator": "RiichiEnv",
        "generator_version": simulator_version,
        "rule": "GameRule.default_mjsoul()",
        "policy": "greedy-shanten-v2: win, 35% per-opportunity riichi, min-shanten discard, pass calls",
        "data_kind": "synthetic_demo",
        "human_game_records": False,
        "game_length": args.length,
        "seed_start": args.seed,
        "seed_note": "RiichiEnv 0.4.10 does not reproduce later East-round walls from reset(seed); exact regeneration uses the archived MJAI event log.",
        "games_per_mode": args.games_per_mode,
        "game_counts": game_counts,
        "sample_counts": turn_counts,
        "tenpai_positive_counts": tenpai_counts,
        "riichi_sample_counts": riichi_counts,
        "sha256": digest,
        "event_log_sha256": hashlib.sha256(logs_path.read_bytes()).hexdigest(),
        "event_log_file": str(logs_path.resolve()),
        "training_file": str(args.output.resolve()),
        "real_world_accuracy_claim": False,
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dataset: {args.output.resolve()}\nEvent log: {logs_path.resolve()}\n"
          f"Manifest: {manifest_path.resolve()}\nSHA256: {digest}")


if __name__ == "__main__":
    main()
