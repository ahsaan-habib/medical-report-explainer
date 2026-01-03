"""uvicorn medrep.api:app --port 8030

Auth is deliberately minimal here (two static tokens). Put this behind your
real identity provider before it sees a real report.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import audit, store
from .models import Patient, Report, Status
from .parse import read_text
from .pipeline import process

app = FastAPI(title="medical-report-explainer")
CLINICIAN_TOKEN = os.environ.get("MEDREP_CLINICIAN_TOKEN", "dev-clinician")
STATIC = Path(__file__).parent / "static"


def clinician(authorization: str = Header(...), x_clinician: str = Header(...)) -> str:
    if authorization.removeprefix("Bearer ").strip() != CLINICIAN_TOKEN:
        raise HTTPException(401)
    return x_clinician


@app.post("/reports")
async def upload(file: UploadFile = File(...), sex: str | None = Form(None), age: int | None = Form(None),
                 who: str = Depends(clinician)) -> dict:
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "x.txt").suffix) as tmp:
        tmp.write(await file.read())
        tmp.flush()
        text = read_text(Path(tmp.name))
    report = store.save(Report(id=uuid.uuid4().hex[:12], raw_text=text, patient=Patient(sex=sex, age=age)))
    audit.log(report.id, who, "uploaded", filename=file.filename)
    report = store.save(process(report))
    audit.log(report.id, "system", "drafted", results=len(report.results))
    return {"id": report.id, "status": report.status}


@app.get("/review")
def queue(who: str = Depends(clinician)) -> list[dict]:
    return [r.model_dump(exclude={"raw_text"}) for r in store.all_reports(Status.DRAFTED)]


@app.get("/review/{report_id}")
def detail(report_id: str, who: str = Depends(clinician)) -> dict:
    r = store.get(report_id)
    if r is None:
        raise HTTPException(404)
    return {**r.model_dump(), "history": audit.history(report_id)}


class Decision(BaseModel):
    final_text: str = ""
    reason: str = ""


@app.post("/review/{report_id}/approve")
def approve(report_id: str, body: Decision, who: str = Depends(clinician)) -> dict:
    if store.get(report_id) is None:
        raise HTTPException(404)
    try:
        return {"status": store.approve(report_id, who, body.final_text).status}
    except store.GateError as e:
        raise HTTPException(409, str(e))


@app.post("/review/{report_id}/reject")
def reject(report_id: str, body: Decision, who: str = Depends(clinician)) -> dict:
    if store.get(report_id) is None:
        raise HTTPException(404)
    try:
        return {"status": store.reject(report_id, who, body.reason).status}
    except store.GateError as e:
        raise HTTPException(409, str(e))


@app.get("/patient/{report_id}")
def patient(report_id: str) -> dict:
    text = store.patient_view(report_id)
    if text is None:
        return {"status": "pending_review",
                "message": "Your results are being reviewed by your clinician and will appear here once they have."}
    return {"status": "ready", "explanation": text}


@app.get("/")
def console() -> FileResponse:
    return FileResponse(STATIC / "review.html")
