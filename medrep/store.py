"""Reports and the clinician gate.

The gate is a state machine, not a flag: the only way to APPROVED is through
`approve`, which needs a named clinician, and the patient view returns nothing
for any other state. The clinician is a required step in the flow, not a
fallback.
"""
from __future__ import annotations

import os
import sqlite3

from .models import Report, Status

DB = os.environ.get("MEDREP_DB", "medrep.db")

ALLOWED = {
    Status.UPLOADED: {Status.EXTRACTED, Status.DRAFTED},
    Status.EXTRACTED: {Status.DRAFTED},
    Status.DRAFTED: {Status.APPROVED, Status.REJECTED, Status.DRAFTED},
    Status.APPROVED: set(),
    Status.REJECTED: set(),
}


class GateError(Exception):
    pass


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
    return conn


def save(report: Report) -> Report:
    conn = _conn()
    conn.execute("INSERT OR REPLACE INTO reports (id, body) VALUES (?, ?)", (report.id, report.model_dump_json()))
    conn.commit()
    return report


def get(report_id: str) -> Report | None:
    row = _conn().execute("SELECT body FROM reports WHERE id = ?", (report_id,)).fetchone()
    return Report.model_validate_json(row[0]) if row else None


def all_reports(status: Status | None = None) -> list[Report]:
    reports = [Report.model_validate_json(r[0]) for r in _conn().execute("SELECT body FROM reports")]
    return [r for r in reports if status is None or r.status == status]


def transition(report: Report, new: Status, **changes) -> Report:
    if new not in ALLOWED[report.status]:
        raise GateError(f"{report.id}: {report.status.value} -> {new.value} is not allowed")
    return save(report.model_copy(update={"status": new, **changes}))


def approve(report_id: str, clinician: str, final_text: str) -> Report:
    from . import audit

    if not clinician.strip():
        raise GateError("approval needs a named clinician")
    if not final_text.strip():
        raise GateError("approval needs the text the patient will see")
    report = get(report_id)
    out = transition(report, Status.APPROVED, reviewer=clinician, final=final_text)
    audit.log(report_id, clinician, "approved", edits=audit.edits(report.draft, final_text))
    return out


def reject(report_id: str, clinician: str, reason: str = "") -> Report:
    from . import audit

    out = transition(get(report_id), Status.REJECTED, reviewer=clinician)
    audit.log(report_id, clinician, "rejected", reason=reason)
    return out


def patient_view(report_id: str) -> str | None:
    """None unless a clinician approved it. There is no other path to the patient."""
    from . import audit

    r = get(report_id)
    if r and r.status == Status.APPROVED:
        audit.log(report_id, "patient", "viewed")
        return r.final
    return None
