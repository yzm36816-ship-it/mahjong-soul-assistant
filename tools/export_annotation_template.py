"""Create a private, deliberately untrainable review sheet from verified events.

Open a full Mahjong Soul replay to fill target_concealed and confirm all fields.
"""
import argparse
import json
from pathlib import Path

from mahjong_assistant.infrastructure.paths import data_root
from mahjong_assistant.infrastructure.storage import History

parser = argparse.ArgumentParser()
parser.add_argument("session_id", help="Session ID shown by the local dashboard API")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
history = History()
events = history.events(args.session_id)
snapshots = history.snapshots(args.session_id)
if not events or not snapshots:
    raise SystemExit("No recorded events and snapshots for this session")
mode = snapshots[0]["board"]["mode"]
turns = []
trusted = False
histories = {seat: [] for seat in (("self", "top", "right") if mode == 3 else ("self", "left", "top", "right"))}
for event in events:
    if event["kind"] == "round_start":
        trusted = True
        histories = {seat: [] for seat in histories}
    if event["kind"] in ("tracking_gap", "river_removed_candidate", "midround_join"):
        trusted = False
    if event["kind"] != "discard" or not event["seat"]:
        continue
    histories[event["seat"]].append(event["tile"])
    if not trusted or event["seat"] == "self":
        continue
    snapshot = next((item for item in snapshots if item["at"] >= event["observed_at"]), None)
    if snapshot is None:
        continue
    board = snapshot["board"]
    opponents = {item["seat"]: item for item in board["opponents"]}
    if event["seat"] not in opponents:
        continue
    rivers = {seat: (histories[seat].copy() if seat == "self" else opponents[seat]["discards"])
              for seat in histories}
    turns.append({"turn": event["sequence"], "event_type": "discard",
                  "observer_hand": board["hand"], "rivers": rivers,
                  "target_seat": event["seat"], "target_discard_history": histories[event["seat"]].copy(),
                  "target_concealed": [], "target_meld_count": 0,
                  "target_riichi": None, "temporary_furiten": None,
                  "needs_review": True, "review_note": "从完整复盘核对公开状态、对手手牌、副露与振听后删除 needs_review"})
output = args.output or data_root() / "annotations" / f"{args.session_id}.jsonl"
output.parent.mkdir(parents=True, exist_ok=True)
game = {"game_id": args.session_id, "mode": mode,
        "source": {"provenance": "self_recorded", "description": "从本地复盘观察生成；待人工核验"},
        "turns": turns}
output.write_text(json.dumps(game, ensure_ascii=False, indent=None) + "\n", encoding="utf-8")
print(f"Review template: {output}; post-discard candidates: {len(turns)}. Unreviewed rows are rejected by training.")
