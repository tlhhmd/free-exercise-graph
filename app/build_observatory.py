"""
build_observatory.py

Generate app/observatory.json — per-exercise pipeline-replay data for the
Builder View in the static app.

Only curated exercises are included (hand-picked for narrative value).
Run after build_site.py, before deploying.

Usage:
    python3 app/build_observatory.py
    python3 app/build_observatory.py --out app/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import get_connection

# ── Curated exercise set ───────────────────────────────────────────────────────
# Each entry has a narrative that the Builder View displays above the stepper.

_CURATED: list[dict] = [
    {
        "entity_id": "dead_bug",
        "narrative": (
            "Three source records across two datasets disagreed on laterality — "
            "one said Contralateral (right arm + left leg move together), another "
            "said Unilateral. Both are defensible. The reconciler deferred rather "
            "than guess. The LLM enrichment pass resolved it to Contralateral "
            "and added TransverseAbdominis and ErectorSpinae — muscles no source "
            "had mentioned."
        ),
    },
    {
        "entity_id": "romanian_deadlift",
        "narrative": (
            "Three source records (two from different datasets) agreed on the "
            "core facts: HipHinge pattern, posterior-chain muscles, bilateral. "
            "Consensus resolution handled most fields. Equipment was unioned "
            "(Barbell + Kettlebell both preserved). A clean multi-source merge."
        ),
    },
    {
        "entity_id": "crunch",
        "narrative": (
            "Three records — Cable Crunch, Exercise Ball Crunch, and Bodyweight "
            "Crunch — clustered into one canonical entity. The pipeline added "
            "CoreFlexion as the movement pattern (a concept added specifically "
            "for spinal-flexion isolation exercises, distinct from the joint "
            "action SpinalFlexion). Equipment was unioned across all variants."
        ),
    },
    {
        "entity_id": "ffdb_Double_Kettlebell_Gorilla_Row",
        "narrative": (
            "Single source record. The LLM consistently placed HipHinge in the "
            "wrong field (supporting_joint_action instead of movement_pattern). "
            "The exercise genuinely IS both HorizontalPull and HipHinge. "
            "Resolution: a human override claim was inserted directly into "
            "resolved_claims to correct the field assignment."
        ),
    },
    {
        "entity_id": "bent_over_row",
        "narrative": (
            "Three records across two datasets: Bent Over Barbell Row, "
            "Barbell Bent Over Row, and Sandbag Bent Over Row. Equipment "
            "was unioned (Barbell + Sandbag). Muscles reached consensus "
            "across sources. A typical clean multi-source merge for a "
            "well-documented exercise."
        ),
    },
]

# ── Predicate display labels ───────────────────────────────────────────────────

_PREDICATE_LABELS: dict[str, str] = {
    "muscle": "Muscle",
    "movement_pattern": "Movement Pattern",
    "primary_joint_action": "Primary Joint Action",
    "supporting_joint_action": "Supporting Joint Action",
    "equipment": "Equipment",
    "laterality": "Laterality",
    "is_compound": "Compound",
    "is_combination": "Combination",
    "modality": "Modality",
    "exercise_style": "Exercise Style",
    "plane_of_motion": "Plane of Motion",
    "laterality": "Laterality",
}

_METHOD_LABELS: dict[str, str] = {
    "consensus": "Consensus",
    "union": "Union",
    "conservative": "Conservative",
    "coverage_gap": "Coverage gap",
    "human_override": "Human override",
    "defer": "Deferred",
}

_SOURCE_LABELS: dict[str, str] = {
    "free-exercise-db": "free-exercise-db",
    "functional-fitness-db": "functional-fitness-db",
}


def _prettify(value: str) -> str:
    """CamelCase → Title Case with spaces."""
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return s.replace("_", " ").strip()


def _predicate_label(predicate: str) -> str:
    return _PREDICATE_LABELS.get(predicate, _prettify(predicate))


def _format_claim(predicate: str, value: str, qualifier: str | None) -> str:
    """Return a human-readable claim string."""
    val = _prettify(value)
    if qualifier:
        return f"{val} ({_prettify(qualifier)})"
    return val


# ── Per-stage queries ──────────────────────────────────────────────────────────


def _stage_sources(conn, entity_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT es.source, es.source_id, sr.display_name, es.confidence
        FROM entity_sources es
        JOIN source_records sr
          ON es.source = sr.source AND es.source_id = sr.source_id
        WHERE es.entity_id = ?
        ORDER BY es.source, sr.display_name
        """,
        (entity_id,),
    ).fetchall()

    records = []
    for r in rows:
        source, source_id, display_name, confidence = r
        # Collect claims for this source record
        claims = conn.execute(
            """
            SELECT predicate, value, qualifier
            FROM source_claims
            WHERE source = ? AND source_id = ?
            ORDER BY predicate, value
            """,
            (source, source_id),
        ).fetchall()
        records.append(
            {
                "source": _SOURCE_LABELS.get(source, source),
                "display_name": display_name,
                "confidence": confidence,
                "claims": [
                    {
                        "predicate": _predicate_label(c[0]),
                        "value": _format_claim(c[0], c[1], c[2]),
                    }
                    for c in claims
                ],
            }
        )
    return records


def _stage_identity(conn, entity_id: str) -> dict:
    sources_rows = conn.execute(
        "SELECT DISTINCT source FROM entity_sources WHERE entity_id = ?",
        (entity_id,),
    ).fetchall()
    source_names = [_SOURCE_LABELS.get(r[0], r[0]) for r in sources_rows]

    record_count = conn.execute(
        "SELECT COUNT(*) FROM entity_sources WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()[0]

    possible = conn.execute(
        """
        SELECT pm.entity_id_b, e.display_name, pm.score, pm.status
        FROM possible_matches pm
        JOIN entities e ON pm.entity_id_b = e.entity_id
        WHERE pm.entity_id_a = ?
        ORDER BY pm.score DESC
        LIMIT 3
        """,
        (entity_id,),
    ).fetchall()

    return {
        "record_count": record_count,
        "sources": source_names,
        "cross_source": len(source_names) > 1,
        "possible_matches": [
            {
                "display_name": r[1],
                "score": round(r[2], 2),
                "status": r[3],
            }
            for r in possible
        ],
    }


def _stage_reconcile(conn, entity_id: str) -> dict:
    resolved = conn.execute(
        """
        SELECT predicate, value, qualifier, resolution_method
        FROM resolved_claims
        WHERE entity_id = ?
        ORDER BY resolution_method, predicate, value
        """,
        (entity_id,),
    ).fetchall()

    # Group by method
    by_method: dict[str, list[dict]] = {}
    for r in resolved:
        method = r[3]
        label = _METHOD_LABELS.get(method, method)
        by_method.setdefault(label, []).append(
            {
                "predicate": _predicate_label(r[0]),
                "value": _format_claim(r[0], r[1], r[2]),
            }
        )

    conflicts = conn.execute(
        "SELECT predicate, description, status FROM conflicts WHERE entity_id = ?",
        (entity_id,),
    ).fetchall()

    return {
        "by_method": by_method,
        "method_counts": {k: len(v) for k, v in by_method.items()},
        "conflicts": [
            {
                "predicate": _predicate_label(r[0]),
                "description": r[1],
                "status": r[2],
            }
            for r in conflicts
        ],
    }


def _stage_enrich(conn, entity_id: str) -> dict:
    stamp = conn.execute(
        "SELECT model, enriched_at FROM enrichment_stamps WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()

    inferred = conn.execute(
        """
        SELECT predicate, value, qualifier
        FROM inferred_claims
        WHERE entity_id = ?
        ORDER BY predicate, value
        """,
        (entity_id,),
    ).fetchall()

    # "Notable" = inferred values NOT present in resolved_claims for the same predicate
    resolved_values = set(
        conn.execute(
            "SELECT predicate, value FROM resolved_claims WHERE entity_id = ?",
            (entity_id,),
        ).fetchall()
    )

    notable = [
        {
            "predicate": _predicate_label(r[0]),
            "value": _format_claim(r[0], r[1], r[2]),
        }
        for r in inferred
        if (r[0], r[1]) not in resolved_values
    ]

    warnings = conn.execute(
        "SELECT predicate, stripped_value FROM enrichment_warnings WHERE entity_id = ?",
        (entity_id,),
    ).fetchall()

    return {
        "model": stamp[0] if stamp else None,
        "enriched_at": stamp[1][:10] if stamp else None,
        "inferred_count": len(inferred),
        "notable": notable[:12],  # cap display
        "warnings": [
            {
                "predicate": _predicate_label(r[0]),
                "stripped_value": _prettify(r[1]),
            }
            for r in warnings
        ],
    }


# ── Main ───────────────────────────────────────────────────────────────────────


def build_observatory(out_dir: Path) -> None:
    conn = get_connection()
    result = []

    for spec in _CURATED:
        entity_id = spec["entity_id"]
        row = conn.execute(
            "SELECT display_name FROM entities WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        if not row:
            print(f"  WARNING: entity_id not found: {entity_id}", file=sys.stderr)
            continue

        record = {
            "entity_id": entity_id,
            "display_name": row[0],
            "narrative": spec["narrative"],
            "stages": {
                "sources": _stage_sources(conn, entity_id),
                "identity": _stage_identity(conn, entity_id),
                "reconcile": _stage_reconcile(conn, entity_id),
                "enrich": _stage_enrich(conn, entity_id),
            },
        }
        result.append(record)
        print(f"  {entity_id}: {row[0]}")

    out_path = out_dir / "observatory.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {len(result)} exercises → {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate observatory.json for Builder View")
    parser.add_argument("--out", default=str(_APP_DIR), help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Building observatory.json...")
    build_observatory(out_dir)


if __name__ == "__main__":
    main()
