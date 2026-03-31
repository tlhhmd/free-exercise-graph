"""
build_site.py

Generate app/data.json and app/vocab.json from pipeline.db or graph.ttl.
Run before deploying the static site.

Usage:
    python3 app/build_site.py                  # read from pipeline.db (local dev)
    python3 app/build_site.py --from-graph     # read from graph.ttl (CI / no DB)
    python3 app/build_site.py --out app/       # explicit output directory
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDFS, SKOS, RDF

_APP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, get_connection

_GRAPH_TTL = _PROJECT_ROOT / "graph.ttl"

FEG = Namespace("https://placeholder.url#")
_ONTOLOGY_DIR = _PROJECT_ROOT / "ontology"

_DEGREE_PRIORITY = {"PrimeMover": 0, "Synergist": 1, "Stabilizer": 2, "PassiveTarget": 3}
_DEGREE_WEIGHT = {"PrimeMover": 3.0, "Synergist": 2.0, "Stabilizer": 1.0, "PassiveTarget": 0.5}

_REGION_ALIASES = {
    "Shoulders": "shoulders",
    "Traps": "back",
    "Chest": "chest",
    "Biceps": "arms",
    "Forearms": "arms",
    "Triceps": "arms",
    "Abdominals": "core",
    "Quadriceps": "legs_front",
    "Calves": "calves",
    "LowerLeg": "calves",
    "Peroneals": "calves",
    "Shins": "calves",
    "Glutes": "glutes",
    "Hamstrings": "hamstrings",
    "LowerBack": "lower_back",
    "Lats": "back",
    "MiddleBack": "back",
    "HipFlexors": "hips",
    "Adductors": "hips",
    "Abductors": "hips",
    "Neck": "back",
}

_REGION_DISPLAY = {
    "legs_front": "Quads",
    "hamstrings": "Hamstrings",
    "glutes": "Glutes",
    "calves": "Calves",
    "core": "Core",
    "back": "Back",
    "lower_back": "Lower Back",
    "shoulders": "Shoulders",
    "chest": "Chest",
    "arms": "Arms",
    "hips": "Hips",
}

_TOKEN_NORMALIZATION = {
    "biceps": "bicep",
    "triceps": "tricep",
    "glutes": "glute",
    "quads": "quad",
    "delts": "delt",
    "shoulders": "shoulder",
    "hamstrings": "hamstring",
    "calves": "calf",
    "obliques": "oblique",
}

_QUERY_ALIASES = {
    "bicep": ["biceps brachii", "brachialis"],
    "biceps": ["biceps brachii", "brachialis"],
    "tricep": ["triceps"],
    "triceps": ["triceps"],
    "delt": ["deltoid", "shoulder"],
    "delts": ["deltoid", "shoulder"],
    "shoulder": ["shoulder", "deltoid"],
    "shoulders": ["shoulder", "deltoid"],
    "quad": ["quadriceps", "vastus", "rectus femoris"],
    "quads": ["quadriceps", "vastus", "rectus femoris"],
    "glute": ["glute"],
    "glutes": ["glute"],
    "hamstring": ["hamstring", "biceps femoris", "semitendinosus", "semimembranosus"],
    "hamstrings": ["hamstring", "biceps femoris", "semitendinosus", "semimembranosus"],
    "abs": ["rectus abdominis", "oblique", "transverse abdominis", "core"],
    "rear delt": ["posterior deltoid"],
    "rear delts": ["posterior deltoid"],
}

_PATTERN_COPY = {
    "KneeDominant": "Squat, split-squat, and lunge patterns that bias knee travel and quad demand.",
    "HipHinge": "Patterns that load the hips and posterior chain through a hinge mechanic.",
    "HorizontalPush": "Pressing patterns moving away from the torso on a horizontal line.",
    "HorizontalPull": "Rowing patterns that bring the load toward the torso.",
    "VerticalPush": "Overhead pressing patterns with upward force production.",
    "VerticalPull": "Pull-down and pull-up style patterns with vertical intent.",
    "AntiExtension": "Core patterns that resist lumbar extension and keep the trunk stacked.",
    "AntiRotation": "Core patterns that resist twisting under load or position change.",
    "AntiFlexion": "Core patterns that resist collapsing forward under load.",
    "AntiLateralFlexion": "Core patterns that resist side-bending and asymmetry.",
    "Carry": "Loaded transport patterns that challenge trunk stiffness and grip.",
    "Locomotion": "Travel-based movement patterns for conditioning and coordination.",
    "LateralLocomotion": "Side-to-side locomotion emphasizing frontal-plane movement.",
    "Rotation": "Rotational patterns that create or control trunk and hip turning.",
    "Mobility": "Low-load patterns designed to expand range of motion and control.",
}

_MODALITY_COPY = {
    "Strength": "High-tension work for force production and load tolerance.",
    "Hypertrophy": "Moderate-to-high volume work biased toward muscle growth.",
    "Power": "Fast, forceful work that prioritizes speed and intent.",
    "Plyometrics": "Elastic, reactive jumping or rebounding patterns.",
    "Cardio": "Conditioning work with sustained or repeated effort demand.",
    "Mobility": "Control and range-of-motion work with lower tissue stress.",
}


# ─── Ontology loading ─────────────────────────────────────────────────────────

def _load_ontology() -> Graph:
    g = Graph()
    for f in sorted(_ONTOLOGY_DIR.glob("*.ttl")):
        if f.name != "shapes.ttl":
            g.parse(f, format="turtle")
    return g


def _local(uri) -> str:
    return str(uri).split("#")[-1]


def _term_value(term) -> str:
    """Return the plain lexical value for pyoxigraph or rdflib terms."""
    if hasattr(term, "value"):
        return str(term.value)
    return str(term)


def _term_local(term) -> str:
    value = _term_value(term)
    return value.split("#")[-1]


def _label(g: Graph, uri) -> str:
    lbl = g.value(uri, RDFS.label)
    if lbl:
        return str(lbl)
    return _local(uri)


def _sorted_ids(ids: list[str], node_map: dict[str, dict], count_key: str = "count") -> list[str]:
    return sorted(ids, key=lambda node_id: (-node_map[node_id][count_key], node_map[node_id]["label"]))


def _pretty_local(local: str) -> str:
    text = local.replace("_", " ").replace("-", " ").replace("/", " ")
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_search_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())).strip()


def _canonicalize_search_text(text: str) -> str:
    return " ".join(
        _TOKEN_NORMALIZATION.get(token, token)
        for token in _normalize_search_text(text).split()
        if token
    )


# ─── Vocab extraction ─────────────────────────────────────────────────────────

def _build_vocab(g: Graph, counts: dict, exercises: list[dict]) -> dict:
    """Build vocab.json structure from ontology graph."""

    # Movement patterns — hierarchy with descendant rollups
    pattern_nodes: dict[str, dict] = {}
    pattern_children: dict[str | None, list[str]] = {}
    for mp in g.subjects(RDF.type, FEG.MovementPattern):
        local = _local(mp)
        broader = g.value(mp, SKOS.broader)
        parent = _local(broader) if broader else None
        pattern_nodes[local] = {
            "id": local,
            "label": _label(g, mp),
            "parent": parent,
            "exactCount": counts.get(("pattern", local), 0),
        }
        pattern_children.setdefault(parent, []).append(local)

    @lru_cache(maxsize=None)
    def pattern_total(local: str) -> int:
        return pattern_nodes[local]["exactCount"] + sum(
            pattern_total(child_id) for child_id in pattern_children.get(local, [])
        )

    patterns = []

    def emit_pattern(node_id: str, depth: int = 0) -> None:
        total = pattern_total(node_id)
        if total <= 0:
            return
        node = pattern_nodes[node_id]
        patterns.append({
            "id": node["id"],
            "label": node["label"],
            "parent": node["parent"],
            "depth": depth,
            "count": total,
            "description": _PATTERN_COPY.get(node["id"]),
        })
        for child_id in _sorted_ids(pattern_children.get(node_id, []), {
            cid: {"label": pattern_nodes[cid]["label"], "count": pattern_total(cid)}
            for cid in pattern_children.get(node_id, [])
        }):
            emit_pattern(child_id, depth + 1)

    for root_id in _sorted_ids(pattern_children.get(None, []), {
        node_id: {"label": pattern_nodes[node_id]["label"], "count": pattern_total(node_id)}
        for node_id in pattern_children.get(None, [])
    }):
        emit_pattern(root_id)

    # Joint actions — grouped by joint
    joints_map: dict[str, dict] = {}
    for ja in g.subjects(RDF.type, FEG.JointAction):
        local = _local(ja)
        broader = g.value(ja, SKOS.broader)
        if broader is None:
            continue
        joint_local = _local(broader)
        joint_label = _label(g, broader)
        if joint_local not in joints_map:
            joints_map[joint_local] = {"id": joint_local, "label": joint_label, "actions": []}
        count = counts.get(("ja", local), 0)
        if count <= 0:
            continue
        joints_map[joint_local]["actions"].append({
            "id": local,
            "label": _label(g, ja),
            "count": count,
        })
    # Also include joint groups themselves
    for jg in g.subjects(RDF.type, FEG.JointGroup):
        local = _local(jg)
        if local not in joints_map:
            joints_map[local] = {"id": local, "label": _label(g, jg), "actions": []}
    for j in joints_map.values():
        j["actions"].sort(key=lambda a: -a["count"])
    joints = sorted(joints_map.values(), key=lambda j: j["label"])

    # Training modalities
    modalities = []
    for tm in g.subjects(RDF.type, FEG.TrainingModality):
        local = _local(tm)
        count = counts.get(("modality", local), 0)
        if count <= 0:
            continue
        modalities.append({
            "id": local,
            "label": _label(g, tm),
            "count": count,
            "description": _MODALITY_COPY.get(local),
        })
    modalities.sort(key=lambda item: (-item["count"], item["label"]))

    # Equipment
    equipment = []
    for eq in g.subjects(RDF.type, FEG.Equipment):
        local = _local(eq)
        count = counts.get(("equipment", local), 0)
        if count <= 0:
            continue
        equipment.append({
            "id": local,
            "label": _label(g, eq),
            "count": count,
        })
    equipment.sort(key=lambda e: -e["count"])

    # Laterality
    laterality = []
    for lat in g.subjects(RDF.type, FEG.Laterality):
        local = _local(lat)
        count = counts.get(("laterality", local), 0)
        if count <= 0:
            continue
        laterality.append({
            "id": local,
            "label": _label(g, lat),
            "count": count,
        })
    laterality.sort(key=lambda item: (-item["count"], item["label"]))

    # Planes of motion
    planes = []
    for plane in g.subjects(RDF.type, FEG.PlaneOfMotion):
        local = _local(plane)
        count = counts.get(("plane", local), 0)
        if count <= 0:
            continue
        planes.append({
            "id": local,
            "label": _label(g, plane),
            "count": count,
        })
    planes.sort(key=lambda item: (-item["count"], item["label"]))

    # Exercise styles
    styles = []
    for style in g.subjects(RDF.type, FEG.ExerciseStyle):
        local = _local(style)
        count = counts.get(("style", local), 0)
        if count <= 0:
            continue
        styles.append({
            "id": local,
            "label": _label(g, style),
            "count": count,
        })
    styles.sort(key=lambda item: (-item["count"], item["label"]))

    # Muscle hierarchy: regions → descendants with rolled-up counts
    muscle_nodes: dict[str, dict] = {}
    muscle_children: dict[str | None, list[str]] = {}
    type_labels = {
        FEG.MuscleRegion: "region",
        FEG.MuscleGroup: "group",
        FEG.MuscleHead: "head",
        FEG.Muscle: "muscle",
    }
    node_uris = (
        set(g.subjects(RDF.type, FEG.MuscleRegion))
        | set(g.subjects(RDF.type, FEG.MuscleGroup))
        | set(g.subjects(RDF.type, FEG.MuscleHead))
        | set(g.subjects(RDF.type, FEG.Muscle))
    )
    muscle_exact_sets: dict[str, set[str]] = {}
    for exercise in exercises:
        for muscle, _degree in {tuple(item) for item in exercise["muscles"]}:
            muscle_exact_sets.setdefault(muscle, set()).add(exercise["id"])

    for node in node_uris:
        local = _local(node)
        broader = g.value(node, SKOS.broader)
        parent = _local(broader) if broader else None
        node_type = "muscle"
        for rdf_type, label in type_labels.items():
            if (node, RDF.type, rdf_type) in g:
                node_type = label
                break
        muscle_nodes[local] = {
            "id": local,
            "label": _label(g, node),
            "type": node_type,
            "parent": parent,
            "exactCount": len(muscle_exact_sets.get(local, set())),
        }
        muscle_children.setdefault(parent, []).append(local)

    @lru_cache(maxsize=None)
    def muscle_total_set(local: str) -> frozenset[str]:
        ids = set(muscle_exact_sets.get(local, set()))
        for child_id in muscle_children.get(local, []):
            ids.update(muscle_total_set(child_id))
        return frozenset(ids)

    def muscle_total(local: str) -> int:
        return len(muscle_total_set(local))

    def build_muscle_node(local: str) -> dict | None:
        total = muscle_total(local)
        if total <= 0:
            return None
        children = [
            build_muscle_node(child_id)
            for child_id in _sorted_ids(
                muscle_children.get(local, []),
                {
                    cid: {"label": muscle_nodes[cid]["label"], "count": muscle_total(cid)}
                    for cid in muscle_children.get(local, [])
                },
            )
        ]
        return {
            "id": local,
            "label": muscle_nodes[local]["label"],
            "type": muscle_nodes[local]["type"],
            "count": total,
            "children": [child for child in children if child is not None],
        }

    regions = []
    for region_id in _sorted_ids(
        [
            node_id
            for node_id, node in muscle_nodes.items()
            if node["type"] == "region" and node["parent"] is None
        ],
        {
            node_id: {"label": muscle_nodes[node_id]["label"], "count": muscle_total(node_id)}
            for node_id, node in muscle_nodes.items()
            if node["type"] == "region" and node["parent"] is None
        },
    ):
        node = build_muscle_node(region_id)
        if node is not None:
            regions.append(node)
    regions.sort(key=lambda r: -r["count"])

    return {
        "patterns": patterns,
        "joints": joints,
        "modalities": modalities,
        "equipment": equipment,
        "laterality": laterality,
        "planes": planes,
        "styles": styles,
        "muscles": {"regions": regions},
    }


# ─── Exercise data extraction ─────────────────────────────────────────────────

def _build_muscle_maps(g: Graph) -> tuple[dict[str, str], dict[str, frozenset[str]]]:
    """Return (group_level_map, ancestor_map) — mirrors build.py logic."""
    group_level_map: dict[str, str] = {}
    for group in g.subjects(FEG.useGroupLevel, None):
        if g.value(group, FEG.useGroupLevel) and str(g.value(group, FEG.useGroupLevel)).lower() == "true":
            group_name = _local(group)
            for head in g.subjects(SKOS.broader, group):
                group_level_map[_local(head)] = group_name

    # Re-implement useGroupLevel check properly
    from rdflib import Literal
    group_level_map = {}
    for group in g.subjects(FEG.useGroupLevel, Literal(True)):
        group_name = _local(group)
        for head in g.subjects(SKOS.broader, group):
            group_level_map[_local(head)] = group_name

    all_muscles = (
        set(g.subjects(RDF.type, FEG.Muscle))
        | set(g.subjects(RDF.type, FEG.MuscleRegion))
        | set(g.subjects(RDF.type, FEG.MuscleGroup))
        | set(g.subjects(RDF.type, FEG.MuscleHead))
    )

    def ancestors_of(uri) -> frozenset[str]:
        result: set[str] = set()
        queue = list(g.objects(uri, SKOS.broader))
        while queue:
            p = queue.pop()
            n = _local(p)
            if n not in result:
                result.add(n)
                queue.extend(g.objects(p, SKOS.broader))
        return frozenset(result)

    ancestor_map = {_local(m): ancestors_of(m) for m in all_muscles}
    return group_level_map, ancestor_map


def _effective_muscles(
    resolved: list, inferred: list,
    group_level_map: dict[str, str],
    ancestor_map: dict[str, frozenset[str]],
) -> list[tuple[str, str]]:
    """Union merge of resolved + inferred muscles, normalized to group level."""
    resolved_muscles = {r["value"]: r["qualifier"] for r in resolved if r["predicate"] == "muscle"}
    inferred_muscles = {r["value"]: r["qualifier"] for r in inferred if r["predicate"] == "muscle"}

    merged: list[tuple[str, str | None]] = []
    for muscle, res_deg in resolved_muscles.items():
        inf_deg = inferred_muscles.get(muscle)
        if inf_deg == "PrimeMover" and res_deg != "PrimeMover":
            merged.append((muscle, "PrimeMover"))
        else:
            merged.append((muscle, res_deg))
    for muscle, inf_deg in inferred_muscles.items():
        if muscle not in resolved_muscles:
            merged.append((muscle, inf_deg))

    # Normalize: group level + best degree dedup
    best: dict[str, str] = {}
    for muscle, degree in merged:
        if degree is None:
            continue
        muscle = group_level_map.get(muscle, muscle)
        cur = best.get(muscle)
        if cur is None or _DEGREE_PRIORITY.get(degree, 99) < _DEGREE_PRIORITY.get(cur, 99):
            best[muscle] = degree

    # Strip ancestors
    muscle_set = set(best)
    to_remove = {
        anc for m in muscle_set for anc in ancestor_map.get(m, frozenset()) if anc in muscle_set
    }
    for anc in to_remove:
        del best[anc]

    return sorted(best.items(), key=lambda x: _DEGREE_PRIORITY.get(x[1], 99))


def _collect_inferred(inferred: list, predicate: str) -> list[str]:
    return [r["value"] for r in inferred if r["predicate"] == predicate]


def _collect_resolved(resolved: list, predicate: str) -> list[str]:
    return list({r["value"] for r in resolved if r["predicate"] == predicate})


def _derive_visual_regions(muscles: list[tuple[str, str]], ancestor_map: dict[str, frozenset[str]]) -> list[str]:
    weighted: dict[str, float] = {}
    for muscle, degree in muscles:
        lineage = {muscle, *ancestor_map.get(muscle, frozenset())}
        for node in lineage:
            region = _REGION_ALIASES.get(node)
            if region:
                weighted[region] = weighted.get(region, 0.0) + _DEGREE_WEIGHT.get(degree, 0.5)
    return [
        region
        for region, _ in sorted(weighted.items(), key=lambda item: (-item[1], item[0]))
    ][:4]


def _derive_body_focus(visual_regions: list[str]) -> str:
    region_set = set(visual_regions)
    upper = {"shoulders", "chest", "arms", "back"}
    lower = {"legs_front", "hamstrings", "glutes", "calves", "hips"}
    posterior = {"back", "lower_back", "glutes", "hamstrings", "calves"}
    anterior = {"chest", "shoulders", "arms", "core", "legs_front", "hips"}

    upper_hits = len(region_set & upper)
    lower_hits = len(region_set & lower)
    posterior_hits = len(region_set & posterior)
    anterior_hits = len(region_set & anterior)

    if region_set == {"core"} or region_set <= {"core", "lower_back"}:
        return "core"
    if lower_hits and not upper_hits:
        return "lower"
    if upper_hits and not lower_hits:
        return "upper"
    if posterior_hits >= anterior_hits + 1:
        return "posterior_chain"
    if anterior_hits >= posterior_hits + 1:
        return "anterior_chain"
    return "full_body"


def _derive_spinal_load(
    patterns: list[str],
    equipment: list[str],
    modality: str | None,
    compound: bool,
    combination: bool,
    visual_regions: list[str],
) -> str:
    pattern_set = set(patterns)
    equipment_set = set(equipment)
    if modality == "Mobility" or pattern_set & {"Mobility", "SoftTissue"}:
        return "low"
    if pattern_set & {"TrunkStability", "AntiExtension", "AntiRotation", "AntiFlexion", "AntiLateralFlexion"}:
        return "low"
    if combination:
        return "high"
    if "HipHinge" in pattern_set and equipment_set & {"Barbell", "TrapBar", "HeavySandbag", "Kettlebell"}:
        return "high"
    if pattern_set & {"Carry"} or equipment_set & {"HeavySandbag", "Sandbag"}:
        return "high"
    if compound or "lower_back" in visual_regions:
        return "medium"
    return "low"


def _derive_explosiveness(modality: str | None, patterns: list[str]) -> str:
    if modality in {"Power", "Plyometrics"}:
        return "high"
    if modality == "Cardio" or set(patterns) & {"Locomotion", "LateralLocomotion", "Rotation"}:
        return "medium"
    return "low"


def _derive_skill_level(
    laterality: str | None,
    compound: bool,
    combination: bool,
    equipment: list[str],
) -> str:
    equipment_set = set(equipment)
    advanced_equipment = {"GymnasticRings", "Clubbell", "Macebell", "Landmine", "ParalletteBar", "ClimbingRope", "IndianClub"}
    if combination or laterality in {"Contralateral", "Ipsilateral"} or equipment_set & advanced_equipment:
        return "advanced"
    if laterality == "Unilateral" or compound or equipment_set & {"Barbell", "Kettlebell", "TrapBar", "Dumbbell", "EZBar"}:
        return "intermediate"
    return "beginner"


def _derive_builder_roles(patterns: list[str], visual_regions: list[str]) -> list[str]:
    roles: list[str] = []
    pattern_set = set(patterns)

    if pattern_set & {"KneeDominant", "Squat", "Lunge", "SplitSquat"}:
        roles.append("squat")
    if "HipHinge" in pattern_set:
        roles.append("hinge")
    if pattern_set & {"Push", "VerticalPush", "HorizontalPush"}:
        roles.append("push")
    if pattern_set & {"Pull", "VerticalPull", "HorizontalPull"}:
        roles.append("pull")
    if pattern_set & {"TrunkStability", "AntiExtension", "AntiRotation", "AntiFlexion", "AntiLateralFlexion", "IsometricHold"}:
        roles.append("core")
    if "Carry" in pattern_set:
        roles.append("carry")
    if pattern_set & {"Locomotion", "LateralLocomotion"}:
        roles.append("locomotion")
    if pattern_set & {"Mobility", "SoftTissue"}:
        roles.append("mobility")
    if not roles and "core" in visual_regions:
        roles.append("core")

    return sorted(set(roles))


def _derive_movement_family(patterns: list[str]) -> str:
    pattern_set = set(patterns)
    families = [
        ("squat", {"KneeDominant", "Squat", "Lunge", "SplitSquat"}),
        ("hinge", {"HipHinge"}),
        ("push", {"Push", "VerticalPush", "HorizontalPush"}),
        ("pull", {"Pull", "VerticalPull", "HorizontalPull"}),
        ("core", {"TrunkStability", "AntiExtension", "AntiRotation", "AntiFlexion", "AntiLateralFlexion", "IsometricHold"}),
        ("carry", {"Carry"}),
        ("locomotion", {"Locomotion", "LateralLocomotion"}),
        ("rotation", {"Rotation"}),
        ("mobility", {"Mobility", "SoftTissue"}),
    ]
    for family, members in families:
        if pattern_set & members:
            return family
    return "general"


def _derive_practical_note(exercise: dict) -> str:
    family = exercise["movementFamily"]
    if family == "hinge":
        return "Best when you want posterior-chain stimulus and hip-dominant loading."
    if family == "squat":
        return "Useful when you want knee-dominant leg work that is easy to place in a session."
    if family == "push":
        return "Good for building pressing volume without needing a full program view."
    if family == "pull":
        return "Useful for balancing out pressing-heavy training with upper-back work."
    if family == "core":
        return "A solid trunk slot when you want visible core demand without guessing."
    if family == "carry":
        return "Great when you want conditioning, grip, and trunk stiffness in one choice."
    if exercise["explosiveness"] == "high":
        return "Best used when speed and intent matter more than sheer fatigue."
    if exercise["skillLevel"] == "beginner":
        return "Simple enough to slot into a plan quickly without much technical setup."
    return "A flexible option when you want a broadly useful pattern match."


def _derive_why_hints(exercise: dict) -> list[str]:
    hints: list[str] = []
    if exercise["patterns"]:
        hints.append(f"Movement pattern: {_pretty_local(exercise['patterns'][0])}.")
    top_prime = [m for m, degree in exercise["muscles"] if degree == "PrimeMover"][:2]
    if top_prime:
        hints.append(f"Prime movers: {', '.join(_pretty_local(m) for m in top_prime)}.")
    elif exercise["muscles"]:
        hints.append(f"Muscle emphasis: {_pretty_local(exercise['muscles'][0][0])}.")
    if exercise["modality"]:
        hints.append(f"Training modality: {_pretty_local(exercise['modality'])}.")
    if exercise["equipment"]:
        hints.append(f"Equipment: {', '.join(_pretty_local(item) for item in exercise['equipment'][:2])}.")
    return hints[:4]


def _search_aliases(exercise: dict) -> list[str]:
    aliases: set[str] = set()
    labels = [_canonicalize_search_text(_pretty_local(muscle)) for muscle, _ in exercise["muscles"]]

    if any("bicep brachii" in label or "brachialis" in label for label in labels):
        aliases.update({"bicep", "biceps"})
    if any("tricep" in label for label in labels):
        aliases.update({"tricep", "triceps"})
    if any("deltoid" in label for label in labels):
        aliases.update({"delt", "delts", "shoulder", "shoulders"})
    if any("vastus" in label or "rectus femoris" in label for label in labels):
        aliases.update({"quad", "quads"})
    if any("glute" in label for label in labels):
        aliases.update({"glute", "glutes"})
    if any(term in label for label in labels for term in ("bicep femoris", "semitendinosus", "semimembranosus")):
        aliases.update({"hamstring", "hamstrings"})
    if any(term in label for label in labels for term in ("rectus abdominis", "oblique", "transverse abdominis")):
        aliases.add("abs")
    return sorted(aliases)


def _build_search_index(exercise: dict) -> dict:
    muscles = [_canonicalize_search_text(_pretty_local(muscle)) for muscle, _ in exercise["muscles"]]
    muscle_entries = [
        {
            "label": _canonicalize_search_text(_pretty_local(muscle)),
            "degree": degree,
        }
        for muscle, degree in exercise["muscles"]
    ]
    patterns = [_canonicalize_search_text(_pretty_local(pattern)) for pattern in exercise["patterns"]]
    primary_ja = [_canonicalize_search_text(_pretty_local(item)) for item in exercise["primaryJA"]]
    supporting_ja = [_canonicalize_search_text(_pretty_local(item)) for item in exercise["supportingJA"]]
    equipment = [_canonicalize_search_text(_pretty_local(item)) for item in exercise["equipment"]]
    planes = [_canonicalize_search_text(_pretty_local(item)) for item in exercise["planes"]]
    styles = [_canonicalize_search_text(_pretty_local(item)) for item in exercise["style"]]
    regions = [_canonicalize_search_text(_REGION_DISPLAY.get(region, _pretty_local(region))) for region in exercise["visualRegions"]]
    aliases = _search_aliases(exercise)
    modality = _canonicalize_search_text(_pretty_local(exercise["modality"])) if exercise["modality"] else ""
    laterality = _canonicalize_search_text(_pretty_local(exercise["laterality"])) if exercise["laterality"] else ""
    name = _canonicalize_search_text(exercise["name"])
    body_focus = _canonicalize_search_text(exercise["bodyFocus"])
    movement_family = _canonicalize_search_text(exercise["movementFamily"])
    alias_targets = sorted({
        _canonicalize_search_text(target)
        for alias in aliases
        for target in _QUERY_ALIASES.get(alias, [])
    })
    all_terms = sorted(set(filter(None, [
        name,
        modality,
        laterality,
        body_focus,
        movement_family,
        *patterns,
        *primary_ja,
        *supporting_ja,
        *equipment,
        *planes,
        *styles,
        *muscles,
        *regions,
        *aliases,
    ])))
    return {
        "name": name,
        "modality": modality,
        "laterality": laterality,
        "bodyFocus": body_focus,
        "movementFamily": movement_family,
        "patterns": patterns,
        "primaryJA": primary_ja,
        "supportingJA": supporting_ja,
        "equipment": equipment,
        "planes": planes,
        "styles": styles,
        "muscles": muscles,
        "muscleEntries": muscle_entries,
        "regions": regions,
        "aliases": aliases,
        "aliasTargets": alias_targets,
        "all": " | ".join(all_terms),
    }


def _decorate_exercises(exercises: list[dict], ancestor_map: dict[str, frozenset[str]]) -> list[dict]:
    for exercise in exercises:
        muscles = [(m, d) for m, d in exercise["muscles"]]
        visual_regions = _derive_visual_regions(muscles, ancestor_map)
        body_focus = _derive_body_focus(visual_regions)
        spinal_load = _derive_spinal_load(
            exercise["patterns"],
            exercise["equipment"],
            exercise["modality"],
            exercise["compound"],
            exercise["combination"],
            visual_regions,
        )
        explosiveness = _derive_explosiveness(exercise["modality"], exercise["patterns"])
        skill_level = _derive_skill_level(
            exercise["laterality"],
            exercise["compound"],
            exercise["combination"],
            exercise["equipment"],
        )
        builder_roles = _derive_builder_roles(exercise["patterns"], visual_regions)
        movement_family = _derive_movement_family(exercise["patterns"])
        top_muscles = [_pretty_local(muscle) for muscle, _ in muscles[:3]]
        top_patterns = [_pretty_local(pattern) for pattern in exercise["patterns"][:2]]

        exercise["visualRegions"] = visual_regions
        exercise["bodyFocus"] = body_focus
        exercise["spinalLoad"] = spinal_load
        exercise["explosiveness"] = explosiveness
        exercise["skillLevel"] = skill_level
        exercise["builderRoles"] = builder_roles
        exercise["movementFamily"] = movement_family
        exercise["practicalNote"] = _derive_practical_note({
            **exercise,
            "movementFamily": movement_family,
        })
        exercise["compareAttributes"] = {
            "bodyFocus": body_focus,
            "spinalLoad": spinal_load,
            "explosiveness": explosiveness,
            "skillLevel": skill_level,
            "builderRoles": builder_roles,
            "movementFamily": movement_family,
            "topMuscles": top_muscles,
            "topPatterns": top_patterns,
            "modality": _pretty_local(exercise["modality"]) if exercise["modality"] else None,
            "laterality": _pretty_local(exercise["laterality"]) if exercise["laterality"] else None,
            "combination": exercise["combination"],
            "compound": exercise["compound"],
        }
        exercise["whyHints"] = _derive_why_hints(exercise)
        exercise["searchIndex"] = _build_search_index(exercise)
    return exercises


def _build_exercises(conn, group_level_map, ancestor_map) -> tuple[list[dict], dict]:
    entities = conn.execute(
        "SELECT entity_id, display_name FROM entities ORDER BY entity_id"
    ).fetchall()

    counts: dict[tuple[str, str], int] = {}
    exercises = []

    for row in entities:
        eid = row["entity_id"]
        name = row["display_name"]

        resolved = conn.execute(
            "SELECT predicate, value, qualifier FROM resolved_claims WHERE entity_id = ?",
            (eid,),
        ).fetchall()
        inferred = conn.execute(
            "SELECT predicate, value, qualifier FROM inferred_claims WHERE entity_id = ?",
            (eid,),
        ).fetchall()

        muscles = _effective_muscles(resolved, inferred, group_level_map, ancestor_map)
        patterns = _collect_inferred(inferred, "movement_pattern")
        primary_ja = _collect_inferred(inferred, "primary_joint_action")
        supporting_ja = _collect_inferred(inferred, "supporting_joint_action")
        equipment = _collect_resolved(resolved, "equipment")
        laterality = next((r["value"] for r in inferred if r["predicate"] == "laterality"), None)
        modality_list = _collect_inferred(inferred, "training_modality")
        planes = _collect_inferred(inferred, "plane_of_motion")
        style = _collect_inferred(inferred, "exercise_style")
        compound = next((r["value"] for r in inferred if r["predicate"] == "is_compound"), None)
        combination = next((r["value"] for r in inferred if r["predicate"] == "is_combination"), None)

        # Accumulate counts for vocab
        for m, _ in muscles:
            counts[("muscle", m)] = counts.get(("muscle", m), 0) + 1
        for p in patterns:
            counts[("pattern", p)] = counts.get(("pattern", p), 0) + 1
        for ja in set(primary_ja) | set(supporting_ja):
            counts[("ja", ja)] = counts.get(("ja", ja), 0) + 1
        for eq in equipment:
            counts[("equipment", eq)] = counts.get(("equipment", eq), 0) + 1
        if modality_list:
            counts[("modality", modality_list[0])] = counts.get(("modality", modality_list[0]), 0) + 1
        if laterality:
            counts[("laterality", laterality)] = counts.get(("laterality", laterality), 0) + 1
        for plane in planes:
            counts[("plane", plane)] = counts.get(("plane", plane), 0) + 1
        for style_item in style:
            counts[("style", style_item)] = counts.get(("style", style_item), 0) + 1

        exercises.append({
            "id": eid,
            "name": name,
            "muscles": [[m, d] for m, d in muscles],
            "patterns": patterns,
            "primaryJA": primary_ja,
            "supportingJA": supporting_ja,
            "equipment": equipment,
            "laterality": laterality,
            "modality": modality_list[0] if modality_list else None,
            "planes": planes,
            "style": style,
            "compound": compound == "true",
            "combination": combination == "true",
        })

    return exercises, counts


# ─── From-graph path ──────────────────────────────────────────────────────────

def _build_exercises_from_graph(graph_path: Path) -> tuple[list[dict], dict]:
    """Read exercise data directly from graph.ttl via pyoxigraph bulk SPARQL."""
    import pyoxigraph as ox

    FEG_NS = "https://placeholder.url#"
    print(f"  Loading {graph_path.name} into store...")
    store = ox.Store()
    store.load(graph_path.read_bytes(), format=ox.RdfFormat.TURTLE)

    def local(node) -> str:
        return _term_local(node)

    def sparql(q: str):
        return store.query(q)

    # Bulk queries — one pass per property type
    print("  Querying exercises...")
    ex_rows = sparql(f"""
        PREFIX feg: <{FEG_NS}> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT ?ex ?label ?eid WHERE {{
            ?ex a feg:Exercise ; rdfs:label ?label ; feg:legacySourceId ?eid .
        }} ORDER BY ?eid
    """)
    ex_index: dict[str, dict] = {}
    for row in ex_rows:
        uri = _term_value(row["ex"])
        ex_index[uri] = {
            "id": _term_value(row["eid"]),
            "name": _term_value(row["label"]),
            "muscles": [], "patterns": [], "primaryJA": [], "supportingJA": [],
            "equipment": [], "laterality": None, "modality": None, "planes": [],
            "style": [], "compound": False, "combination": False,
        }

    def bulk(q: str, key: str, multi: bool = True):
        for row in sparql(q):
            uri = _term_value(row["ex"])
            if uri not in ex_index:
                continue
            val = local(row[key])
            if multi:
                ex_index[uri][key].append(val)
            else:
                ex_index[uri][key] = val

    print("  Querying muscles...")
    for row in sparql(f"""
        PREFIX feg: <{FEG_NS}>
        SELECT ?ex ?muscle ?degree WHERE {{
            ?ex feg:hasInvolvement ?inv . ?inv feg:muscle ?muscle ; feg:degree ?degree .
        }}
    """):
        uri = _term_value(row["ex"])
        if uri in ex_index:
            ex_index[uri]["muscles"].append([local(row["muscle"]), local(row["degree"])])

    print("  Querying patterns, joint actions, equipment...")
    for prop, key in [
        ("movementPattern", "patterns"),
        ("primaryJointAction", "primaryJA"),
        ("supportingJointAction", "supportingJA"),
        ("equipment", "equipment"),
        ("planeOfMotion", "planes"),
        ("exerciseStyle", "style"),
    ]:
        for row in sparql(f"PREFIX feg: <{FEG_NS}> SELECT ?ex ?v WHERE {{ ?ex feg:{prop} ?v }}"):
            uri = _term_value(row["ex"])
            if uri in ex_index:
                ex_index[uri][key].append(local(row["v"]))

    for prop, key in [("laterality", "laterality"), ("trainingModality", "modality")]:
        for row in sparql(f"PREFIX feg: <{FEG_NS}> SELECT ?ex ?v WHERE {{ ?ex feg:{prop} ?v }}"):
            uri = _term_value(row["ex"])
            if uri in ex_index:
                ex_index[uri][key] = local(row["v"])

    for prop, key in [("isCompound", "compound"), ("isCombination", "combination")]:
        for row in sparql(f"PREFIX feg: <{FEG_NS}> SELECT ?ex ?v WHERE {{ ?ex feg:{prop} ?v }}"):
            uri = _term_value(row["ex"])
            if uri in ex_index:
                ex_index[uri][key] = _term_value(row["v"]).lower() == "true"

    # Sort muscles by degree priority
    for ex in ex_index.values():
        ex["muscles"].sort(key=lambda m: _DEGREE_PRIORITY.get(m[1], 99))

    exercises = sorted(ex_index.values(), key=lambda e: e["id"])

    # Build counts from graph data
    counts: dict[tuple[str, str], int] = {}
    for ex in exercises:
        for m, _ in ex["muscles"]:
            counts[("muscle", m)] = counts.get(("muscle", m), 0) + 1
        for p in ex["patterns"]:
            counts[("pattern", p)] = counts.get(("pattern", p), 0) + 1
        for ja in set(ex["primaryJA"]) | set(ex["supportingJA"]):
            counts[("ja", ja)] = counts.get(("ja", ja), 0) + 1
        for eq in ex["equipment"]:
            counts[("equipment", eq)] = counts.get(("equipment", eq), 0) + 1
        if ex["modality"]:
            counts[("modality", ex["modality"])] = counts.get(("modality", ex["modality"]), 0) + 1
        if ex["laterality"]:
            counts[("laterality", ex["laterality"])] = counts.get(("laterality", ex["laterality"]), 0) + 1
        for plane in ex["planes"]:
            counts[("plane", plane)] = counts.get(("plane", plane), 0) + 1
        for style_item in ex["style"]:
            counts[("style", style_item)] = counts.get(("style", style_item), 0) + 1

    return exercises, counts


# ─── Main ─────────────────────────────────────────────────────────────────────

def generate(
    out_dir: Path = _APP_DIR,
    db_path: Path = DB_PATH,
    from_graph: bool = False,
    graph_path: Path = _GRAPH_TTL,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading ontology...")
    g = _load_ontology()
    group_level_map, ancestor_map = _build_muscle_maps(g)

    if from_graph:
        print(f"Building exercise data from {graph_path.name}...")
        exercises, counts = _build_exercises_from_graph(graph_path)
    else:
        print("Building exercise data from pipeline.db...")
        conn = get_connection(db_path)
        exercises, counts = _build_exercises(conn, group_level_map, ancestor_map)
        conn.close()

    exercises = _decorate_exercises(exercises, ancestor_map)

    print("Building vocabulary...")
    vocab = _build_vocab(g, counts, exercises)

    data_path = out_dir / "data.json"
    vocab_path = out_dir / "vocab.json"

    data_path.write_text(json.dumps(exercises, separators=(",", ":")), encoding="utf-8")
    vocab_path.write_text(json.dumps(vocab, separators=(",", ":")), encoding="utf-8")

    import gzip
    data_gz = len(gzip.compress(data_path.read_bytes()))
    vocab_gz = len(gzip.compress(vocab_path.read_bytes()))

    print(f"Wrote {data_path} ({len(exercises)} exercises, {data_gz//1024} KB gzipped)")
    print(f"Wrote {vocab_path} ({vocab_gz//1024} KB gzipped)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate static site data")
    parser.add_argument("--out", type=Path, default=_APP_DIR)
    parser.add_argument("--from-graph", action="store_true",
                        help="Read from graph.ttl instead of pipeline.db (used in CI)")
    parser.add_argument("--graph", type=Path, default=_GRAPH_TTL,
                        help="Path to graph.ttl (default: project root)")
    args = parser.parse_args()
    generate(out_dir=args.out, from_graph=args.from_graph, graph_path=args.graph)


if __name__ == "__main__":
    main()
