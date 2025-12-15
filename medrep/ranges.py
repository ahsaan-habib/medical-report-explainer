"""Ground every value in a reference range with a named source.

Order of preference:
  1. the range printed on the report (it's the lab's own interval for its own method)
  2. the reference table, matched on test, unit, sex and age
  3. nothing -> flag "unknown"; the explanation says so instead of guessing

No unit conversion. A value in a unit the table doesn't have stays "unknown"
rather than risking a wrong conversion.
"""
from __future__ import annotations

import csv
import os
import re
from functools import lru_cache
from pathlib import Path

from .models import Patient, Result

TABLE = Path(os.environ.get("MEDREP_RANGES", Path(__file__).resolve().parents[1] / "data" / "reference_ranges.sample.csv"))


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@lru_cache(maxsize=1)
def _table() -> list[dict]:
    rows = []
    for r in csv.DictReader(TABLE.open()):
        r["names"] = {_key(r["test"]), *(_key(a) for a in r["aliases"].split("|") if a)}
        rows.append(r)
    return rows


def lookup(test: str, unit: str, patient: Patient) -> dict | None:
    k, u = _key(test), unit.strip().lower()
    for r in _table():
        if k not in r["names"] or r["unit"].lower() != u:
            continue
        if r["sex"] and patient.sex and r["sex"] != patient.sex:
            continue
        if r["sex"] and not patient.sex:
            continue      # sex-specific range and we don't know the sex: don't guess
        if patient.age is not None and not int(r["age_min"]) <= patient.age <= int(r["age_max"]):
            continue
        return r
    return None


def flag(r: Result) -> str:
    if r.ref_low is None and r.ref_high is None:
        return "unknown"
    if r.ref_low is not None and r.value < r.ref_low:
        return "low"
    if r.ref_high is not None and r.value > r.ref_high:
        return "high"
    return "normal"


def ground(results: list[Result], patient: Patient) -> list[Result]:
    out = []
    for r in results:
        if r.ref_source != "report":
            row = lookup(r.test, r.unit, patient)
            if row:
                r = r.model_copy(update={
                    "ref_low": float(row["low"]) if row["low"] else None,
                    "ref_high": float(row["high"]) if row["high"] else None,
                    "ref_source": f"table: {row['test']} ({row['unit']}{', ' + row['sex'] if row['sex'] else ''}) — {row['source']}",
                })
        out.append(r.model_copy(update={"flag": flag(r)}))
    return out
