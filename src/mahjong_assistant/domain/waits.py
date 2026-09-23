"""Necessary local wait-shape constraints, NOT a probability model or full hand solver."""
from .models import Board, Opponent, WaitCandidate
from .tiles import ALL_TILES, normalize, label


def possible_ron_waits(board: Board, opponent: Opponent) -> list[WaitCandidate]:
    if not (opponent.confirmed or opponent.auto_observed):
        return []
    if not (opponent.riichi or opponent.riichi_candidate):
        return []
    available = [t for t in ALL_TILES if board.mode != 3 or t[1] != "m" or t[0] in "19"]
    remaining = {t: max(0, 4 - board.visible_counts.get(t, 0)) for t in ALL_TILES}
    river = {normalize(t) for t in opponent.discards}
    orphans = {"1m", "9m", "1p", "9p", "1s", "9s", *(f"{n}z" for n in range(1, 8))}
    result = []
    for tile in available:
        if tile in river:
            continue  # Own-discard furiten excludes ron, not tsumo.
        n, suit = int(tile[0]), tile[1]
        shapes = []
        if remaining[tile] >= 1:
            shapes.append("单骑 / 七对子")
        if remaining[tile] >= 2 and any(t != tile and t not in river and remaining[t] >= 2 for t in available):
            shapes.append("双碰")
        if suit != "z" and not (board.mode == 3 and suit == "m"):
            if 2 <= n <= 8 and all(remaining[f"{v}{suit}"] > 0 for v in (n-1, n+1)):
                shapes.append(f"嵌张（{label(str(n-1)+suit)}、{label(str(n+1)+suit)}）")
            edge = (1, 2) if n == 3 else (8, 9) if n == 7 else None
            if edge and all(remaining[f"{v}{suit}"] > 0 for v in edge):
                shapes.append("边张")
            for lower in (n, n-3):
                if 1 <= lower <= 6:
                    waits = {f"{lower}{suit}", f"{lower+3}{suit}"}
                    if not waits.intersection(river) and all(remaining[f"{v}{suit}"] > 0 for v in (lower+1, lower+2)):
                        shapes.append(f"两面（{label(str(lower)+suit)} / {label(str(lower+3)+suit)}）")
        if tile in orphans and opponent.melds == 0:
            other = orphans - {tile}
            if all(remaining[t] >= 1 for t in other) and any(remaining[t] >= 2 for t in other):
                shapes.append("国士单面")
            if not river.intersection(orphans) and all(remaining[t] >= 1 for t in orphans):
                shapes.append("国士十三面")
        if shapes:
            result.append(WaitCandidate(tile, shapes))
    return result
