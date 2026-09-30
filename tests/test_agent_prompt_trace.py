from __future__ import annotations

from contextlib import contextmanager

import pytest

from app import agent as agent_module
from app import incidents


class ManagedPrompt:
    version = 3

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class RecordingObservation:
    def __init__(self, **kwargs) -> None:
        self.start = kwargs
        self.updates: list[dict] = []

    def update(self, **kwargs) -> "RecordingObservation":
        self.updates.append(kwargs)
        return self

    def merged(self) -> dict:
        merged = dict(self.start)
        for update in self.updates:
            merged.update(update)
        return merged


class RecordingLangfuseClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.span_updates: list[dict] = []
        self.observations: list[RecordingObservation] = []

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        observation = RecordingObservation(**kwargs)
        self.observations.append(observation)
        yield observation


@pytest.fixture
def recording_client(monkeypatch) -> RecordingLangfuseClient:
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)
    return client


def run_agent(message: str = "Explain traces"):
    agent = agent_module.LabAgent()
    return agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message=message,
        correlation_id="req-12345678",
    )


def test_agent_records_prompt_version_with_v4_observation_api(
    monkeypatch, recording_client: RecordingLangfuseClient
) -> None:
    propagated: list[dict] = []

    @contextmanager
    def record_attributes(**kwargs):
        propagated.append(kwargs)
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    run_agent()

    span_update = recording_client.span_updates[-1]
    assert span_update["metadata"] == {
        "doc_count": 1,
        "query_preview": "Explain traces",
        "prompt_name": "day13-chat",
        "prompt_label": "production",
        "prompt_version": "3",
        "prompt_source": "langfuse",
        "prompt_fetch_error": "",
    }
    assert span_update["version"] == "3"
    assert propagated[0]["metadata"]["correlation_id"] == "req-12345678"
    assert propagated[-1]["prompt"] is recording_client.prompt


def test_agent_creates_retrieval_and_generation_child_observations(
    recording_client: RecordingLangfuseClient,
) -> None:
    result = run_agent()

    retrieval, prompt_span, generation = recording_client.observations
    assert prompt_span.start["name"] == "prompt-resolve"
    assert prompt_span.merged()["metadata"]["prompt_version"] == "3"
    assert retrieval.start["name"] == "retrieval"
    assert retrieval.start["as_type"] == "retriever"
    assert retrieval.merged()["metadata"]["tool_success"] is True

    gen = generation.merged()
    assert gen["name"] == "llm-generation"
    assert gen["as_type"] == "generation"
    assert gen["model"] == "claude-sonnet-4-5"
    assert gen["prompt"] is recording_client.prompt
    assert gen["usage_details"] == {
        "input": result.tokens_in,
        "output": result.tokens_out,
        "total": result.tokens_in + result.tokens_out,
    }
    assert gen["cost_details"]["total"] == result.cost_usd


def test_observations_do_not_capture_raw_pii(recording_client: RecordingLangfuseClient) -> None:
    run_agent("Refund policy? Email student@vinuni.edu.vn, phone 0987654321")

    raw = repr([observation.merged() for observation in recording_client.observations])
    raw += repr(recording_client.span_updates)
    assert "student@vinuni.edu.vn" not in raw
    assert "0987654321" not in raw


def test_retrieval_failure_marks_observation_as_error(
    monkeypatch, recording_client: RecordingLangfuseClient
) -> None:
    monkeypatch.setitem(incidents.STATE, "tool_fail", True)

    with pytest.raises(RuntimeError):
        run_agent()

    (retrieval,) = recording_client.observations
    merged = retrieval.merged()
    assert merged["level"] == "ERROR"
    assert merged["metadata"]["tool_success"] is False
