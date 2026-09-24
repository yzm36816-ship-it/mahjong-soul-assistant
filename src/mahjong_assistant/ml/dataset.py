"""Permission-aware replay examples. Private hands are labels, never features."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

from ..domain.hand_solver import structural_waits, riichi_ron_waits, legal_tiles
from ..domain.tiles import ALL_TILES, normalize

TILE_INDEX = {tile: index for index, tile in enumerate(ALL_TILES)}
FEATURE_SIZE = 34 * 4 + 8 * 34 + 2
ALLOWED_PROVENANCE = {"self_recorded", "permission_granted", "explicit_open_license", "synthetic_demo"}


@dataclass(frozen=True)
class PublicPosition:
    mode: int
    own_hand: tuple[str, ...]
    rivers: dict[str, tuple[str, ...]]
    target_seat: str
    riichi_confirmed: bool
    target_history: tuple[str, ...] | None = None


@dataclass(frozen=True)
class TrainingExample:
    game_id: str
    turn: int
    public: PublicPosition
    tenpai: bool
    waits: tuple[str, ...] | None
    ron_waits: tuple[str, ...] | None


def features(public: PublicPosition) -> np.ndarray:
    """Only values also available from a verified live observation are used."""
    if public.mode not in (3, 4) or public.target_seat not in public.rivers:
        raise ValueError("invalid public position")
    allowed = set(legal_tiles(public.mode))
    all_visible = tuple(public.own_hand) + tuple(tile for river in public.rivers.values() for tile in river)
    if any(normalize(tile) not in allowed for tile in all_visible):
        raise ValueError("public position contains an invalid tile")
    target = public.target_history if public.target_history is not None else public.rivers[public.target_seat]
    if any(normalize(tile) not in allowed for tile in target):
        raise ValueError("discard history contains an invalid tile")
    other = tuple(tile for seat, river in public.rivers.items() if seat != public.target_seat for tile in river)
    vector = np.zeros(FEATURE_SIZE, dtype=np.float32)
    for offset, tiles in ((0, public.own_hand), (34, all_visible), (68, target), (102, other)):
        for tile in tiles:
            vector[offset + TILE_INDEX[normalize(tile)]] += .25
    for index, tile in enumerate(target[-8:]):
        vector[136 + (8 - len(target[-8:]) + index) * 34 + TILE_INDEX[normalize(tile)]] = 1
    vector[-2] = min(len(target), 24) / 24
    vector[-1] = 1.0 if public.riichi_confirmed else 0.0
    return vector


def example_from_turn(game_id: str, mode: int, turn: dict) -> TrainingExample:
    if turn.get("needs_review"):
        raise ValueError("turn still requires human replay review")
    required = {"turn", "event_type", "observer_hand", "rivers", "target_seat", "target_discard_history", "target_concealed", "target_meld_count", "target_riichi"}
    if not required.issubset(turn):
        raise ValueError(f"missing turn fields: {sorted(required - turn.keys())}")
    rivers = {seat: tuple(tiles) for seat, tiles in turn["rivers"].items()}
    target_seat = turn["target_seat"]
    if not isinstance(turn["target_riichi"], bool):
        raise ValueError("target_riichi must be confirmed true or false")
    if turn.get("temporary_furiten") not in (None, True, False):
        raise ValueError("temporary_furiten must be true, false, or null")
    if turn["event_type"] != "discard":
        raise ValueError("training snapshot must follow the target's discard")
    if target_seat not in rivers:
        raise ValueError("target seat missing from rivers")
    history = tuple(turn["target_discard_history"])
    if not history or history[-1] != rivers[target_seat][-1]:
        raise ValueError("target discard history must end at the observed discard")
    public = PublicPosition(mode, tuple(turn["observer_hand"]), rivers, target_seat,
                            bool(turn["target_riichi"]), history)
    features(public)  # Validate without touching the hidden-hand label.
    concealed = list(turn["target_concealed"])
    if not 1 <= len(public.own_hand) <= 14 or len(public.own_hand) % 3 == 0:
        raise ValueError("observer hand has an impossible tile count")
    from collections import Counter
    counts = Counter(normalize(tile) for tile in [*public.own_hand, *concealed,
                    *(tile for river in rivers.values() for tile in river)])
    if any(count > 4 for count in counts.values()):
        raise ValueError("public and private tiles exceed four copies")
    meld_count = int(turn["target_meld_count"])
    waits = structural_waits(concealed, mode, meld_count)
    ron = None
    if public.riichi_confirmed and turn.get("temporary_furiten") is not None:
        ron = set() if turn["temporary_furiten"] else riichi_ron_waits(concealed, list(history), mode)
    return TrainingExample(game_id, int(turn["turn"]), public, bool(waits),
                           tuple(sorted(waits)) if public.riichi_confirmed else None,
                           tuple(sorted(ron)) if ron is not None else None)


def load_games(path: Path) -> list[TrainingExample]:
    """Read JSONL games; reject data without an explicit usable provenance."""
    examples = []
    seen = set()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            game = json.loads(line)
            game_id = game["game_id"]
            if game_id in seen:
                raise ValueError(f"duplicate game_id at line {line_number}")
            seen.add(game_id)
            source = game.get("source", {})
            if source.get("provenance") not in ALLOWED_PROVENANCE or not source.get("description"):
                raise ValueError(f"unverified source at line {line_number}")
            if source["provenance"] == "explicit_open_license" and not source.get("license_url"):
                raise ValueError(f"license URL required at line {line_number}")
            if source["provenance"] == "permission_granted" and not source.get("permission_ref"):
                raise ValueError(f"permission reference required at line {line_number}")
            mode = game["mode"]
            for turn in game["turns"]:
                examples.append(example_from_turn(game_id, mode, turn))
    return examples


def source_summary(path: Path, mode: int | None = None) -> dict:
    counts: dict[str, int] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                game = json.loads(line)
                if mode is not None and game["mode"] != mode:
                    continue
                kind = game["source"]["provenance"]
                counts[kind] = counts.get(kind, 0) + 1
    return counts


def split_for_game(game_id: str) -> str:
    bucket = int(hashlib.sha256(game_id.encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "validation" if bucket < 85 else "test"


def target_vectors(example: TrainingExample):
    waits = np.zeros(34, dtype=np.float32)
    ron = np.zeros(34, dtype=np.float32)
    if example.waits is not None:
        for tile in example.waits:
            waits[TILE_INDEX[tile]] = 1
    if example.ron_waits is not None:
        for tile in example.ron_waits:
            ron[TILE_INDEX[tile]] = 1
    return (float(example.tenpai), waits, ron,
            example.waits is not None, example.ron_waits is not None)
