"""Đọc traces của project Langfuse cá nhân qua Public API (key trong .env) để đối chiếu với log.

    python scripts/langfuse_traces.py list --since 2026-09-30T16:44:00Z     # danh sách trace
    python scripts/langfuse_traces.py show --correlation-id req-1a2b3c4d     # cây observation của 1 request

Trace được nối với structured log bằng metadata `correlation_id`.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio


def client() -> httpx.Client:
    load_dotenv(REPO_ROOT / ".env")
    return httpx.Client(
        base_url=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").rstrip("/") + "/api/public",
        auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]),
        timeout=30,
    )


def get(http: httpx.Client, path: str, **params) -> dict:
    for attempt in range(5):
        response = http.get(path, params=params)
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()
        time.sleep(2 * (attempt + 1))
    response.raise_for_status()
    return {}


def fetch_traces(http: httpx.Client, since: str, until: str | None = None) -> list[dict]:
    traces, page = [], 1
    while True:
        params = {"fromTimestamp": since, "limit": 100, "page": page, "orderBy": "timestamp.asc"}
        if until:
            params["toTimestamp"] = until
        data = get(http, "/traces", **params)
        traces += data.get("data", [])
        if page >= data.get("meta", {}).get("totalPages", 1):
            return traces
        page += 1


def correlation_id(trace: dict) -> str:
    return (trace.get("metadata") or {}).get("correlation_id", "-")


def ms(start: str | None, end: str | None) -> str:
    if not (start and end):
        return "-"
    parse = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
    return f"{(parse(end) - parse(start)).total_seconds() * 1000:.0f}ms"


def show(http: httpx.Client, trace: dict) -> None:
    detail = get(http, f"/traces/{trace['id']}")
    project = get(http, "/projects").get("data", [{}])[0].get("name", "?")
    print(f"project: {project}")
    print(f"trace id: {detail['id']}  name: {detail.get('name')}  timestamp: {detail.get('timestamp')}")
    print(f"user_id: {detail.get('userId')}  session_id: {detail.get('sessionId')}  env: {detail.get('environment')}")
    print(f"tags: {detail.get('tags')}  latency: {detail.get('latency')}s  total_cost: {detail.get('totalCost')}")
    # Bỏ resourceAttributes/scope do SDK tự thêm (có public key) để evidence không lộ key.
    trace_meta = {k: v for k, v in (detail.get("metadata") or {}).items() if k not in {"resourceAttributes", "scope"}}
    print(f"trace metadata: {trace_meta}")
    observations = sorted(detail.get("observations", []), key=lambda o: o.get("startTime") or "")
    children: dict[str | None, list[dict]] = {}
    for obs in observations:
        children.setdefault(obs.get("parentObservationId"), []).append(obs)

    def walk(parent: str | None, depth: int) -> None:
        for obs in children.get(parent, []):
            line = f"{'  ' * depth}└─ [{obs.get('type')}] {obs.get('name')}  {ms(obs.get('startTime'), obs.get('endTime'))}  level={obs.get('level')}"
            if obs.get("statusMessage"):
                line += f"  status='{obs['statusMessage']}'"
            print(line)
            pad = "  " * depth + "     "
            if obs.get("type") == "GENERATION":
                print(f"{pad}model={obs.get('model')} prompt={obs.get('promptName')} v{obs.get('promptVersion')} "
                      f"usage={obs.get('usageDetails')} cost={obs.get('costDetails')}")
            if obs.get("metadata"):
                meta = {k: v for k, v in obs["metadata"].items() if k not in {"resourceAttributes", "scope"}}
                print(f"{pad}metadata={meta}")
            if obs.get("input") is not None:
                print(f"{pad}input={obs.get('input')}")
            if obs.get("output") is not None:
                print(f"{pad}output={obs.get('output')}")
            walk(obs["id"], depth + 1)

    walk(None, 0)


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--since", required=True)
    list_cmd.add_argument("--until")
    show_cmd = sub.add_parser("show")
    show_cmd.add_argument("--correlation-id", required=True)
    show_cmd.add_argument("--since", default="2026-01-01T00:00:00Z")
    args = parser.parse_args()

    with client() as http:
        if args.action == "list":
            traces = fetch_traces(http, args.since, args.until)
            project = get(http, "/projects").get("data", [{}])[0].get("name", "?")
            print(f"project: {project} | traces since {args.since}: {len(traces)}")
            print("timestamp | trace id | name | correlation_id | prompt label/version | latency s")
            for trace in traces:
                meta = trace.get("metadata") or {}
                print(f"{trace.get('timestamp')} | {trace['id']} | {trace.get('name')} | {correlation_id(trace)} | "
                      f"{meta.get('prompt_label', '-')}/{meta.get('prompt_version', '-')} | {trace.get('latency')}")
            return 0

        matches = [t for t in fetch_traces(http, args.since) if correlation_id(t) == args.correlation_id]
        if not matches:
            print(f"Không tìm thấy trace có correlation_id={args.correlation_id}")
            return 1
        show(http, matches[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
