"""Exact structural winning-hand checks for labelled, fully known hands.

This module never infers an opponent's hidden tiles from live pixels. It is used
only for replay ground truth and deterministic rule tests.
"""
from collections import Counter
from functools import lru_cache

from .tiles import ALL_TILES, normalize

ORPHANS = frozenset({"1m", "9m", "1p", "9p", "1s", "9s", *(f"{n}z" for n in range(1, 8))})
TILE_INDEX = {tile: index for index, tile in enumerate(ALL_TILES)}


def legal_tiles(mode: int) -> tuple[str, ...]:
    if mode not in (3, 4):
        raise ValueError("mode must be 3 or 4")
    return tuple(tile for tile in ALL_TILES if mode == 4 or tile[1] != "m" or tile[0] in "19")


def validate_concealed(tiles: list[str], mode: int, meld_count: int) -> tuple[int, ...]:
    if not 0 <= meld_count <= 4:
        raise ValueError("meld_count must be between 0 and 4")
    allowed = set(legal_tiles(mode))
    normalized = [normalize(tile) for tile in tiles]
    if any(tile not in allowed for tile in normalized):
        raise ValueError("tile not present in this mode")
    if len(normalized) != 13 - 3 * meld_count:
        raise ValueError("expected a post-discard concealed hand")
    counts = Counter(normalized)
    if any(count > 4 for count in counts.values()):
        raise ValueError("more than four copies of a tile")
    return tuple(counts[tile] for tile in ALL_TILES)


@lru_cache(maxsize=200_000)
def _sets_only(counts: tuple[int, ...]) -> bool:
    try:
        index = next(i for i, count in enumerate(counts) if count)
    except StopIteration:
        return True
    if counts[index] >= 3:
        next_counts = list(counts)
        next_counts[index] -= 3
        if _sets_only(tuple(next_counts)):
            return True
    tile = ALL_TILES[index]
    if tile[1] != "z" and int(tile[0]) <= 7 and counts[index + 1] and counts[index + 2]:
        next_counts = list(counts)
        for offset in (0, 1, 2):
            next_counts[index + offset] -= 1
        if _sets_only(tuple(next_counts)):
            return True
    return False


def is_complete(counts: tuple[int, ...], meld_count: int) -> bool:
    if sum(counts) != 14 - 3 * meld_count:
        return False
    if meld_count == 0:
        pairs = sum(count == 2 for count in counts)
        if pairs == 7:
            return True
        orphan_counts = [counts[TILE_INDEX[tile]] for tile in ORPHANS]
        if all(orphan_counts) and sum(orphan_counts) == 14:
            return True
    for index, count in enumerate(counts):
        if count >= 2:
            next_counts = list(counts)
            next_counts[index] -= 2
            if _sets_only(tuple(next_counts)):
                return True
    return False


def structural_waits(tiles: list[str], mode: int, meld_count: int = 0) -> set[str]:
    """Return every tile that completes a known post-discard hand."""
    counts = validate_concealed(tiles, mode, meld_count)
    result = set()
    for tile in legal_tiles(mode):
        index = TILE_INDEX[tile]
        if counts[index] >= 4:
            continue
        next_counts = list(counts)
        next_counts[index] += 1
        if is_complete(tuple(next_counts), meld_count):
            result.add(tile)
    return result


def riichi_ron_waits(tiles: list[str], own_discards: list[str], mode: int) -> set[str]:
    """Permanent furiten excludes every ron wait; temporary furiten is unknown."""
    waits = structural_waits(tiles, mode)
    return set() if waits.intersection(normalize(tile) for tile in own_discards) else waits
