"""Tile identities and explicit text input; red fives share a structural identity."""
from collections import Counter
import re

ALL_TILES = tuple(f"{n}{s}" for s in "mps" for n in range(1, 10)) + tuple(f"{n}z" for n in range(1, 8))
HONORS = {"1z": "东", "2z": "南", "3z": "西", "4z": "北", "5z": "白", "6z": "发", "7z": "中"}


def normalize(tile: str) -> str:
    if tile in ("0m", "0p", "0s"):
        return "5" + tile[1]
    if tile not in ALL_TILES:
        raise ValueError(f"无效牌编码：{tile}")
    return tile


def label(tile: str) -> str:
    if tile == "?":
        return "?"
    if tile in HONORS:
        return HONORS[tile]
    return ("赤5" if tile[0] == "0" else tile[0]) + {"m": "万", "p": "筒", "s": "索"}[tile[1]]


def parse_tiles(text: str, mode: int = 4) -> list[str]:
    cleaned = re.sub(r"[\s,，;；]+", "", text.lower())
    for tile, name in HONORS.items():
        cleaned = cleaned.replace(name, tile)
    cleaned = cleaned.replace("發", "6z").replace("東", "1z")
    groups = re.findall(r"([0-9]+)([mpsz])", cleaned)
    if "".join(a + b for a, b in groups) != cleaned:
        raise ValueError("请输入如 123m456p789s东白；m=万 p=筒 s=索 z=字牌。")
    tiles = [n + suit for digits, suit in groups for n in digits]
    for tile in tiles:
        normalized = normalize(tile)
        if mode == 3 and normalized[1] == "m" and normalized[0] not in "19":
            raise ValueError("三麻不使用二至八万。")
    if any(n > 4 for n in Counter(normalize(t) for t in tiles).values()):
        raise ValueError("同一种牌（含赤五）不能超过四张。")
    return tiles

