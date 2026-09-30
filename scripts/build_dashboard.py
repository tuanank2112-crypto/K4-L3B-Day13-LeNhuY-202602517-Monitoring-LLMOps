"""Sinh dashboard HTML 6 panel từ data/logs.jsonl theo contract config/dashboard.yaml.

Ví dụ:
    python scripts/build_dashboard.py                 # 60 phút gần nhất tính tới hiện tại
    python scripts/build_dashboard.py --anchor latest # 60 phút tính tới log mới nhất
    python scripts/build_dashboard.py --watch         # tự sinh lại mỗi refresh_seconds

Mở file output (mặc định data/dashboard.html) bằng trình duyệt; trang tự reload theo
refresh_seconds của contract. Thresholds, time range và đơn vị đều đọc từ YAML.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.metrics import percentile
from scripts.validate_dashboard import load_dashboard_config

COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"]


@dataclass
class Window:
    start: datetime
    end: datetime
    minutes: list[datetime] = field(default_factory=list)


def parse_ts(value: str) -> datetime | None:
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = parse_ts(record.get("ts", ""))
        if ts is not None:
            record["_ts"] = ts
            records.append(record)
    return records


def build_window(records: list[dict], minutes: int, anchor: str) -> Window:
    if anchor == "latest" and records:
        end = max(record["_ts"] for record in records)
    else:
        end = datetime.now(timezone.utc)
    end = end.replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=minutes)
    return Window(start, end, [start + timedelta(minutes=i) for i in range(minutes)])


def bucket(records: list[dict], window: Window) -> dict[datetime, list[dict]]:
    buckets: dict[datetime, list[dict]] = defaultdict(list)
    for record in records:
        buckets[record["_ts"].replace(second=0, microsecond=0)].append(record)
    return buckets


def compute(records: list[dict], window: Window) -> dict:
    in_window = [r for r in records if window.start <= r["_ts"] < window.end]
    by_event: dict[str, list[dict]] = defaultdict(list)
    for record in in_window:
        by_event[record.get("event", "")].append(record)
    responses = by_event["response_sent"]
    received = by_event["request_received"]
    failed = by_event["request_failed"]
    tool_events = [r for r in in_window if r.get("tool_success") is not None]

    per_minute: dict[str, dict[datetime, list[dict]]] = {
        "responses": bucket(responses, window),
        "received": bucket(received, window),
        "failed": bucket(failed, window),
        "tools": bucket(tool_events, window),
    }

    def series(kind: str, fn) -> list[float | None]:
        return [fn(per_minute[kind].get(minute, [])) for minute in window.minutes]

    def pct(values: list[dict], key: str, p: int) -> float | None:
        items = [r[key] for r in values if isinstance(r.get(key), (int, float))]
        return percentile(items, p) if items else None

    def total(values: list[dict], key: str) -> float:
        return sum(r.get(key) or 0 for r in values)

    def error_rate(minute: datetime) -> float | None:
        requests = len(per_minute["received"].get(minute, []))
        if not requests:
            return None
        return len(per_minute["failed"].get(minute, [])) / requests * 100

    def success_rate(values: list[dict]) -> float | None:
        if not values:
            return None
        return sum(1 for r in values if r.get("tool_success") is True) / len(values) * 100

    latencies = [r["latency_ms"] for r in responses if isinstance(r.get("latency_ms"), int)]
    ttfts = [r["ttft_ms"] for r in responses if isinstance(r.get("ttft_ms"), int)]
    qualities = [r["quality_score"] for r in responses if isinstance(r.get("quality_score"), (int, float))]
    active_minutes = [m for m in window.minutes if per_minute["received"].get(m)]

    return {
        "latency": {
            "series": {
                "P50": series("responses", lambda v: pct(v, "latency_ms", 50)),
                "P95": series("responses", lambda v: pct(v, "latency_ms", 95)),
                "P99": series("responses", lambda v: pct(v, "latency_ms", 99)),
                "TTFT P95": series("responses", lambda v: pct(v, "ttft_ms", 95)),
            },
            "stats": {
                "p50": percentile(latencies, 50) if latencies else None,
                "p95": percentile(latencies, 95) if latencies else None,
                "p99": percentile(latencies, 99) if latencies else None,
                "ttft_p95": percentile(ttfts, 95) if ttfts else None,
            },
        },
        "traffic": {
            "series": {"requests/min": series("received", lambda v: float(len(v)) if v else None)},
            "stats": {
                "count": len(received),
                "rate_per_minute": len(received) / len(active_minutes) if active_minutes else None,
            },
        },
        "errors": {
            "series": {
                "error rate %": [error_rate(m) for m in window.minutes],
                "retrieval success %": series("tools", success_rate),
            },
            "stats": {
                "error_rate_pct": len(failed) / len(received) * 100 if received else None,
                "tool_success_rate_pct": success_rate(tool_events),
                "count_by_value": dict(Counter(r.get("error_type") or "unknown" for r in failed)),
            },
        },
        "cost": {
            "series": {"USD/min": series("responses", lambda v: total(v, "cost_usd") if v else None)},
            "stats": {"total": total(responses, "cost_usd"), "sum_by_minute": None},
        },
        "tokens": {
            "series": {
                "tokens_in/min": series("responses", lambda v: total(v, "tokens_in") if v else None),
                "tokens_out/min": series("responses", lambda v: total(v, "tokens_out") if v else None),
            },
            "stats": {
                "tokens_in": total(responses, "tokens_in"),
                "tokens_out": total(responses, "tokens_out"),
                "sum_by_field": max(total(responses, "tokens_in"), total(responses, "tokens_out")),
            },
        },
        "quality": {
            "series": {
                "mean": series(
                    "responses",
                    lambda v: mean([r["quality_score"] for r in v if isinstance(r.get("quality_score"), (int, float))])
                    if v
                    else None,
                )
            },
            "stats": {"mean": mean(qualities) if qualities else None},
        },
        "records_in_window": len(in_window),
    }


def fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "usd":
        return f"${value:.4f}"
    if unit in {"percent"}:
        return f"{value:.1f}%"
    if unit == "score_0_to_1":
        return f"{value:.2f}"
    if unit == "requests_per_minute":
        return f"{value:.1f} rpm"
    if unit == "ms":
        return f"{value:,.0f} ms"
    return f"{value:,.0f}"


def breaches(value: float | None, threshold: dict) -> bool | None:
    if value is None:
        return None
    return value > threshold["value"] if threshold["operator"] == "lte" else value < threshold["value"]


def svg_chart(window: Window, series: dict[str, list[float | None]], threshold: float | None, unit: str) -> str:
    width, height, pad_l, pad_r, pad_t, pad_b = 520, 190, 56, 12, 12, 26
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    values = [v for points in series.values() for v in points if v is not None]
    y_max = max(values + ([threshold] if threshold is not None else []) + [0.0]) or 1.0
    if unit in {"percent"}:
        y_max = max(100.0, y_max)
    y_max *= 1.1
    n = len(window.minutes)

    def x(i: int) -> float:
        return pad_l + (i + 0.5) * plot_w / n

    def y(v: float) -> float:
        return pad_t + plot_h - v / y_max * plot_h

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" preserveAspectRatio="none">']
    for frac in (0, 0.5, 1):
        gy = pad_t + plot_h - frac * plot_h
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{gy:.1f}" y2="{gy:.1f}" class="grid"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{gy + 4:.1f}" class="axis" text-anchor="end">{html.escape(fmt(frac * y_max, unit))}</text>')
    for i in range(0, n, 15):
        parts.append(f'<text x="{x(i):.1f}" y="{height - 6}" class="axis" text-anchor="middle">{window.minutes[i]:%H:%M}</text>')
    parts.append(f'<text x="{width - pad_r}" y="{height - 6}" class="axis" text-anchor="end">{window.end:%H:%M} UTC</text>')

    bar_mode = len(series) <= 2 and unit in {"requests_per_minute", "usd", "tokens"}
    for index, (name, points) in enumerate(series.items()):
        color = COLORS[index % len(COLORS)]
        if bar_mode:
            bar_w = max(1.5, plot_w / n / len(series) - 1)
            for i, v in enumerate(points):
                if v is not None:
                    bx = pad_l + i * plot_w / n + index * bar_w
                    parts.append(
                        f'<rect x="{bx:.1f}" y="{y(v):.1f}" width="{bar_w:.1f}" height="{pad_t + plot_h - y(v):.1f}" '
                        f'fill="{color}"><title>{window.minutes[i]:%H:%M} {html.escape(name)}: {html.escape(fmt(v, unit))}</title></rect>'
                    )
            continue
        segment: list[str] = []
        for i, v in enumerate(points):
            if v is None:
                if len(segment) > 1:
                    parts.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="2"/>')
                segment = []
                continue
            segment.append(f"{x(i):.1f},{y(v):.1f}")
            parts.append(
                f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.5" fill="{color}">'
                f'<title>{window.minutes[i]:%H:%M} {html.escape(name)}: {html.escape(fmt(v, unit))}</title></circle>'
            )
        if len(segment) > 1:
            parts.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="2"/>')

    if threshold is not None:
        ty = y(threshold)
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{ty:.1f}" y2="{ty:.1f}" class="threshold"/>')
        parts.append(f'<text x="{width - pad_r - 4}" y="{ty - 4:.1f}" class="threshold-label" text-anchor="end">threshold {html.escape(fmt(threshold, unit))}</text>')
    parts.append("</svg>")
    return "".join(parts)


STAT_LABELS = {
    "p50": "P50",
    "p95": "P95",
    "p99": "P99",
    "ttft_p95": "TTFT P95",
    "count": "Requests",
    "rate_per_minute": "Avg rate (active min)",
    "error_rate_pct": "Error rate",
    "tool_success_rate_pct": "Retrieval success",
    "total": "Total cost",
    "tokens_in": "Tokens in",
    "tokens_out": "Tokens out",
    "mean": "Mean quality",
}


def render_panel(panel: dict, data: dict, window: Window) -> str:
    unit = panel["unit"]
    threshold = panel["threshold"]
    stats = data["stats"]
    checked = stats.get(threshold["aggregation"])
    status = breaches(checked, threshold)
    badge = {None: ("no data", "muted"), True: ("BREACH", "bad"), False: ("OK", "good")}[status]
    op = "≤" if threshold["operator"] == "lte" else "≥"

    stat_items = []
    for key, value in stats.items():
        if key not in STAT_LABELS or key == "sum_by_minute":
            continue
        stat_unit = "percent" if key.endswith("_pct") else ("count" if key in {"count", "tokens_in", "tokens_out"} else unit)
        stat_items.append(f'<div class="stat"><span>{STAT_LABELS[key]}</span><b>{html.escape(fmt(value, stat_unit))}</b></div>')
    breakdown = stats.get("count_by_value")
    if breakdown is not None:
        text = ", ".join(f"{k}: {v}" for k, v in sorted(breakdown.items())) or "no failures"
        stat_items.append(f'<div class="stat wide"><span>Errors by type</span><b>{html.escape(text)}</b></div>')

    legend = "".join(
        f'<span class="key"><i style="background:{COLORS[i % len(COLORS)]}"></i>{html.escape(name)}</span>'
        for i, name in enumerate(data["series"])
    )
    chart_threshold = threshold["value"] if threshold["aggregation"] not in {"total", "sum_by_field"} else None
    note = "" if chart_threshold is not None else f'<p class="note">Threshold áp dụng cho {html.escape(threshold["aggregation"])} toàn cửa sổ (xem badge).</p>'
    return f"""
<section class="panel">
  <header>
    <h2>{html.escape(panel["title"])}</h2>
    <span class="badge {badge[1]}">{badge[0]}</span>
  </header>
  <p class="meta">unit: <b>{html.escape(unit)}</b> · threshold: {html.escape(threshold["aggregation"])} {op} {threshold["value"]} · checked value: <b>{html.escape(fmt(checked, "percent" if threshold["aggregation"].endswith("_pct") else unit))}</b></p>
  <div class="stats">{"".join(stat_items)}</div>
  <div class="legend">{legend}</div>
  {svg_chart(window, data["series"], chart_threshold, unit)}
  {note}
</section>"""


def render(config: dict, records: list[dict], window: Window, source: Path) -> str:
    dashboard = config["dashboard"]
    data = compute(records, window)
    panels = "".join(render_panel(panel, data[panel["id"]], window) for panel in dashboard["panels"])
    generated = datetime.now(timezone.utc)
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{dashboard["refresh_seconds"]}">
<title>Day 13 Dashboard</title>
<style>
:root {{
  --bg:#f6f7f9; --card:#fff; --fg:#1d2330; --muted:#667085; --line:#e4e7ec;
  --s1:#2563eb; --s2:#d97706; --s3:#7c3aed; --s4:#059669; --bad:#dc2626; --good:#16a34a;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#0f1115; --card:#181b22; --fg:#e6e8ee; --muted:#98a2b3; --line:#2a2f3a;
    --s1:#60a5fa; --s2:#fbbf24; --s3:#a78bfa; --s4:#34d399; --bad:#f87171; --good:#4ade80;
  }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:16px; background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }}
h1 {{ font-size:20px; margin:0 0 4px; }}
.sub {{ color:var(--muted); margin:0 0 16px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 520px), 1fr)); gap:16px; }}
.panel {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; min-width:0; }}
.panel header {{ display:flex; justify-content:space-between; align-items:center; gap:8px; }}
.panel h2 {{ font-size:15px; margin:0; }}
.meta, .note {{ color:var(--muted); font-size:12px; margin:4px 0 8px; }}
.badge {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px; border:1px solid currentColor; }}
.badge.good {{ color:var(--good); }} .badge.bad {{ color:var(--bad); }} .badge.muted {{ color:var(--muted); }}
.stats {{ display:flex; flex-wrap:wrap; gap:6px 16px; margin-bottom:6px; }}
.stat span {{ display:block; color:var(--muted); font-size:11px; }}
.stat b {{ font-size:16px; font-variant-numeric:tabular-nums; }}
.stat.wide b {{ font-size:13px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:12px; font-size:12px; color:var(--muted); }}
.key i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:-1px; }}
svg {{ width:100%; height:190px; display:block; margin-top:6px; }}
svg .grid {{ stroke:var(--line); }}
svg .axis {{ fill:var(--muted); font-size:10px; }}
svg .threshold {{ stroke:var(--bad); stroke-width:1.5; stroke-dasharray:6 4; }}
svg .threshold-label {{ fill:var(--bad); font-size:10px; }}
</style>
</head>
<body>
<h1>{html.escape(dashboard["title"])}</h1>
<p class="sub">Time range: <b>last {dashboard["time_range_minutes"]} minutes</b> ({window.start:%Y-%m-%d %H:%M} → {window.end:%H:%M} UTC) ·
auto-refresh {dashboard["refresh_seconds"]}s · source: <code>{html.escape(source.as_posix())}</code> ·
{data["records_in_window"]} log records · generated {generated:%H:%M:%S} UTC</p>
<main class="grid">{panels}</main>
</body>
</html>
"""


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Sinh dashboard HTML 6 panel từ structured logs")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    parser.add_argument("--logs", type=Path, default=Path("data/logs.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/dashboard.html"))
    parser.add_argument("--anchor", choices=["now", "latest"], default="now", help="Mốc cuối của cửa sổ thời gian")
    parser.add_argument("--watch", action="store_true", help="Sinh lại liên tục theo refresh_seconds")
    args = parser.parse_args()

    config = load_dashboard_config(args.config)
    dashboard = config["dashboard"]
    while True:
        records = load_records(args.logs)
        window = build_window(records, dashboard["time_range_minutes"], args.anchor)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render(config, records, window, args.logs), encoding="utf-8")
        print(f"Dashboard: {args.out} ({len(records)} records, {window.start:%H:%M}-{window.end:%H:%M} UTC)")
        if not args.watch:
            return 0
        time.sleep(dashboard["refresh_seconds"])


if __name__ == "__main__":
    raise SystemExit(main())
