"""Draft an explanation with a real local model and run it through the
guards. Opt-in:

    RUN_OLLAMA=1 pytest tests/test_smoke_ollama.py -s
"""
import os

import pytest

from conftest import REPORT
from medrep.models import Patient, Report, Status
from medrep.pipeline import process

pytestmark = pytest.mark.skipif(os.environ.get("RUN_OLLAMA") != "1", reason="set RUN_OLLAMA=1 to run")


def test_real_draft_passes_the_guards_or_is_withheld():
    out = process(Report(id="smoke", raw_text=REPORT, patient=Patient(sex="female", age=40)))
    print("\n", [(r.test, r.value, r.flag) for r in out.results], "\n\n", out.draft)
    assert out.status == Status.DRAFTED and out.draft
    ferritin = [r for r in out.results if r.test.lower().startswith("ferritin")]
    assert ferritin and ferritin[0].flag == "low", "8 against a printed 15-150 must be low"
    # a withheld draft is a safe outcome, but on this report the rules are easy to keep
    assert not out.draft.startswith("[Automatic draft withheld")
