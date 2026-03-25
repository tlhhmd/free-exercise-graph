"""
feg_site.py

Generate site/data.json and site/vocab.json from pipeline.db or graph.ttl.
Run before deploying the static site.

Usage:
    python3 feg_site.py                        # read from pipeline.db (local dev)
    python3 feg_site.py --from-graph           # read from graph.ttl (CI / no DB)
    python3 feg_site.py --out site/            # explicit output directory
"""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDFS, SKOS, RDF

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, get_connection

_GRAPH_TTL = _PROJECT_ROOT / "graph.ttl"

FEG = Namespace("https://placeholder.url#")
_ONTOLOGY_DIR = _PROJECT_ROOT / "ontology"

_DEGREE_PRIORITY = {"PrimeMover": 0, "Synergist": 1, "Stabilizer": 2, "PassiveTarget": 3}


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


# ─── Vocab extraction ─────────────────────────────────────────────────────────

def _build_vocab(g: Graph, counts: dict) -> dict:
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
            "exactCount": counts.get(("muscle", local), 0),
        }
        muscle_children.setdefault(parent, []).append(local)

    @lru_cache(maxsize=None)
    def muscle_total(local: str) -> int:
        return muscle_nodes[local]["exactCount"] + sum(
            muscle_total(child_id) for child_id in muscle_children.get(local, [])
        )

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
        style = _collect_inferred(inferred, "exercise_style")
        compound = next((r["value"] for r in inferred if r["predicate"] == "is_compound"), None)
        combination = next((r["value"] for r in inferred if r["predicate"] == "is_combination"), None)

        # Accumulate counts for vocab
        for m, _ in muscles:
            counts[("muscle", m)] = counts.get(("muscle", m), 0) + 1
        for p in patterns:
            counts[("pattern", p)] = counts.get(("pattern", p), 0) + 1
        for ja in primary_ja:
            counts[("ja", ja)] = counts.get(("ja", ja), 0) + 1
        for eq in equipment:
            counts[("equipment", eq)] = counts.get(("equipment", eq), 0) + 1
        if modality_list:
            counts[("modality", modality_list[0])] = counts.get(("modality", modality_list[0]), 0) + 1

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
            "equipment": [], "laterality": None, "modality": None,
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
        for ja in ex["primaryJA"]:
            counts[("ja", ja)] = counts.get(("ja", ja), 0) + 1
        for eq in ex["equipment"]:
            counts[("equipment", eq)] = counts.get(("equipment", eq), 0) + 1
        if ex["modality"]:
            counts[("modality", ex["modality"])] = counts.get(("modality", ex["modality"]), 0) + 1

    return exercises, counts


# ─── Main ─────────────────────────────────────────────────────────────────────

def generate(
    out_dir: Path = _PROJECT_ROOT / "site",
    db_path: Path = DB_PATH,
    from_graph: bool = False,
    graph_path: Path = _GRAPH_TTL,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading ontology...")
    g = _load_ontology()

    if from_graph:
        print(f"Building exercise data from {graph_path.name}...")
        exercises, counts = _build_exercises_from_graph(graph_path)
    else:
        print("Building exercise data from pipeline.db...")
        group_level_map, ancestor_map = _build_muscle_maps(g)
        conn = get_connection(db_path)
        exercises, counts = _build_exercises(conn, group_level_map, ancestor_map)
        conn.close()

    print("Building vocabulary...")
    vocab = _build_vocab(g, counts)

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
    parser.add_argument("--out", type=Path, default=_PROJECT_ROOT / "site")
    parser.add_argument("--from-graph", action="store_true",
                        help="Read from graph.ttl instead of pipeline.db (used in CI)")
    parser.add_argument("--graph", type=Path, default=_GRAPH_TTL,
                        help="Path to graph.ttl (default: project root)")
    args = parser.parse_args()
    generate(out_dir=args.out, from_graph=args.from_graph, graph_path=args.graph)


if __name__ == "__main__":
    main()
