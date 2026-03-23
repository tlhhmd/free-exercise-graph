#!/usr/bin/env python3
"""
graph_health.py — Productized Graph Health report built on top of quality_report.csv.

Reads the CSV produced by validate.py and generates a stakeholder-readable report
summarising failure counts by dimension, pass rates, and imperfect exercises.

Output formats:
  stdout    — Markdown (default)
  --md      — write Markdown to file
  --html    — write HTML to file

Usage:
    python3 sources/free-exercise-db/graph_health.py
    python3 sources/free-exercise-db/graph_health.py --md report.md --html report.html
    python3 sources/free-exercise-db/graph_health.py --csv path/to/quality_report.csv
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = SOURCE_DIR / "quality_report.csv"
DEFAULT_MD = SOURCE_DIR / "quality_report.md"
DEFAULT_HTML = SOURCE_DIR / "quality_report.html"

FAIL_DIMS = ["validity", "uniqueness", "integrity"]
WARN_DIMS = ["timeliness", "consistency", "completeness"]
ALL_DIMS = FAIL_DIMS + WARN_DIMS
SEVERITY = {d: "FAIL" for d in FAIL_DIMS} | {d: "WARN" for d in WARN_DIMS}


# ── Data loading ──────────────────────────────────────────────────────────────


def _load(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run validate.py first.", file=sys.stderr)
        sys.exit(1)
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _stats(rows: list[dict]) -> dict:
    total = len(rows)
    dim_counts = {d: sum(1 for r in rows if r[d] != "pass") for d in ALL_DIMS}
    perfect = sum(1 for r in rows if all(r[d] == "pass" for d in ALL_DIMS))
    imperfect = [r for r in rows if any(r[d] != "pass" for d in ALL_DIMS)]
    return {
        "total": total,
        "perfect": perfect,
        "imperfect_count": total - perfect,
        "dim_counts": dim_counts,
        "imperfect": imperfect,
    }


# ── Markdown renderer ─────────────────────────────────────────────────────────


def _render_md(rows: list[dict], stats: dict, generated: str) -> str:
    total = stats["total"]
    perfect = stats["perfect"]
    imperfect_count = stats["imperfect_count"]
    dim_counts = stats["dim_counts"]

    lines = []
    lines.append("# Graph Health Report")
    lines.append(f"\n_Generated: {generated}_")

    lines.append("\n---\n")
    lines.append("## Summary\n")
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| Total exercises | {total} |")
    lines.append(f"| Perfect (all pass) | {perfect} ({perfect/total*100:.1f}%) |")
    lines.append(f"| With warnings or failures | {imperfect_count} ({imperfect_count/total*100:.1f}%) |")

    lines.append("\n---\n")
    lines.append("## Dimensions\n")
    lines.append("| Dimension | Severity | Affected | Pass rate |")
    lines.append("|---|---|---|---|")
    for d in ALL_DIMS:
        n = dim_counts[d]
        sev = SEVERITY[d]
        rate = (total - n) / total * 100
        lines.append(f"| {d} | {sev} | {n} | {rate:.1f}% |")

    if stats["imperfect"]:
        lines.append("\n---\n")
        lines.append("## Imperfect Exercises\n")
        for r in stats["imperfect"]:
            flags = " ".join(
                f"`[{r[d].upper()}] {d}`" for d in ALL_DIMS if r[d] != "pass"
            )
            lines.append(f"**{r['name']}** — {flags}")
            if r["issues"]:
                for issue in r["issues"].split("; "):
                    lines.append(f"- {issue}")
            lines.append("")

    return "\n".join(lines)


# ── HTML renderer ─────────────────────────────────────────────────────────────


def _render_html(rows: list[dict], stats: dict, generated: str) -> str:
    total = stats["total"]
    perfect = stats["perfect"]
    imperfect_count = stats["imperfect_count"]
    dim_counts = stats["dim_counts"]

    STATUS_COLOR = {"pass": "#27ae60", "fail": "#e74c3c", "warn": "#e67e22"}

    def badge(status: str) -> str:
        color = STATUS_COLOR.get(status, "#888")
        return (
            f'<span style="background:{color};color:#fff;padding:2px 7px;'
            f'border-radius:3px;font-size:0.8em;font-weight:bold">'
            f"{status.upper()}</span>"
        )

    dim_rows = ""
    for d in ALL_DIMS:
        n = dim_counts[d]
        rate = (total - n) / total * 100
        sev = SEVERITY[d]
        sev_color = STATUS_COLOR["fail"] if sev == "FAIL" else STATUS_COLOR["warn"]
        dim_rows += (
            f"<tr><td>{d}</td>"
            f'<td><span style="color:{sev_color};font-weight:bold">{sev}</span></td>'
            f"<td>{n}</td>"
            f"<td>{rate:.1f}%</td></tr>\n"
        )

    imperfect_rows = ""
    for r in stats["imperfect"]:
        cells = "".join(
            f"<td style='text-align:center'>{badge(r[d])}</td>" for d in ALL_DIMS
        )
        issues_html = ""
        if r["issues"]:
            items = "".join(f"<li>{i}</li>" for i in r["issues"].split("; "))
            issues_html = f"<ul style='margin:4px 0 0 0;font-size:0.85em;color:#666'>{items}</ul>"
        imperfect_rows += (
            f"<tr><td><strong>{r['name']}</strong>{issues_html}</td>{cells}</tr>\n"
        )

    dim_headers = "".join(f"<th>{d}</th>" for d in ALL_DIMS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Graph Health Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 1100px; margin: 40px auto; padding: 0 20px; color: #222; }}
  h1   {{ border-bottom: 3px solid #222; padding-bottom: 8px; }}
  h2   {{ margin-top: 2em; color: #444; }}
  .meta {{ color: #888; font-size: 0.9em; margin-top: -8px; }}
  .cards {{ display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }}
  .card  {{ background: #f5f5f5; border-radius: 6px; padding: 16px 24px;
             min-width: 160px; text-align: center; }}
  .card .value {{ font-size: 2em; font-weight: bold; }}
  .card .label {{ font-size: 0.85em; color: #666; margin-top: 4px; }}
  table  {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th     {{ background: #f0f0f0; font-weight: 600; }}
  tr:nth-child(even) {{ background: #fafafa; }}
</style>
</head>
<body>
<h1>Graph Health Report</h1>
<p class="meta">Generated: {generated}</p>

<h2>Summary</h2>
<div class="cards">
  <div class="card">
    <div class="value">{total}</div>
    <div class="label">Total exercises</div>
  </div>
  <div class="card">
    <div class="value" style="color:#27ae60">{perfect}</div>
    <div class="label">Perfect ({perfect/total*100:.1f}%)</div>
  </div>
  <div class="card">
    <div class="value" style="color:#e67e22">{imperfect_count}</div>
    <div class="label">With issues ({imperfect_count/total*100:.1f}%)</div>
  </div>
</div>

<h2>Dimensions</h2>
<table>
  <thead><tr><th>Dimension</th><th>Severity</th><th>Affected</th><th>Pass rate</th></tr></thead>
  <tbody>{dim_rows}</tbody>
</table>

<h2>Imperfect Exercises ({imperfect_count})</h2>
<table>
  <thead><tr><th>Exercise</th>{dim_headers}</tr></thead>
  <tbody>{imperfect_rows}</tbody>
</table>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Graph Health report from quality_report.csv.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Input CSV path")
    parser.add_argument("--md", nargs="?", const=str(DEFAULT_MD), help="Write Markdown to file")
    parser.add_argument("--html", nargs="?", const=str(DEFAULT_HTML), help="Write HTML to file")
    args = parser.parse_args()

    rows = _load(Path(args.csv))
    stats = _stats(rows)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md = _render_md(rows, stats, generated)
    html = _render_html(rows, stats, generated) if args.html else None

    # Always print Markdown to stdout
    print(md)

    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
        print(f"\nMarkdown written to: {args.md}", file=sys.stderr)

    if args.html:
        Path(args.html).write_text(html, encoding="utf-8")
        print(f"HTML written to: {args.html}", file=sys.stderr)


if __name__ == "__main__":
    main()
