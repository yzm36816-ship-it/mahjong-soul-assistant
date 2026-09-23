"""Session boundaries and explicit confirmation; never guess around missing tiles."""
from collections import Counter
from ..domain.models import Board, Opponent
from ..domain.tiles import normalize
from ..vision.recognizer import Observation
from .events import EventTracker


class Session:
    def __init__(self, mode=4):
        self.mode = mode
        self.reset()

    def reset(self):
        self.board = Board(mode=self.mode)
        self.observation = None
        self._confirmed = {}
        self._last_signature = None
        self.changes = 0
        self._runs = {}
        self.frames = 0
        self.tracker = EventTracker(self.mode)
        self.recent_events = []

    def update(self, observation: Observation, require_stability=True):
        self.observation = observation
        self.frames += 1
        stable = {}
        for seat in ("hand", "left", "top", "right"):
            signature = tuple(sorted((d.tile, d.sideways) for d in observation.for_seat(seat)))
            last, count = self._runs.get(seat, (None, 0))
            count = count + 1 if signature == last else 1
            self._runs[seat] = signature, count
            stable[seat] = count >= 2 or not require_stability
        hand_detections = observation.for_seat("hand")
        hand = [d.tile for d in hand_detections if d.tile != "?"]
        opponents = []
        warnings = []
        for seat in ("left", "top", "right"):
            if self.mode == 3 and seat == "left":
                continue
            tiles = observation.for_seat(seat)
            river = [d.tile for d in tiles if d.tile != "?"]
            signature = tuple(d.tile for d in tiles)
            previous = self._confirmed.get(seat)
            # Confirmation applies only to exactly this observed river.
            same = previous is not None and previous[0] == signature
            opponents.append(Opponent(seat, river, previous[1] if same else 0,
                                      previous[2] if same else False, same,
                                      sum(d.tile == "?" for d in tiles),
                                      stable[seat] and (not tiles or len(river) >= 1),
                                      stable[seat] and any(d.sideways for d in tiles)))
        hand_signature = tuple(d.tile for d in hand_detections)
        hand_confirmed = self._confirmed.get("hand") == hand_signature
        if not hand_detections:
            warnings.append("没有检测到手牌：请检查窗口、动画或识别区域。")
        elif len(hand_detections) > 14 or len(hand_detections) % 3 == 0:
            hand_confirmed = False
            warnings.append("检测到的手牌数量不符合稳定牌型，可能有动画、漏检或重叠；请等待并校对。")
        unknown = sum(d.tile == "?" for d in observation.detections)
        if unknown:
            warnings.append(f"{unknown} 张牌待校对；相似度不是识别正确率。")
        warnings.append("自动初判无需校对；横置牌仅提示疑似立直，风险等级不是等待概率。")
        if self.mode == 3:
            warnings.append("三麻使用上方和右侧两家区域；首次使用请按实际布局校准。")
        # Counting only currently visible rivers and own hand avoids double-counting called discards.
        visible = hand + [t for o in opponents for t in o.discards] + [d.tile for d in observation.for_seat("self") if d.tile != "?"]
        invalid = any(n > 4 for n in Counter(normalize(t) for t in visible).values())
        if self.mode == 3 and any(normalize(t) in {f"{n}m" for n in range(2, 9)} for t in visible):
            invalid = True
        if invalid:
            warnings.insert(0, "牌数或模式冲突：请校对，已暂停安全结论。")
            hand_confirmed = False
            for opponent in opponents:
                opponent.confirmed = False
                opponent.riichi = False
                opponent.auto_observed = False
                opponent.riichi_candidate = False
        # Automatic observations stay distinct from human-confirmed facts.
        valid_shape = 1 <= len(hand_detections) <= 14 and len(hand_detections) % 3 in (1, 2)
        auto_hand = stable["hand"] and valid_shape and len(hand) >= max(1, len(hand_detections) * .7) and not invalid
        if not valid_shape or len(hand) < 1:
            for opponent in opponents:
                opponent.auto_observed = False
                opponent.riichi_candidate = False
        if not auto_hand and not hand_confirmed and hand_detections and not invalid:
            warnings.insert(0, "正在等待稳定手牌画面；动画和不确定牌暂不用于风险排序。")
        self.board = Board(self.mode, hand, opponents, observation.source, hand_confirmed,
                           hand_confirmed and all(o.confirmed for o in opponents), warnings, auto_hand,
                           dict(Counter(normalize(t) for t in visible)))
        self.recent_events = self.tracker.observe(self.board, observation,
                                                  single_frame=not require_stability or all(stable.values()))
        signature = (hand_signature, tuple((o.seat, tuple(o.discards), o.unknown_count) for o in opponents))
        changed = signature != self._last_signature
        if changed:
            self.changes += 1
            self._last_signature = signature
        return changed

    def confirm(self, board: Board):
        previous = {o.seat: o for o in self.board.opponents}
        self.board = board
        board.visible_counts = dict(Counter(normalize(t) for t in board.hand + [t for o in board.opponents for t in o.discards]))
        self._confirmed = {"hand": tuple(board.hand)}
        for opponent in board.opponents:
            self._confirmed[opponent.seat] = (tuple(opponent.discards), opponent.melds, opponent.riichi)
            old = previous.get(opponent.seat)
            if old is not None and opponent.melds > old.melds:
                self.recent_events.append(self.tracker.confirm_call(opponent.seat, board.source))
            if opponent.riichi and (old is None or not old.riichi):
                self.recent_events.append(self.tracker.confirm_riichi(opponent.seat, board.source))
