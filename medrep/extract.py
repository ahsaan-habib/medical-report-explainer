"""Model-assisted extraction for the lines the table parser couldn't read.

The model is a transcriber here, not an interpreter. Every value it returns
must appear verbatim in the line it came from; anything else is dropped and
left for the clinician to read from the original.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from . import llm
from .models import Result
from .parse import NUM, to_float


class Row(BaseModel):
    line: int
    test: str
    value: float
    unit: str
    ref_low: float | None = None
    ref_high: float | None = None


class Rows(BaseModel):
    rows: list[Row]


SYSTEM = """Transcribe laboratory results from the numbered lines. For each line
that contains a test result, output the line number, test name, numeric value,
unit, and the reference range only if it is printed on that line.
Copy numbers exactly. Do not infer, convert or add reference ranges.
Skip lines that are not results (addresses, dates, comments). Reply as JSON."""


def extract(lines: list[str]) -> tuple[list[Result], list[str]]:
    if not lines:
        return [], []
    numbered = "\n".join(f"{i}: {l}" for i, l in enumerate(lines))
    raw = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": numbered}],
                   fmt=Rows.model_json_schema())
    try:
        rows = Rows.model_validate_json(raw).rows
    except (ValidationError, json.JSONDecodeError):
        return [], lines

    results, used = [], set()
    for r in rows:
        if not 0 <= r.line < len(lines):
            continue
        source = lines[r.line]
        numbers = {to_float(n) for n in re.findall(NUM, source)}
        bounds = [b for b in (r.ref_low, r.ref_high) if b is not None]
        if r.value not in numbers or any(b not in numbers for b in bounds):
            continue          # a number that isn't on the page is not a result
        used.add(r.line)
        results.append(Result(test=r.test, value=r.value, unit=r.unit, ref_low=r.ref_low,
                              ref_high=r.ref_high, ref_source="report" if bounds else ""))
    unread = [l for i, l in enumerate(lines) if i not in used]
    return results, unread
