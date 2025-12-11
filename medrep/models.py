from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Status(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTED = "extracted"
    DRAFTED = "drafted"          # explanation written, waiting for a clinician
    APPROVED = "approved"        # clinician signed off -> visible to the patient
    REJECTED = "rejected"        # clinician will contact the patient directly


class Patient(BaseModel):
    sex: Literal["female", "male"] | None = None
    age: int | None = Field(default=None, ge=0, le=130)


class Result(BaseModel):
    test: str
    value: float
    unit: str
    ref_low: float | None = None
    ref_high: float | None = None
    ref_source: str = ""         # "report" or a row in the reference table
    flag: Literal["low", "normal", "high", "unknown"] = "unknown"


class Report(BaseModel):
    id: str
    status: Status = Status.UPLOADED
    patient: Patient = Patient()
    raw_text: str = ""
    results: list[Result] = []
    draft: str = ""
    final: str = ""              # what the patient sees, after clinician edits
    reviewer: str = ""
