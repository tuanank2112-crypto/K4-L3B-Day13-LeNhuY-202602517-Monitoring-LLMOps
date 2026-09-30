from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from scripts import build_dashboard

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_alert_rules_are_complete_and_symptom_based() -> None:
    rules = yaml.safe_load((REPO_ROOT / "config" / "alert_rules.yaml").read_text(encoding="utf-8"))
    alerts = rules["alerts"]
    runbook = (REPO_ROOT / "docs" / "alerts.md").read_text(encoding="utf-8")

    assert len(alerts) == 3
    for alert in alerts:
        for field in ("name", "severity", "condition", "duration", "owner", "runbook", "slack_channel"):
            assert alert.get(field) and "TODO" not in str(alert[field]), (alert.get("name"), field)
        assert alert["type"] == "symptom-based"
        assert alert["channel"] == "slack"
        assert alert["severity"] in {"info", "warning", "critical"}
        assert re.fullmatch(r"\d+[smh]", alert["duration"])
        anchor = alert["runbook"].split("#")[1]
        assert f"## {anchor.replace('-', ' ').title()}" in runbook
        assert alert["name"] in runbook


def test_slo_error_budget_matches_target() -> None:
    slo = yaml.safe_load((REPO_ROOT / "config" / "slo.yaml").read_text(encoding="utf-8"))["primary_slo"]
    assert round(100 - slo["target_percent"], 6) == slo["error_budget_percent"]


def test_dashboard_builder_computes_panels_from_logs(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    ts = lambda offset: (now - timedelta(minutes=offset)).isoformat().replace("+00:00", "Z")
    records = [
        {"ts": ts(2), "event": "request_received"},
        {"ts": ts(2), "event": "response_sent", "latency_ms": 150, "ttft_ms": 50, "cost_usd": 0.002,
         "tokens_in": 40, "tokens_out": 120, "quality_score": 0.9, "tool_success": True},
        {"ts": ts(1), "event": "request_received"},
        {"ts": ts(1), "event": "request_failed", "error_type": "RuntimeError", "tool_success": False},
        {"ts": ts(120), "event": "request_received"},  # ngoài cửa sổ 60 phút
    ]
    logs = tmp_path / "logs.jsonl"
    logs.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    loaded = build_dashboard.load_records(logs)
    window = build_dashboard.build_window(loaded, 60, "now")
    data = build_dashboard.compute(loaded, window)

    assert data["traffic"]["stats"]["count"] == 2
    assert data["errors"]["stats"]["error_rate_pct"] == 50
    assert data["errors"]["stats"]["tool_success_rate_pct"] == 50
    assert data["errors"]["stats"]["count_by_value"] == {"RuntimeError": 1}
    assert data["latency"]["stats"]["p95"] == 150
    assert data["cost"]["stats"]["total"] == 0.002

    config = yaml.safe_load((REPO_ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8"))
    page = build_dashboard.render(config, loaded, window, logs)
    for panel in config["dashboard"]["panels"]:
        assert panel["title"] in page
    assert "last 60 minutes" in page
