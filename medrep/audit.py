"""Append-only audit log: who changed what, when, from which state.
Draft vs final is kept so every clinician edit is visible later."""
from __future__ import annotations

import difflib
import json
import time

from .store import _conn


def _table():
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit (
        id INTEGER PRIMARY KEY, ts REAL NOT NULL, report_id TEXT NOT NULL,
        actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT)""")
    return conn


def log(report_id: str, actor: str, action: str, **detail) -> None:
    conn = _table()
    conn.execute("INSERT INTO audit (ts, report_id, actor, action, detail) VALUES (?,?,?,?,?)",
                 (time.time(), report_id, actor, action, json.dumps(detail, default=str)))
    conn.commit()


def edits(draft: str, final: str) -> str:
    return "\n".join(difflib.unified_diff(draft.splitlines(), final.splitlines(), "draft", "final", lineterm=""))


def history(report_id: str) -> list[dict]:
    rows = _table().execute("SELECT ts, actor, action, detail FROM audit WHERE report_id = ? ORDER BY ts",
                            (report_id,)).fetchall()
    return [{"ts": r[0], "actor": r[1], "action": r[2], **json.loads(r[3] or "{}")} for r in rows]
