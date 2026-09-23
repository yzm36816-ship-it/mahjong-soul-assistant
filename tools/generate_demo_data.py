"""Generate public synthetic pipeline fixtures; NEVER qualify for live promotion."""
from collections import Counter
import json
from pathlib import Path
import random

from mahjong_assistant.domain.hand_solver import legal_tiles, structural_waits

random.seed(1729)
output = Path("examples/synthetic_replays.jsonl")
output.parent.mkdir(parents=True, exist_ok=True)


def deal(mode, positive):
    allowed = legal_tiles(mode)
    deck = [tile for tile in allowed for _ in range(4)]
    if positive:
        concealed = "1p 2p 3p 4p 5p 6p 7p 8p 9p 1s 2s 3s 7z".split()
    else:
        while True:
            random.shuffle(deck)
            concealed = deck[:13]
            if not structural_waits(concealed, mode):
                break
    for tile in concealed:
        deck.remove(tile)
    random.shuffle(deck)
    own = deck[:13]
    deck = deck[13:]
    return concealed, own, deck


with output.open("w", encoding="utf-8") as stream:
    for mode in (3, 4):
        for game_index in range(80):
            turns = []
            for turn_index in range(10):
                positive = (game_index + turn_index) % 2 == 0
                concealed, own, deck = deal(mode, positive)
                riichi = positive and turn_index % 3 != 0
                seats = ("self", "top", "right") if mode == 3 else ("self", "left", "top", "right")
                rivers = {seat: [] for seat in seats}
                target_count = turn_index + 1
                for index in range(target_count):
                    rivers["top"].append(deck.pop())
                for seat in seats:
                    if seat != "top":
                        for _ in range(min(turn_index, 5)):
                            rivers[seat].append(deck.pop())
                turns.append({"turn": turn_index + 1, "event_type": "discard",
                              "observer_hand": own, "rivers": rivers, "target_seat": "top",
                              "target_discard_history": rivers["top"],
                              "target_concealed": concealed, "target_meld_count": 0,
                              "target_riichi": riichi,
                              "temporary_furiten": False if riichi else None})
            game = {"game_id": f"synthetic-{mode}p-{game_index:03d}", "mode": mode,
                    "source": {"provenance": "synthetic_demo", "description": "Deterministic non-game fixture"},
                    "turns": turns}
            stream.write(json.dumps(game, ensure_ascii=False) + "\n")
print(f"Wrote {output} — synthetic only, not evidence of real-world accuracy")
