from __future__ import annotations

import os

import httpx

OLLAMA_URL = os.environ.get("MEDREP_OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("MEDREP_MODEL", "qwen3:4b-instruct")


def chat(messages: list[dict], fmt: str | dict | None = None) -> str:
    body = {"model": MODEL, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0.0}}
    if fmt is not None:
        body["format"] = fmt
    r = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=180)
    r.raise_for_status()
    return r.json()["message"]["content"]
