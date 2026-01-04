# medical-report-explainer

Blueprint 2 from *Designing AI Automation for Your Business*: a lab report
goes in, a plain-language explanation comes out — but only after a clinician
has read, edited and approved it.

> Not a medical device and not for clinical use as-is. The bundled reference
> ranges are sample values; replace them with your laboratory's validated
> intervals. Put real authentication in front of it before any real data.

```
upload ─▶ parse table rows (regex, exact) ─▶ model transcribes leftover lines
                                              (values must appear verbatim)
       ─▶ ground: range printed on the report > reference table (test/unit/sex/age) > "unknown"
       ─▶ draft explanation (local model) ─▶ guard: diagnosis / treatment language,
                                              numbers not in the results → one rewrite, else withheld
       ─▶ DRAFTED ── clinician edits ──▶ APPROVED ─▶ patient can see it
                                     └─▶ REJECTED ─▶ clinician contacts the patient
```

## The two things that make it safe

**Grounded values.** "Your value is X; the reference range is Y to Z" comes
from the report itself or a named row in a reference table, never from the
model's memory. Every range carries its source into the review screen. No
unit conversion; an unmatched unit stays "unknown".

**The clinician is a step, not a fallback.** Report status is a state
machine (`medrep/store.py`). The only path to `APPROVED` is `approve()`,
which needs a named clinician and the final text; the patient endpoint
returns "pending review" for every other state. The AI's job is to turn a
fifteen-minute read into a two-minute confirmation, not to replace it.

Every approval is audit-logged with the diff between the AI draft and what
the clinician released, so how much the drafts get edited is measurable.

## What the draft will not do

Name a condition, suggest a cause, recommend treatment or dosage, reassure
or alarm, or mention a number that isn't in the results. `medrep/guard.py`
checks for all of it; a draft that still breaks a rule after one rewrite is
withheld and the clinician gets the raw values instead.

## Run it

```bash
ollama pull qwen3:4b-instruct   # not plain qwen3:4b: that tag is now a thinking-only build
python -m venv .venv && .venv/bin/pip install -e . && source .venv/bin/activate
uvicorn medrep.api:app --port 8030      # review console at /
curl -F file=@report.pdf -F sex=female -F age=45 \
     -H 'authorization: Bearer dev-clinician' -H 'x-clinician: Dr Example' \
     localhost:8030/reports
```
