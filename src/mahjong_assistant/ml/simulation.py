"""Turn complete RiichiEnv self-play logs into labelled, synthetic replay games.

The simulator's omniscient log is used only here. Its concealed hands become
labels; the model feature builder still receives public state and our own hand.
"""

import json
import random

from ..domain.tiles import normalize


HONORS = {letter: f"{index}z" for index, letter in enumerate("ESWNPFC", 1)}


def tile_name(value: str) -> str:
    if value in HONORS:
        return HONORS[value]
    if len(value) == 3 and value[:2] in ("5m", "5p", "5s") and value[2] == "r":
        return "0" + value[1]
    return normalize(value)


def _remove(hand: list[str], tile: str) -> None:
    if tile in hand:
        hand.remove(tile)
        return
    for index, value in enumerate(hand):
        if normalize(value) == normalize(tile):
            hand.pop(index)
            return
    raise ValueError(f"simulator log removes absent tile: {tile}")


def greedy_action(observation, mode: int, rng: random.Random):
    """A reproducible, deliberately simple self-play policy with useful labels."""
    from riichienv import calculate_shanten, calculate_shanten_3p

    actions = observation.legal_actions()
    by_kind: dict[str, list] = {}
    for action in actions:
        by_kind.setdefault(json.loads(action.to_mjai())["type"], []).append(action)
    if by_kind.get("hora"):
        return by_kind["hora"][0]
    # Keep some tenpai hands undeclared, or the public riichi flag becomes an
    # almost perfect label and the tenpai task is vacuous in self-play.
    if by_kind.get("reach") and rng.random() < .35:
        return by_kind["reach"][0]
    if by_kind.get("dahai"):
        shanten = calculate_shanten_3p if mode == 3 else calculate_shanten
        scored = []
        for action in by_kind["dahai"]:
            remainder = observation.hand.copy()
            remainder.remove(action.tile)
            scored.append((shanten(remainder), rng.random(), action))
        return min(scored, key=lambda row: row[:2])[2]
    if by_kind.get("none"):
        return by_kind["none"][0]
    raise ValueError(f"self-play policy cannot handle {sorted(by_kind)}")


def simulate_game(mode: int, seed: int, game_length: str = "east") -> list[dict]:
    from riichienv import GameRule, RiichiEnv

    if mode not in (3, 4) or game_length not in ("single", "east", "half"):
        raise ValueError("unsupported simulation mode or length")
    env = RiichiEnv(game_mode=f"{mode}p-red-{game_length}", rule=GameRule.default_mjsoul())
    observations = env.reset(seed=seed)
    rng = random.Random((mode << 32) | seed)
    while not env.done():
        observations = env.step({seat: greedy_action(observation, mode, rng)
                                 for seat, observation in observations.items()})
    return env.mjai_log


def game_from_log(events: list[dict], mode: int, game_id: str, *,
                  simulator_version: str = "unknown") -> dict:
    """Build one training record per opponent discard from an omniscient log.

    This converter intentionally accepts only closed-hand logs from our policy.
    Calls or north extraction require a separate verified reconstruction path.
    """
    seats = ("self", "right", "top", "left")[:mode]
    hands: list[list[str]] = []
    rivers: list[list[str]] = []
    history: list[list[str]] = []
    riichi: list[bool] = []
    turns: list[dict] = []
    last_discard: int | None = None
    for event in events:
        kind = event["type"]
        if kind == "start_kyoku":
            if len(event["tehais"]) != mode:
                raise ValueError("simulator player count differs from requested mode")
            hands = [[tile_name(tile) for tile in seat] for seat in event["tehais"]]
            rivers = [[] for _ in range(mode)]
            history = [[] for _ in range(mode)]
            riichi = [False] * mode
            last_discard = None
        elif kind == "tsumo":
            hands[event["actor"]].append(tile_name(event["pai"]))
        elif kind == "dahai":
            actor = event["actor"]
            tile = tile_name(event["pai"])
            _remove(hands[actor], tile)
            rivers[actor].append(tile)
            history[actor].append(tile)
            last_discard = actor
            if actor != 0:
                if len(hands[0]) != 13 or len(hands[actor]) != 13:
                    raise ValueError("unexpected hand size after opponent discard")
                turns.append({
                    "turn": len(turns) + 1,
                    "event_type": "discard",
                    "observer_hand": hands[0].copy(),
                    "rivers": {seat: river.copy() for seat, river in zip(seats, rivers)},
                    "target_seat": seats[actor],
                    "target_discard_history": history[actor].copy(),
                    "target_concealed": hands[actor].copy(),
                    "target_meld_count": 0,
                    "target_riichi": riichi[actor],
                    # The generating policy always takes an available ron.
                    "temporary_furiten": False,
                })
        elif kind == "reach_accepted":
            actor = event["actor"]
            riichi[actor] = True
            if actor != 0 and last_discard == actor and turns:
                turns[-1]["target_riichi"] = True
        elif kind in ("chi", "pon", "daiminkan", "ankan", "kakan", "kita"):
            raise ValueError(f"unsupported self-play call: {kind}")
        elif kind in ("start_game", "reach", "dora", "hora", "ryukyoku", "end_kyoku", "end_game"):
            pass
        else:
            raise ValueError(f"unrecognized simulator event: {kind}")
    if not turns:
        raise ValueError("self-play game has no opponent discards")
    return {
        "game_id": game_id,
        "mode": mode,
        "source": {"provenance": "synthetic_demo",
                   "description": f"RiichiEnv {simulator_version} self-play, MJSoul rule preset, greedy shanten policy; no human game records"},
        "turns": turns,
    }
