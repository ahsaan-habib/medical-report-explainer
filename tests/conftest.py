"""Offline by default: the model is scripted, the database is a temp file.
test_smoke_ollama.py is opt-in."""
import pytest

from medrep import store


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", str(tmp_path / "medrep.db"))


class ScriptedLLM:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, messages, fmt=None):
        self.calls.append({"messages": messages, "fmt": fmt})
        return self.replies.pop(0)


@pytest.fixture
def llm(monkeypatch):
    def install(*replies):
        fake = ScriptedLLM(*replies)
        monkeypatch.setattr("medrep.llm.chat", fake)
        return fake
    return install


REPORT = """Example Lab Ltd — Patient report
Haemoglobin          11.2  L  g/dL     12.0 - 15.5
Sodium               139      mmol/L   135–145
eGFR                 72       mL/min   > 60
White cell count     6.2      10^9/L   4.5 - 11.0
Base excess          -1.0     mmol/L   -2 - 2
Ferritin result was 8 ug/L (ref 15-150)
Collected 2026-01-02
"""
