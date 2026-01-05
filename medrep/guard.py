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
    # not "infection": "white cells fight infection" explains the test; "you may have
    # an infection" and "consistent with infection" are caught by the two patterns above
    (r"\b(anaemi|anemi|diabet|hypothyroid|hyperthyroid|kidney disease|liver disease|leuk(a)?emi)\w*", "names a condition"),
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


def numbers_grounded(text: str, results: list[Result], extra: tuple[float, ...] = ()) -> list[str]:
    """Every number in the draft must come from the input values or ranges."""
    # abs(): the scan below reads "-1 mmol/L" as 1
    allowed = {f"{abs(x):g}" for r in results for x in (r.value, r.ref_low, r.ref_high) if x is not None}
    # digits inside units ("10^9/L") are units, not claims
    allowed |= {f"{float(n):g}" for r in results for n in re.findall(r"\d+(?:\.\d+)?", r.unit)}
    allowed |= {f"{abs(x):g}" for x in extra}
    stray = [n for n in re.findall(r"\d+(?:\.\d+)?", text) if n not in allowed and f"{float(n):g}" not in allowed]
    return [f"number not in the results ({n})" for n in sorted(set(stray))]
