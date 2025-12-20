from __future__ import annotations

from . import explain, guard
from .extract import extract
from .models import Report, Status
from .parse import parse_rows
from .ranges import ground


def process(report: Report) -> Report:
    results, leftovers = parse_rows(report.raw_text)
    more, _unread = extract(leftovers)
    results = ground(results + more, report.patient)
    report = report.model_copy(update={"results": results, "status": Status.EXTRACTED})

    text = explain.draft(results, report.patient)
    extra = (report.patient.age,) if report.patient.age is not None else ()
    issues = guard.problems(text) + guard.numbers_grounded(text, results, extra)
    if issues:
        text = explain.draft(results, report.patient, feedback="; ".join(issues))
        issues = guard.problems(text) + guard.numbers_grounded(text, results, extra)
    if issues:
        # don't hand the clinician a draft that breaks the rules; hand them the facts
        text = ("[Automatic draft withheld: " + "; ".join(issues) + "]\n\n"
                + "\n".join(explain._line(r) for r in results))
    return report.model_copy(update={"draft": text, "status": Status.DRAFTED})
