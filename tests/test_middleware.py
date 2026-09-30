from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app
from app.middleware import resolve_correlation_id

REQUEST_ID = re.compile(r"^req-[0-9a-f]{8}$")


def post_chat(payload: dict, headers: dict | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/chat", json=payload, headers=headers or {})

    return asyncio.run(send())


def test_resolve_correlation_id_accepts_valid_and_regenerates_invalid() -> None:
    assert resolve_correlation_id("req-1a2b3c4d") == "req-1a2b3c4d"
    assert resolve_correlation_id("REQ-1A2B3C4D") == "req-1a2b3c4d"
    for bad in (None, "", "MISSING", "req-xyz", "req-1a2b3c4d\nforged-log-line"):
        generated = resolve_correlation_id(bad)
        assert REQUEST_ID.fullmatch(generated)
        assert generated != bad


def test_chat_returns_and_logs_same_correlation_id(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    payload = {
        "user_id": "student-01",
        "session_id": "session-01",
        "feature": "qa",
        "message": "My email is student@vinuni.edu.vn and phone 0987654321",
    }

    first = post_chat(payload, headers={"x-request-id": "req-0000abcd"})
    second = post_chat({**payload, "session_id": "session-02", "feature": "summary"})

    assert first.headers["x-request-id"] == "req-0000abcd"
    assert first.json()["correlation_id"] == "req-0000abcd"
    assert float(first.headers["x-response-time-ms"]) >= 0
    second_id = second.headers["x-request-id"]
    assert REQUEST_ID.fullmatch(second_id) and second_id != "req-0000abcd"

    raw = log_path.read_text(encoding="utf-8")
    assert "student@vinuni.edu.vn" not in raw
    assert "0987654321" not in raw

    events = [json.loads(line) for line in raw.splitlines()]
    api_events = [event for event in events if event.get("service") == "api"]
    assert {event["event"] for event in api_events} >= {"request_received", "response_sent"}
    for event in api_events:
        assert {"user_id_hash", "session_id", "feature", "model", "env"} <= event.keys()
        # Không rò context: mỗi dòng mang đúng session của request tạo ra nó.
        expected_session = "session-01" if event["correlation_id"] == "req-0000abcd" else "session-02"
        assert event["session_id"] == expected_session
        assert event["user_id_hash"] != "student-01"
