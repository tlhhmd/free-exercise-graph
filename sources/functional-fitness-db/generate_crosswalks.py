#!/usr/bin/env python3
"""
generate_crosswalks.py — Programmatically generate crosswalk CSVs for the
Functional Fitness Exercise Database by matching source strings against
existing FEG ontology vocabulary.

Produces three crosswalk files in mappings/:
  - muscle_crosswalk.csv       (source string → feg: local name)
  - equipment_crosswalk.csv    (source string → feg: local name)
  - movement_pattern_crosswalk.csv  (source string → feg: local name + target_property)

Status values:
  matched   — auto-matched to an existing ontology term
  gap       — no match found; needs manual resolution or a new vocabulary ADR
  drop      — known no-op value (Other, Unsorted*, None, etc.)

Usage:
    python3 sources/functional-fitness-db/generate_crosswalks.py
    python3 sources/functional-fitness-db/generate_crosswalks.py --show-gaps
"""

import argparse
import csv
import re
import sys
from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS
from rdflib.namespace import SKOS

SOURCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from constants import FEG_NS

FEG = Namespace(FEG_NS)
ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
RAW_CSV = SOURCE_DIR / "raw" / "Exercises.csv"
MAPPINGS_DIR = SOURCE_DIR / "mappings"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def normalize(s: str) -> str:
    """Lowercase, strip whitespace and punctuation for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


def local_name(uri) -> str:
    """Extract local name from a URIRef."""
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.split("/")[-1]


def load_graph(*ttl_files) -> Graph:
    g = Graph()
    for f in ttl_files:
        g.parse(f, format="turtle")
    return g


def build_label_index(g: Graph, rdf_type) -> dict[str, str]:
    """
    Returns {normalized_label: feg_local_name} for all individuals of rdf_type.
    Indexes rdfs:label, skos:prefLabel, and skos:altLabel.
    """
    index = {}
    for subj in g.subjects(RDF.type, rdf_type):
        ln = local_name(subj)
        for pred in (RDFS.label, SKOS.prefLabel, SKOS.altLabel):
            for label in g.objects(subj, pred):
                index[normalize(str(label))] = ln
    return index


def match(source_val: str, index: dict[str, str]) -> str | None:
    """Try normalized exact match, then singular fallback. Returns feg local name or None."""
    nval = normalize(source_val)
    if nval in index:
        return index[nval]
    # Try stripping trailing 's' (plural → singular)
    if nval.endswith("s") and nval[:-1] in index:
        return index[nval[:-1]]
    return None


def read_source_values(col_indices: list[int]) -> list[str]:
    """Read unique non-empty source values from given column indices."""
    values = set()
    with open(RAW_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    for row in rows[16:]:  # data starts at row 17 (0-indexed: 16)
        for i in col_indices:
            if len(row) > i and row[i].strip():
                values.add(row[i].strip())
    return sorted(values)


def write_crosswalk(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    matched = sum(1 for r in rows if r.get("status") == "matched")
    gaps = sum(1 for r in rows if r.get("status") == "gap")
    drops = sum(1 for r in rows if r.get("status") == "drop")
    print(f"  {path.name}: {matched} matched, {gaps} gap(s), {drops} drop(s)")


# ─── Muscle crosswalk ─────────────────────────────────────────────────────────

# Explicit muscle overrides — source strings that can't auto-match due to
# label differences, typos in source data, or ambiguous anatomical names.
MUSCLE_OVERRIDES = {
    # Typo in source ("Mediais" → "Medialis")
    "vastusmediais":              ("VastusMedialis",   "feg:MuscleHead"),
    # Source uses "Quadriceps Femoris" (formal) → our vocab has "Quadriceps" (colloquial)
    "quadricepsfemoris":          ("Quadriceps",       "feg:MuscleGroup"),
    # Source uses "Anterior/Lateral/Posterior/Medial Deltoids" (plural anatomical)
    "anteriordeltoids":           ("AnteriorDeltoid",  "feg:MuscleHead"),
    "lateraldeltoids":            ("LateralDeltoid",   "feg:MuscleHead"),
    "posteriordeltoids":          ("PosteriorDeltoid", "feg:MuscleHead"),
    "medialdeltoids":             ("LateralDeltoid",   "feg:MuscleHead"),  # no medial deltoid head; lateral is closest
    # Region-level overrides
    "back":                       ("MiddleBack",       "feg:MuscleRegion"),  # ambiguous; MiddleBack is safest default
    "hipflexors":                 ("Iliopsoas",        "feg:MuscleGroup"),
    "shins":                      ("Shins",            "feg:MuscleRegion"),  # gap — needs vocab addition
    # Now in vocab (ADR-081)
    "anconeus":                   ("Anconeus",                "feg:MuscleGroup"),
    "extensordigitorumlongus":    ("ExtensorDigitorumLongus", "feg:MuscleGroup"),
    "extensorhallucislongus":     ("ExtensorHallucisLongus",  "feg:MuscleGroup"),
    "tibialistposterior":         ("TibialisPosterior",       "feg:MuscleGroup"),
    "tibialposterior":            ("TibialisPosterior",       "feg:MuscleGroup"),
}


def generate_muscle_crosswalk():
    """Fields 5 (Target Muscle Group → MuscleRegion), 6-8 (Prime/Secondary/Tertiary → MuscleHead/Group)."""
    g = load_graph(ONTOLOGY_DIR / "muscles.ttl", ONTOLOGY_DIR / "ontology.ttl")

    region_index = build_label_index(g, FEG.MuscleRegion)
    group_index  = build_label_index(g, FEG.MuscleGroup)
    head_index   = build_label_index(g, FEG.MuscleHead)
    all_muscle_index = {**region_index, **group_index, **head_index}

    # col 5 = Target Muscle Group (→ MuscleRegion), cols 6/7/8 = muscle names (→ any level)
    muscle_vals  = read_source_values([6, 7, 8])
    region_vals  = read_source_values([5])

    rows = []

    def resolve_muscle(val, index, fallback_class=""):
        nval = normalize(val)
        # Check explicit overrides first
        if nval in MUSCLE_OVERRIDES:
            result = MUSCLE_OVERRIDES[nval]
            if result is None:
                return "", "", "gap"
            feg_local, target_class = result
            status = "matched"
            return feg_local, target_class, status
        feg_local = match(val, index)
        if feg_local:
            if feg_local in head_index.values():
                target_class = "feg:MuscleHead"
            elif feg_local in group_index.values():
                target_class = "feg:MuscleGroup"
            else:
                target_class = "feg:MuscleRegion"
            return feg_local, target_class, "matched"
        return "", fallback_class, "gap"

    # Target Muscle Group → MuscleRegion
    for val in region_vals:
        feg_local, target_class, status = resolve_muscle(val, region_index, "feg:MuscleRegion")
        rows.append({
            "source_value": val,
            "feg_local_name": feg_local,
            "target_class": target_class or "feg:MuscleRegion",
            "status": status,
        })

    # Prime/Secondary/Tertiary → best muscle match
    for val in muscle_vals:
        feg_local, target_class, status = resolve_muscle(val, all_muscle_index)
        rows.append({
            "source_value": val,
            "feg_local_name": feg_local,
            "target_class": target_class,
            "status": status,
        })

    # Deduplicate (a value could appear in both region and muscle cols)
    seen = set()
    deduped = []
    for r in rows:
        if r["source_value"] not in seen:
            seen.add(r["source_value"])
            deduped.append(r)

    write_crosswalk(
        MAPPINGS_DIR / "muscle_crosswalk.csv",
        sorted(deduped, key=lambda r: r["source_value"]),
        ["source_value", "feg_local_name", "target_class", "status"],
    )
    return deduped


# ─── Equipment crosswalk ──────────────────────────────────────────────────────

EQUIPMENT_DROPS = {"none"}

def generate_equipment_crosswalk():
    """Fields 9 + 11 (Primary + Secondary Equipment), flattened."""
    g = load_graph(ONTOLOGY_DIR / "equipment.ttl", ONTOLOGY_DIR / "ontology.ttl")
    index = build_label_index(g, FEG.Equipment)

    vals = read_source_values([9, 11])
    rows = []
    for val in vals:
        if normalize(val) in EQUIPMENT_DROPS:
            rows.append({"source_value": val, "feg_local_name": "", "status": "drop"})
            continue
        feg_local = match(val, index)
        rows.append({
            "source_value": val,
            "feg_local_name": feg_local or "",
            "status": "matched" if feg_local else "gap",
        })

    write_crosswalk(
        MAPPINGS_DIR / "equipment_crosswalk.csv",
        sorted(rows, key=lambda r: r["source_value"]),
        ["source_value", "feg_local_name", "status"],
    )
    return rows


# ─── Movement pattern crosswalk ───────────────────────────────────────────────

MOVEMENT_DROPS = {"other", "unsorted"}

# Explicit overrides for source values that won't auto-match due to label differences
MOVEMENT_OVERRIDES = {
    # source normalized → (feg_local_name, target_property)
    "antilateralflexion":  ("AntiLateralFlexion", "feg:movementPattern"),
    "antiextension":       ("AntiExtension",       "feg:movementPattern"),
    "antiflexion":         ("AntiFlexion",          "feg:movementPattern"),
    "antirotational":      ("AntiRotation",         "feg:movementPattern"),
    "rotational":          ("Rotation",             "feg:movementPattern"),
    "spinalrotational":    ("SpinalRotation",       "feg:jointAction"),
    "spinalflexion":       ("SpinalFlexion",        "feg:jointAction"),
    "spinalextension":     ("SpinalExtension",      "feg:jointAction"),
    "laterallocomotion":   ("LateralLocomotion",    "feg:movementPattern"),
    "loadedcarry":         ("Carry",                "feg:movementPattern"),
    "isometrichold":       ("IsometricHold",        "feg:movementPattern"),
    "horizontaladduction": ("ShoulderHorizontalAdduction", "feg:jointAction"),
    "hipdominant":         ("HipHinge",             "feg:movementPattern"),  # mapped to closest FEG concept
    "locomotion":          ("Locomotion",           "feg:movementPattern"),
    "lateralflexion":      ("SpinalLateralFlexion", "feg:jointAction"),
    "shoulderscapularplaneelevation": ("ShoulderFlexion", "feg:jointAction"),  # closest match
    "ankledorsiflexion":   ("Dorsiflexion",         "feg:jointAction"),
    "ankleplanterflexion": ("Plantarflexion",       "feg:jointAction"),
    "ankleplantarflexion": ("Plantarflexion",       "feg:jointAction"),
}

# Joint action values from the source that map to feg:jointAction
JOINT_ACTION_PATTERNS = {
    "feg:jointAction"
}

def generate_movement_pattern_crosswalk():
    """Fields 21-23 (Movement Pattern #1/2/3) — routes to feg:movementPattern or feg:jointAction."""
    mp_graph = load_graph(ONTOLOGY_DIR / "movement_patterns.ttl", ONTOLOGY_DIR / "ontology.ttl")
    ja_graph = load_graph(ONTOLOGY_DIR / "joint_actions.ttl", ONTOLOGY_DIR / "ontology.ttl")

    mp_index = build_label_index(mp_graph, FEG.MovementPattern)
    ja_index = build_label_index(ja_graph, FEG.JointAction)

    vals = read_source_values([21, 22, 23])
    rows = []

    for val in vals:
        nval = normalize(val)

        if nval in MOVEMENT_DROPS:
            rows.append({
                "source_value": val,
                "feg_local_name": "",
                "target_property": "",
                "status": "drop",
                "notes": "",
            })
            continue

        # Check explicit overrides first
        if nval in MOVEMENT_OVERRIDES:
            feg_local, target_prop = MOVEMENT_OVERRIDES[nval]
            # Mark gaps that still need ADRs
            rows.append({
                "source_value": val,
                "feg_local_name": feg_local,
                "target_property": target_prop,
                "status": "matched",
                "notes": "",
            })
            continue

        # Try movement pattern index
        feg_local = match(val, mp_index)
        if feg_local:
            rows.append({
                "source_value": val,
                "feg_local_name": feg_local,
                "target_property": "feg:movementPattern",
                "status": "matched",
                "notes": "",
            })
            continue

        # Try joint action index
        feg_local = match(val, ja_index)
        if feg_local:
            rows.append({
                "source_value": val,
                "feg_local_name": feg_local,
                "target_property": "feg:jointAction",
                "status": "matched",
                "notes": "",
            })
            continue

        # Unresolved gap
        rows.append({
            "source_value": val,
            "feg_local_name": "",
            "target_property": "",
            "status": "gap",
            "notes": "no match in movement_patterns.ttl or joint_actions.ttl",
        })

    write_crosswalk(
        MAPPINGS_DIR / "movement_pattern_crosswalk.csv",
        sorted(rows, key=lambda r: r["source_value"]),
        ["source_value", "feg_local_name", "target_property", "status", "notes"],
    )
    return rows


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate FEG crosswalk CSVs from source vocabulary.")
    parser.add_argument("--show-gaps", action="store_true", help="Print all gap rows after generation")
    args = parser.parse_args()

    print("Generating crosswalks...\n")
    muscle_rows   = generate_muscle_crosswalk()
    equipment_rows = generate_equipment_crosswalk()
    movement_rows  = generate_movement_pattern_crosswalk()

    if args.show_gaps:
        all_gaps = [
            ("muscle",   r) for r in muscle_rows   if r["status"] == "gap"
        ] + [
            ("equipment", r) for r in equipment_rows if r["status"] == "gap"
        ] + [
            ("movement",  r) for r in movement_rows  if r["status"] == "gap"
        ]
        if all_gaps:
            print(f"\nGaps requiring resolution ({len(all_gaps)}):")
            for domain, r in all_gaps:
                print(f"  [{domain}] {r['source_value']}")
        else:
            print("\nNo gaps — all source values matched.")


if __name__ == "__main__":
    main()
