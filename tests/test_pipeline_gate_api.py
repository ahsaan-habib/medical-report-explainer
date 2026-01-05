import json

import pytest
from fastapi.testclient import TestClient

from conftest import REPORT
from medrep import api, audit, store
from medrep.extract import extract
from medrep.models import Patient, Report, Status
from medrep.pipeline import process

GOOD_DRAFT = ("Worth discussing with your clinician\n- Haemoglobin carries oxygen. Your value is 11.2 g/dL; the "
              "range is 12–15.5 g/dL, so it is below the range.\n\nYour clinician has reviewed these results "
              "and will discuss anything that needs follow-up.")


def test_extract_keeps_only_numbers_that_are_on_the_line(llm):
    lines = ["Ferritin result was 8 ug/L (ref 15-150)", "Vitamin D 52 nmol/L", "Collected 2026-01-02"]
    llm(json.dumps({"rows": [
        {"line": 0, "test": "Ferritin", "value": 8, "unit": "ug/L", "ref_low": 15, "ref_high": 150},
        {"line": 1, "test": "Vitamin D", "value": 25, "unit": "nmol/L"},      # invented value
        {"line": 7, "test": "Ghost", "value": 1, "unit": "x"}]}))             # no such line
    results, unread = extract(lines)
    assert [r.test for r in results] == ["Ferritin"] and results[0].ref_source == "report"
    assert unread == lines[1:]
    # the model drops a bound: both ends come from the printed range instead
    llm(json.dumps({"rows": [{"line": 0, "test": "Ferritin", "value": 8, "unit": "ug/L", "ref_high": 150}]}))
    (r,), _ = extract(lines)
    assert (r.ref_low, r.ref_high) == (15.0, 150.0)
    llm("not json")
    assert extract(lines) == ([], lines)
    assert extract([]) == ([], [])


def test_pipeline_redrafts_then_withholds(llm):
    report = Report(id="r1", raw_text=REPORT, patient=Patient(sex="female", age=40))
    fake = llm('{"rows": []}', GOOD_DRAFT)
    out = process(report)
    assert out.status == Status.DRAFTED and out.draft == GOOD_DRAFT and len(fake.calls) == 2
    assert {r.flag for r in out.results} >= {"low", "normal"}

    bad = "You may have anaemia. Take iron tablets."
    fake = llm('{"rows": []}', bad, bad)
    out = process(report)
    assert out.draft.startswith("[Automatic draft withheld:") and "Haemoglobin: 11.2 g/dL" in out.draft
    assert "broke a rule" in fake.calls[2]["messages"][1]["content"]


def test_gate_state_machine():
    r = store.save(Report(id="r2", status=Status.DRAFTED, draft="draft text"))
    with pytest.raises(store.GateError, match="named clinician"):
        store.approve(r.id, " ", "final")
    with pytest.raises(store.GateError, match="text the patient will see"):
        store.approve(r.id, "dr.lee", "")
    assert store.patient_view(r.id) is None
    assert store.approve(r.id, "dr.lee", "final text").status == Status.APPROVED
    assert store.patient_view(r.id) == "final text"
    with pytest.raises(store.GateError, match="approved -> rejected"):
        store.reject(r.id, "dr.lee")
    actions = [h["action"] for h in audit.history(r.id)]
    assert actions == ["approved", "viewed"] and "-draft text" in audit.history(r.id)[0]["edits"]


def test_api_upload_review_approve_patient(llm, monkeypatch):
    llm('{"rows": []}', GOOD_DRAFT)
    c = TestClient(api.app)
    h = {"Authorization": f"Bearer {api.CLINICIAN_TOKEN}", "X-Clinician": "dr.lee"}
    assert c.get("/review", headers={**h, "Authorization": "Bearer wrong"}).status_code == 401
    up = c.post("/reports", headers=h, files={"file": ("report.txt", REPORT.encode())},
                data={"sex": "female", "age": "40"}).json()
    assert up["status"] == "drafted"
    rid = up["id"]
    assert c.get(f"/patient/{rid}").json()["status"] == "pending_review"
    queue = c.get("/review", headers=h).json()
    assert [q["id"] for q in queue] == [rid] and "raw_text" not in queue[0]
    detail = c.get(f"/review/{rid}", headers=h).json()
    assert [x["action"] for x in detail["history"]] == ["uploaded", "drafted"]
    assert c.post(f"/review/{rid}/approve", headers=h, json={"final_text": ""}).status_code == 409
    assert c.post(f"/review/{rid}/approve", headers=h, json={"final_text": "Edited."}).json() == {"status": "approved"}
    assert c.get(f"/patient/{rid}").json() == {"status": "ready", "explanation": "Edited."}
    assert c.post(f"/review/{rid}/reject", headers=h, json={}).status_code == 409
    assert c.get("/review/nope", headers=h).status_code == 404
    assert "review" in c.get("/").text.lower()
