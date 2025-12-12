"""Get lab rows out of a report.

Deterministic first: most lab PDFs are a table of `Test  Value  Unit  Range`.
A regex that understands that table is exact when it matches, and the model
is only asked about the lines it didn't.
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import Result

NUM = r"[-+]?\d+(?:[.,]\d+)?"
# Haemoglobin   13.2   g/dL   12.0 - 15.5      (also "12.0–15.5", "< 5.0", "> 60")
ROW = re.compile(
    rf"^\s*(?P<test>[A-Za-z][A-Za-z0-9 ()/,.\-]*?)\s{{2,}}(?P<value>{NUM})\s*(?P<flag>[HL]\b)?\s+"
    rf"(?P<unit>[^\s\d][^\s]*)\s+(?P<range>(?:{NUM}\s*[-–]\s*{NUM})|(?:[<>]=?\s*{NUM}))\s*$")


def to_float(s: str) -> float:
    return float(s.replace(",", "."))


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_rows(text: str) -> tuple[list[Result], list[str]]:
    """(parsed results, lines that look like data but didn't parse)."""
    results, leftovers = [], []
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            if re.search(NUM, line) and re.search(r"[A-Za-z]{3,}", line):
                leftovers.append(line.strip())
            continue
        rng = m["range"].replace(" ", "")
        low = high = None
        if rng[0] in "<>":
            bound = to_float(rng.lstrip("<>="))
            low, high = (None, bound) if rng[0] == "<" else (bound, None)
        else:
            a, b = re.split(r"[-–]", rng, maxsplit=1)
            low, high = to_float(a), to_float(b)
        results.append(Result(test=m["test"].strip(), value=to_float(m["value"]), unit=m["unit"],
                              ref_low=low, ref_high=high, ref_source="report"))
    return results, leftovers
