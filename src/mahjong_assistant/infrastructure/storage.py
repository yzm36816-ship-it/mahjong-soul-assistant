import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from .paths import data_root


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class History:
    def __init__(self, path: Path | None = None):
        self.path = path or data_root() / "sessions" / "history.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, at TEXT, payload TEXT)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(snapshots)")}
            if "session_id" not in columns:
                db.execute("ALTER TABLE snapshots ADD COLUMN session_id TEXT")
            db.execute("CREATE TABLE IF NOT EXISTS events (session_id TEXT NOT NULL, sequence INTEGER NOT NULL, round_index INTEGER NOT NULL, at TEXT NOT NULL, kind TEXT NOT NULL, seat TEXT, tile TEXT, source TEXT NOT NULL, confidence TEXT NOT NULL, note TEXT NOT NULL, PRIMARY KEY (session_id, sequence))")
            db.execute("CREATE INDEX IF NOT EXISTS events_at ON events(at)")
            db.execute("CREATE TABLE IF NOT EXISTS corrections (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, sequence INTEGER NOT NULL, field TEXT NOT NULL, corrected_value TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL)")

    def record(self, board, session_id: str | None = None):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO snapshots (at, payload, session_id) VALUES (?, ?, ?)",
                       (datetime.now(timezone.utc).isoformat(), json.dumps(asdict(board), ensure_ascii=False), session_id))

    def record_events(self, events):
        with sqlite3.connect(self.path) as db:
            db.executemany("INSERT OR IGNORE INTO events (session_id, sequence, round_index, at, kind, seat, tile, source, confidence, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(event.session_id, event.sequence, event.round_index, event.observed_at,
                  event.kind, event.seat, event.tile, event.source, event.confidence, event.note)
                 for event in events])

    def sessions(self):
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT session_id, MIN(at), MAX(at), COUNT(*), MAX(round_index) FROM events GROUP BY session_id ORDER BY MAX(at) DESC").fetchall()
        return [{"id": row[0], "started_at": row[1], "updated_at": row[2],
                 "event_count": row[3], "round_count": row[4]} for row in rows]

    def events(self, session_id: str):
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT sequence, round_index, kind, seat, tile, source, at, confidence, note FROM events WHERE session_id=? ORDER BY sequence", (session_id,)).fetchall()
        return [{"session_id": session_id, "sequence": row[0], "round_index": row[1],
                 "kind": row[2], "seat": row[3], "tile": row[4], "source": row[5],
                 "observed_at": row[6], "confidence": row[7], "note": row[8]} for row in rows]

    def snapshots(self, session_id: str):
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT id, at, payload FROM snapshots WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
        return [{"id": row[0], "at": row[1], "board": json.loads(row[2])} for row in rows]

    def add_correction(self, session_id: str, sequence: int, field: str, value: str, note: str = ""):
        if field not in {"tile", "kind", "seat", "note"}:
            raise ValueError("invalid correction field")
        if not self.events(session_id) or sequence not in {event["sequence"] for event in self.events(session_id)}:
            raise ValueError("unknown event")
        with sqlite3.connect(self.path) as db:
            cursor = db.execute("INSERT INTO corrections (session_id, sequence, field, corrected_value, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                (session_id, sequence, field, value[:200], note[:500], datetime.now(timezone.utc).isoformat()))
            return cursor.lastrowid

    def corrections(self, session_id: str | None = None):
        with sqlite3.connect(self.path) as db:
            if session_id is None:
                rows = db.execute("SELECT id, session_id, sequence, field, corrected_value, note, created_at FROM corrections ORDER BY id DESC").fetchall()
            else:
                rows = db.execute("SELECT id, session_id, sequence, field, corrected_value, note, created_at FROM corrections WHERE session_id=? ORDER BY id DESC", (session_id,)).fetchall()
        return [{"id": row[0], "session_id": row[1], "sequence": row[2], "field": row[3],
                 "corrected_value": row[4], "note": row[5], "created_at": row[6]} for row in rows]

    def export(self, path: Path):
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT at, payload FROM snapshots ORDER BY id").fetchall()
        save_json(path, [{"at": at, "board": json.loads(payload)} for at, payload in rows])
