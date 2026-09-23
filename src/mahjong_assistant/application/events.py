"""Conservative event reconstruction shared by live capture and video replay."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import uuid

from ..domain.models import Board
from ..vision.recognizer import Observation


@dataclass(frozen=True)
class GameEvent:
    session_id: str
    sequence: int
    round_index: int
    kind: str
    seat: str | None
    tile: str | None
    source: str
    observed_at: str
    confidence: str
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class EventTracker:
    """Never invent an event from a missing or reordered river tile."""

    def __init__(self, mode: int):
        self.mode = mode
        self.session_id = uuid.uuid4().hex
        self.events: list[GameEvent] = []
        self.round_index = 0
        self.ready = False
        self.reason = "等待完整牌桌与新一局"
        self._started = False
        self._joined_midround = False
        self._rivers: dict[str, tuple[str, ...]] = {}
        self._last_hand: tuple[str, ...] = ()
        self._last_signature = None
        self._stable_runs = 0

    def _emit(self, kind: str, seat: str | None, tile: str | None,
              source: str, confidence: str = "observed", note: str = "") -> GameEvent:
        event = GameEvent(self.session_id, len(self.events) + 1, self.round_index, kind,
                          seat, tile, source, datetime.now(timezone.utc).isoformat(), confidence, note)
        self.events.append(event)
        return event

    def _invalid(self, board: Board, observation: Observation) -> str | None:
        if not board.auto_hand_ready and not board.hand_confirmed:
            return "手牌未稳定或不完整"
        if any(not (opponent.auto_observed or opponent.confirmed) for opponent in board.opponents):
            return "对手牌河尚未稳定"
        seats = ("hand", "self", "top", "right") if self.mode == 3 else ("hand", "self", "left", "top", "right")
        if any(d.tile == "?" for seat in seats for d in observation.for_seat(seat)):
            return "牌名未识别完整"
        if any("冲突" in warning for warning in board.warnings):
            return "可见牌数或模式冲突"
        return None

    def observe(self, board: Board, observation: Observation, *, single_frame: bool = False) -> list[GameEvent]:
        reason = self._invalid(board, observation)
        if reason:
            self.ready, self.reason = False, reason
            self._stable_runs = 0
            return []
        seats = ("self", "top", "right") if self.mode == 3 else ("self", "left", "top", "right")
        rivers = {seat: tuple(d.tile for d in observation.for_seat(seat)) for seat in seats}
        hand = tuple(d.tile for d in observation.for_seat("hand"))
        signature = (hand, tuple((seat, rivers[seat]) for seat in seats))
        self._stable_runs = self._stable_runs + 1 if signature == self._last_signature else 1
        self._last_signature = signature
        if self._stable_runs < 2 and not single_frame:
            self.ready, self.reason = False, "等待连续稳定画面"
            return []
        source = observation.source
        emitted: list[GameEvent] = []
        all_empty = all(not river for river in rivers.values())
        if not self._started:
            self._started = True
            self.round_index = 1
            self._joined_midround = not all_empty
            self.ready = all_empty
            self.reason = "可跟踪" if all_empty else "从牌局中途接入，等待下一局"
            self._rivers, self._last_hand = rivers, hand
            emitted.append(self._emit("round_start" if all_empty else "midround_join", None, None, source,
                                      "observed" if all_empty else "unknown"))
            return emitted
        if all_empty and any(self._rivers.values()) and hand != self._last_hand and len(hand) in (13, 14):
            self.round_index += 1
            self._joined_midround = False
            self.ready, self.reason = True, "可跟踪"
            self._rivers, self._last_hand = rivers, hand
            emitted.append(self._emit("round_start", None, None, source))
            return emitted
        for seat in seats:
            old, new = self._rivers.get(seat, ()), rivers[seat]
            if new == old:
                continue
            if len(new) == len(old) + 1 and new[:len(old)] == old:
                tile = new[-1]
                emitted.append(self._emit("discard", seat, tile, source))
                candidates = observation.for_seat(seat)
                if candidates and candidates[-1].sideways:
                    emitted.append(self._emit("riichi_candidate", seat, tile, source, "candidate",
                                              "横置舍牌；尚未确认立直"))
            elif len(new) + 1 == len(old) and _one_removed(old, new):
                emitted.append(self._emit("river_removed_candidate", seat, None, source, "candidate",
                                          "可能被副露取走；尚未确认"))
                self.ready, self.reason = False, "牌河减少，需核对副露或画面"
            else:
                emitted.append(self._emit("tracking_gap", seat, None, source, "unknown",
                                          "牌河变化无法还原为单次出牌"))
                self.ready, self.reason = False, "事件缺失或牌河顺序改变"
        self._rivers, self._last_hand = rivers, hand
        if self._joined_midround:
            self.ready, self.reason = False, "从牌局中途接入，等待下一局"
        elif self.ready:
            self.reason = "可跟踪"
        return emitted

    def confirm_call(self, seat: str, source: str) -> GameEvent:
        self.ready, self.reason = False, "副露已人工确认，等待完整事件校验"
        return self._emit("call_confirmed", seat, None, source, "confirmed")

    def confirm_riichi(self, seat: str, source: str) -> GameEvent:
        return self._emit("riichi_confirmed", seat, None, source, "confirmed")


def _one_removed(old: tuple[str, ...], new: tuple[str, ...]) -> bool:
    return any(old[:index] + old[index + 1:] == new for index in range(len(old)))
