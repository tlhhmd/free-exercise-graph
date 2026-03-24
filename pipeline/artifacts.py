"""
pipeline/artifacts.py

Helpers for writing durable pipeline artifacts outside SQLite.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent

ARTIFACTS_DIR = _HERE / "artifacts"
EXPORTS_DIR = _HERE / "exports"
RELEASES_DIR = _HERE / "releases"


def utc_timestamp(compact: bool = True) -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d-%H%M%S") if compact else now.isoformat()


def slugify_component(value: str | None, *, default: str = "unknown") -> str:
    text = (value or "").strip().lower()
    if not text:
        return default
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or default


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_timestamped_dir(base_dir: Path, *parts: str) -> Path:
    components = [utc_timestamp()]
    components.extend(slugify_component(part) for part in parts if part)
    return ensure_dir(base_dir / "-".join(components))


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=json_default))
    return path

