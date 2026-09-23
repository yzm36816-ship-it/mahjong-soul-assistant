from dataclasses import dataclass, field

SEAT_NAMES = {"left": "上家", "top": "对家", "right": "下家"}


def seat_name(seat: str, mode: int = 4) -> str:
    return "上家（上方）" if mode == 3 and seat == "top" else SEAT_NAMES[seat]


@dataclass
class Opponent:
    seat: str
    discards: list[str] = field(default_factory=list)
    melds: int = 0
    riichi: bool = False
    confirmed: bool = False
    unknown_count: int = 0
    auto_observed: bool = False
    riichi_candidate: bool = False


@dataclass
class Board:
    mode: int = 4
    hand: list[str] = field(default_factory=list)
    opponents: list[Opponent] = field(default_factory=list)
    source: str = "尚未读取"
    hand_confirmed: bool = False
    complete: bool = False
    warnings: list[str] = field(default_factory=list)
    auto_hand_ready: bool = False
    visible_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class TileRisk:
    tile: str
    level: str
    score: int
    reason: str


@dataclass
class Assessment:
    seat: str
    status: str
    detail: str
    risks: list[TileRisk] = field(default_factory=list)
    waits: list["WaitCandidate"] = field(default_factory=list)


@dataclass
class WaitCandidate:
    tile: str
    shapes: list[str]
