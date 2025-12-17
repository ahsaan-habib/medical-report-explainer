"""Plain-language explanation. Explains and surfaces; never diagnoses.

The model gets the grounded values (value, range, where the range came from,
flag) rather than the raw report, so "your value is X, the range is Y to Z"
comes from a cited source, not from the model's memory.
"""
from __future__ import annotations

from . import llm
from .models import Patient, Result

SYSTEM = """You help a clinician by drafting a plain-language explanation of a
patient's lab results. The clinician will review and edit it before the
patient sees it.

Rules:
- For each result: what the test measures in one sentence, the value, the
  reference range exactly as given, and whether it is inside, above or below it.
- Use the flags given. If a flag is "unknown", say no reference range was
  available and the clinician will comment.
- Do NOT diagnose, name conditions the patient may have, suggest causes,
  recommend treatment, medication or dosage, or say whether to worry.
- Do NOT add reference ranges or numbers that are not in the input.
- List results outside their range first under "Worth discussing with your
  clinician", then the rest under "Within the reference range".
- Plain words, short sentences, no jargon without a one-line explanation.
- End with: "Your clinician has reviewed these results and will discuss anything that needs follow-up."
"""


def _line(r: Result) -> str:
    if r.ref_low is None and r.ref_high is None:
        rng = "no reference range available"
    elif r.ref_low is None:
        rng = f"below {r.ref_high:g} {r.unit}"
    elif r.ref_high is None:
        rng = f"above {r.ref_low:g} {r.unit}"
    else:
        rng = f"{r.ref_low:g}–{r.ref_high:g} {r.unit}"
    src = "printed on the report" if r.ref_source == "report" else (r.ref_source or "none")
    return f"- {r.test}: {r.value:g} {r.unit}; reference {rng} (source: {src}); flag: {r.flag}"


def draft(results: list[Result], patient: Patient, feedback: str = "") -> str:
    who = ", ".join(x for x in (patient.sex, f"{patient.age} years" if patient.age is not None else None) if x)
    user = f"Patient: {who or 'not specified'}\nResults:\n" + "\n".join(map(_line, results))
    if feedback:
        user += f"\n\nYour previous draft broke a rule: {feedback}. Rewrite it following every rule."
    return llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]).strip()
