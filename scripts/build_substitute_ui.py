from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.lib.export_json import write_json
from scripts.lib.substitute_ui import build_substitute_ui_artifacts

DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "generated"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "generated"
DEFAULT_SETTINGS = PROJECT_ROOT / "config" / "substitute_ui_settings.json"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_substitute_ui(
    *,
    input_dir: Path,
    out_dir: Path,
    settings_path: Path,
) -> dict:
    features = _load_json(input_dir / "exercise_features.json")
    neighbors = _load_json(input_dir / "exercise_neighbors.json")
    communities = _load_json(input_dir / "exercise_communities.json")
    settings = _load_json(settings_path)

    ui_artifact, debug_artifact = build_substitute_ui_artifacts(
        features=features,
        neighbors=neighbors,
        communities=communities,
        settings=settings,
    )

    write_json(out_dir / "exercise_substitute_ui.json", ui_artifact)
    if settings.get("emitDebug", False):
        write_json(out_dir / "exercise_substitute_ui_debug.json", debug_artifact)

    return {
        "exercise_count": len(ui_artifact),
        "debug_enabled": bool(settings.get("emitDebug", False)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build UI-oriented substitute buckets from similarity artifacts")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    args = parser.parse_args()

    metrics = build_substitute_ui(
        input_dir=args.input_dir,
        out_dir=args.out,
        settings_path=args.settings,
    )
    print(f"Built substitute UI artifact for {metrics['exercise_count']} exercises.")


if __name__ == "__main__":
    main()
