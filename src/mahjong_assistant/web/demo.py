"""Synthetic public replay used when no private session has been captured."""
from datetime import datetime, timezone


def demo_events(mode: int) -> list[dict]:
    seats = ["self", "top", "right"] if mode == 3 else ["self", "left", "top", "right"]
    sequence = [("round_start", None, None, "observed"),
                ("discard", "self", "1p", "observed"),
                ("discard", "top", "9s", "observed"),
                ("discard", "right", "7z", "observed")]
    if mode == 4:
        sequence.append(("discard", "left", "2m", "observed"))
    sequence += [("discard", "top", "5p", "observed"),
                 ("riichi_candidate", "top", "5p", "candidate"),
                 ("tracking_gap", "right", None, "unknown")]
    return [{"session_id": f"demo-{mode}p", "sequence": index, "round_index": 1,
             "kind": kind, "seat": seat, "tile": tile, "source": "合成演示牌局",
             "observed_at": datetime(2026, 1, 1, 12, index, tzinfo=timezone.utc).isoformat(),
             "confidence": confidence, "note": "合成样例；不是实战或模型准确率证据" if confidence == "unknown" else ""}
            for index, (kind, seat, tile, confidence) in enumerate(sequence, 1)]


def demo_sessions() -> list[dict]:
    return [{"id": f"demo-{mode}p", "started_at": "2026-01-01T12:00:00+00:00",
             "updated_at": "2026-01-01T12:08:00+00:00", "event_count": len(demo_events(mode)),
             "round_count": 1, "mode": mode, "synthetic": True} for mode in (3, 4)]
