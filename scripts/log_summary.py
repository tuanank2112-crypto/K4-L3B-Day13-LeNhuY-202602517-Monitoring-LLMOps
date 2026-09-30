"""Tóm tắt latency/error/cost/token/quality từ data/logs.jsonl, tách theo khoảng thời gian.

Ví dụ:
    python scripts/log_summary.py
    python scripts/log_summary.py --window rag_slow=2026-09-30T16:25:49,2026-09-30T16:26:18

Request không thuộc --window nào được gom vào nhóm "normal".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.metrics import percentile


def parse_window(raw: str) -> tuple[str, str, str]:
    name, _, span = raw.partition("=")
    start, _, end = span.partition(",")
    if not (name and start and end):
        raise argparse.ArgumentTypeError("dùng dạng name=START_ISO,END_ISO")
    return name, start, end


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--logs", type=Path, default=Path("data/logs.jsonl"))
    parser.add_argument("--window", type=parse_window, action="append", default=[])
    args = parser.parse_args()

    groups: dict[str, list[dict]] = {}
    for line in args.logs.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = record.get("ts", "")
        name = next((n for n, start, end in args.window if start <= ts < end), "normal")
        groups.setdefault(name, []).append(record)

    print("group | requests | failed | error% | retrieval_ok% | p50/p95/p99 ms | ttft_p95 ms | avg cost usd | avg tokens_out | quality")
    for name, records in groups.items():
        received = [r for r in records if r.get("event") == "request_received"]
        responses = [r for r in records if r.get("event") == "response_sent"]
        failed = [r for r in records if r.get("event") == "request_failed"]
        tools = [r for r in records if r.get("tool_success") is not None]
        latency = [r["latency_ms"] for r in responses]
        error_pct = len(failed) / len(received) * 100 if received else 0.0
        tool_pct = sum(r["tool_success"] is True for r in tools) / len(tools) * 100 if tools else 0.0
        avg = lambda key: round(mean(r[key] for r in responses), 6) if responses else "-"
        print(
            f"{name} | {len(received)} | {len(failed)} | {error_pct:.1f} | {tool_pct:.1f} | "
            f"{percentile(latency, 50):.0f}/{percentile(latency, 95):.0f}/{percentile(latency, 99):.0f} | "
            f"{percentile([r['ttft_ms'] for r in responses], 95):.0f} | {avg('cost_usd')} | "
            f"{avg('tokens_out')} | {avg('quality_score')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
