"""Catch diagnostic or prescriptive language before a clinician even sees it.

A pattern list is blunt, and that's fine: it runs on a draft that a clinician
reviews anyway. Its job is to keep the default output inside "explain", so
review is a confirmation rather than a rewrite.
"""
from __future__ import annotations

import re

from .models import Result

PATTERNS = [
    (r"\byou (may |might |probably |likely )?(have|are suffering from|are developing)\b", "states a condition"),
    (r"\b(diagnos(is|ed|e)|indicat(es|ive of)|consistent with|suggest(s|ive of))\b", "diagnostic framing"),
    (r"\b(anaemi|anemi|diabet|hypothyroid|hyperthyroid|kidney disease|liver disease|infection|leuk(a)?emi)\w*", "names a condition"),
    (r"\b(take|start|stop|increase|decrease|reduce)\b.{0,30}\b(mg|dose|tablet|medication|medicine|supplement|insulin)\b", "treatment advice"),
    (r"\b(nothing to worry about|no need to worry|don't worry|do not worry|serious|dangerous)\b", "reassurance or alarm"),
]


def problems(text: str) -> list[str]:
    found = []
    for pattern, label in PATTERNS:
        m = re.search(pattern, text, re.I)
        if m:
            found.append(f'{label} ("{m.group(0)}")')
    return found


def numbers_grounded(text: str, results: list[Result]) -> list[str]:
    """Every number in the draft must come from the input values or ranges."""
    allowed = {f"{x:g}" for r in results for x in (r.value, r.ref_low, r.ref_high) if x is not None}
    stray = [n for n in re.findall(r"\d+(?:\.\d+)?", text) if n not in allowed and f"{float(n):g}" not in allowed]
    return [f"number not in the results ({n})" for n in sorted(set(stray))]
