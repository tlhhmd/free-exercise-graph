from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.lib.community import detect_communities
from scripts.lib.export_json import export_similarity_artifacts
from scripts.lib.feature_normalize import normalize_features
from scripts.lib.rdf_extract import extract_features
from scripts.lib.similarity import build_similarity_outputs

DEFAULT_INPUT = PROJECT_ROOT / "graph.ttl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "generated"
DEFAULT_WEIGHTS = PROJECT_ROOT / "config" / "similarity_weights.json"
DEFAULT_SETTINGS = PROJECT_ROOT / "config" / "build_settings.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_similarity_graph(
    input_path: Path,
    out_dir: Path,
    weights_path: Path,
    settings_path: Path,
) -> dict:
    raw_features = extract_features(input_path)
    normalized_features = normalize_features(raw_features)
    weights = _load_json(weights_path)
    settings = _load_json(settings_path)

    edges, neighbors, metrics = build_similarity_outputs(normalized_features, weights, settings)
    communities, community_by_exercise = detect_communities(
        [feature.id for feature in normalized_features],
        edges,
    )

    for exercise_id, neighbor_list in neighbors.items():
        for neighbor in neighbor_list:
            neighbor["communityId"] = community_by_exercise.get(neighbor["id"])
        neighbors[exercise_id] = neighbor_list

    features_payload = [feature.to_export_dict() for feature in normalized_features]
    metrics = {
        **metrics,
        "community_count": len(communities),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "inputPath": str(input_path),
        "minScore": settings.get("minScore"),
        "topNeighborsPerExercise": settings.get("topNeighborsPerExercise"),
        "weights": weights,
    }

    export_similarity_artifacts(
        out_dir,
        features=features_payload,
        edges=edges,
        neighbors=neighbors,
        communities=communities,
        metrics=metrics,
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exercise similarity graph artifacts")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    args = parser.parse_args()

    metrics = build_similarity_graph(
        input_path=args.input,
        out_dir=args.out,
        weights_path=args.weights,
        settings_path=args.settings,
    )
    print(
        "Built similarity graph for "
        f"{metrics['exercise_count']} exercises, "
        f"{metrics['edge_count']} edges, "
        f"{metrics['community_count']} communities."
    )


if __name__ == "__main__":
    main()
