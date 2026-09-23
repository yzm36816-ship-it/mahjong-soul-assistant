"""Single safety gate for both desktop and replay model inference."""
from ..ml.dataset import PublicPosition


def predictions_for_session(session, registry) -> dict:
    board = session.board
    observation = session.observation
    if not session.tracker.ready or observation is None or not board.auto_hand_ready:
        return {}
    if any(d.tile == "?" for d in observation.detections):
        return {}
    seats = ("self", "top", "right") if board.mode == 3 else ("self", "left", "top", "right")
    rivers = {seat: tuple(d.tile for d in observation.for_seat(seat)) for seat in seats}
    result = {}
    for opponent in board.opponents:
        try:
            history = tuple(event.tile for event in session.tracker.events
                            if event.round_index == session.tracker.round_index
                            and event.kind == "discard" and event.seat == opponent.seat and event.tile)
            public = PublicPosition(board.mode, tuple(board.hand), rivers, opponent.seat,
                                    opponent.confirmed and opponent.riichi, history)
            prediction = registry.predict(public)
        except (ValueError, KeyError, ImportError, RuntimeError):
            prediction = None
        if prediction is not None:
            result[opponent.seat] = prediction
    return result
