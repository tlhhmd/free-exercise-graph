"""
telemetry.py — Step-level timing and memory profiling for the pipeline.

Usage:
    from telemetry import PipelineRun

    run = PipelineRun("ingest")
    with run.step("morph-KGC", triples_before=len(g)):
        g = morph_kgc.materialize(...)
    run.finish()          # prints summary table + writes JSON report
"""

import json
import os
import resource
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from subprocess import check_output
from typing import Optional

SOURCE_DIR = Path(__file__).resolve().parent
RUNS_DIR = SOURCE_DIR / "runs"

_COL_LABEL = 42
_COL_WALL = 8
_COL_CPU = 8
_COL_MEM = 10
_COL_TRIPLES = 12

_HEADER = (
    f"{'step':<{_COL_LABEL}} {'wall(s)':>{_COL_WALL}} {'cpu(s)':>{_COL_CPU}}"
    f" {'rss(MB)':>{_COL_MEM}} {'triples':>{_COL_TRIPLES}}"
)
_SEP = "-" * len(_HEADER)


def _rss_mb() -> float:
    """Current process RSS in MB. ru_maxrss is bytes on Linux, pages on macOS."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / 1024 / 1024  # bytes → MB
    return usage / 1024  # kB → MB


def _git_sha() -> str:
    try:
        return check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


@dataclass
class StepRecord:
    label: str
    wall_s: float
    cpu_s: float
    rss_delta_mb: float
    triples_delta: Optional[int]


@dataclass
class PipelineRun:
    name: str
    run_id: str = field(init=False)
    git_sha: str = field(init=False)
    steps: list[StepRecord] = field(default_factory=list)
    _started_at: float = field(init=False)
    _cpu_started_at: float = field(init=False)

    def __post_init__(self):
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.git_sha = _git_sha()
        self._started_at = time.perf_counter()
        self._cpu_started_at = time.process_time()
        print(_SEP)
        print(f"Pipeline: {self.name}  run={self.run_id}  git={self.git_sha}")
        print(_SEP)
        print(_HEADER)
        print(_SEP)

    @contextmanager
    def step(self, label: str, triples_before: Optional[int] = None):
        """Context manager that times the block and prints a live metric row."""
        print(f"  → {label}", flush=True)
        rss_before = _rss_mb()
        t_wall = time.perf_counter()
        t_cpu = time.process_time()
        try:
            yield
        finally:
            wall_s = time.perf_counter() - t_wall
            cpu_s = time.process_time() - t_cpu
            rss_delta = _rss_mb() - rss_before
            triples_delta: Optional[int] = None  # caller sets via send() pattern — see note below

            # triples_delta injected via the _triples_delta sentinel attribute on the generator
            # We use a simpler approach: callers pass triples_before and triples_after via wrapper
            record = StepRecord(
                label=label,
                wall_s=wall_s,
                cpu_s=cpu_s,
                rss_delta_mb=rss_delta,
                triples_delta=triples_delta,
            )
            self.steps.append(record)
            self._print_row(record)

    @contextmanager
    def step_graph(self, label: str, graph, *, triples_attr: str = "__len__"):
        """Like step(), but automatically computes triples delta from an rdflib Graph."""
        print(f"  → {label}", flush=True)
        before = len(graph)
        rss_before = _rss_mb()
        t_wall = time.perf_counter()
        t_cpu = time.process_time()
        try:
            yield
        finally:
            wall_s = time.perf_counter() - t_wall
            cpu_s = time.process_time() - t_cpu
            rss_delta = _rss_mb() - rss_before
            after = len(graph)
            record = StepRecord(
                label=label,
                wall_s=wall_s,
                cpu_s=cpu_s,
                rss_delta_mb=rss_delta,
                triples_delta=after - before,
            )
            self.steps.append(record)
            self._print_row(record)

    def record(
        self,
        label: str,
        wall_s: float,
        cpu_s: float,
        rss_delta_mb: float,
        triples_delta: Optional[int] = None,
    ) -> StepRecord:
        """Add a pre-measured step (for cases where timing is done externally)."""
        r = StepRecord(label, wall_s, cpu_s, rss_delta_mb, triples_delta)
        self.steps.append(r)
        self._print_row(r)
        return r

    def _print_row(self, r: StepRecord):
        triples_str = f"{r.triples_delta:+,}" if r.triples_delta is not None else ""
        rss_str = f"{r.rss_delta_mb:+.1f}" if r.rss_delta_mb != 0 else "—"
        print(
            f"{r.label:<{_COL_LABEL}} {r.wall_s:>{_COL_WALL}.2f}"
            f" {r.cpu_s:>{_COL_CPU}.2f} {rss_str:>{_COL_MEM}}"
            f" {triples_str:>{_COL_TRIPLES}}",
            flush=True,
        )

    def finish(self) -> Path:
        """Print summary and write the JSON run report. Returns path to report."""
        total_wall = time.perf_counter() - self._started_at
        total_cpu = time.process_time() - self._cpu_started_at

        print(_SEP)
        print(
            f"{'TOTAL':<{_COL_LABEL}} {total_wall:>{_COL_WALL}.2f}"
            f" {total_cpu:>{_COL_CPU}.2f}"
        )
        print(_SEP)

        report = {
            "run_id": self.run_id,
            "pipeline": self.name,
            "git_sha": self.git_sha,
            "total_wall_s": round(total_wall, 3),
            "total_cpu_s": round(total_cpu, 3),
            "steps": [
                {
                    "label": s.label,
                    "wall_s": round(s.wall_s, 3),
                    "cpu_s": round(s.cpu_s, 3),
                    "rss_delta_mb": round(s.rss_delta_mb, 2),
                    "triples_delta": s.triples_delta,
                }
                for s in self.steps
            ],
        }

        RUNS_DIR.mkdir(exist_ok=True)
        report_path = RUNS_DIR / f"{self.run_id}_{self.name}.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"\nReport: {report_path}")
        return report_path
