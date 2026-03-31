from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def export_similarity_artifacts(
    out_dir: Path,
    *,
    features: list[dict],
    edges: list[dict],
    neighbors: dict[str, list[dict]],
    communities: dict[str, dict],
    metrics: dict,
) -> None:
    write_json(out_dir / "exercise_features.json", features)
    write_json(out_dir / "exercise_similarity_edges.json", edges)
    write_json(out_dir / "exercise_neighbors.json", neighbors)
    write_json(out_dir / "exercise_communities.json", communities)
    write_json(out_dir / "build_metrics.json", metrics)
