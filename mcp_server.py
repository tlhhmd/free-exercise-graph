#!/usr/bin/env python3
"""
mcp_server.py — MCP server for the free-exercise-graph knowledge graph.

Loads graph.ttl into pyoxigraph in-process and exposes 5 tools via the
MCP protocol. No external services, no Docker.

Usage:
    python3 mcp_server.py

Claude Desktop config (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "free-exercise-graph": {
          "command": "python3",
          "args": ["/path/to/free-exercise-graph/mcp_server.py"]
        }
      }
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pyoxigraph as ox
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from constants import FEG_NS

GRAPH_TTL = PROJECT_ROOT / "graph.ttl"

FEG = FEG_NS

# ── Store ─────────────────────────────────────────────────────────────────────


def _load_store() -> ox.Store:
    store = ox.Store()
    store.load(GRAPH_TTL.read_bytes(), format=ox.RdfFormat.TURTLE)
    return store


# Loaded once at startup — MCP servers are long-lived processes.
_store: ox.Store | None = None


def store() -> ox.Store:
    global _store
    if _store is None:
        _store = _load_store()
    return _store


# ── Query helpers ─────────────────────────────────────────────────────────────


def _local(node: ox.NamedNode) -> str:
    """Return the local name from a feg: URI."""
    return node.value.split("#", 1)[1]


def _str(term: Any) -> str:
    """Return the string value of a Literal or NamedNode."""
    if isinstance(term, ox.Literal):
        return term.value
    if isinstance(term, ox.NamedNode):
        return term.value
    return str(term)


def _sparql(query: str) -> list[ox.QuerySolution]:
    return list(store().query(query))


# ── Tool implementations ───────────────────────────────────────────────────────


def search_exercises(
    muscles: list[str] | None = None,
    movement_pattern: str | None = None,
    equipment: str | None = None,
    degree: str | None = None,
) -> list[dict]:
    """Return exercises matching the given filters (all filters ANDed)."""
    filters: list[str] = []

    if muscles:
        for m in muscles:
            muscle_uri = f"<{FEG}{m}>"
            if degree:
                filters.append(
                    f"?ex feg:hasInvolvement ?inv_{m} . "
                    f"?inv_{m} feg:muscle {muscle_uri} ; feg:degree feg:{degree} ."
                )
            else:
                filters.append(
                    f"?ex feg:hasInvolvement ?inv_{m} . ?inv_{m} feg:muscle {muscle_uri} ."
                )

    if movement_pattern:
        filters.append(f"?ex feg:movementPattern feg:{movement_pattern} .")

    if equipment:
        filters.append(f"?ex feg:equipment feg:{equipment} .")

    if not filters:
        # No filters — return a brief listing (limit to avoid overwhelming output)
        query = f"""
        PREFIX feg: <{FEG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?ex ?label WHERE {{
          ?ex a feg:Exercise ; rdfs:label ?label .
        }} ORDER BY ?label LIMIT 50
        """
    else:
        filter_block = "\n  ".join(filters)
        query = f"""
        PREFIX feg: <{FEG}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?ex ?label WHERE {{
          ?ex a feg:Exercise ; rdfs:label ?label .
          {filter_block}
        }} ORDER BY ?label
        """

    rows = _sparql(query)

    results = []
    for r in rows:
        ex_local = _local(r["ex"])
        # Fetch involvement summary for each match
        inv_rows = _sparql(f"""
        PREFIX feg: <{FEG}>
        SELECT ?muscle ?degree WHERE {{
          feg:{ex_local} feg:hasInvolvement ?inv .
          ?inv feg:muscle ?muscle ; feg:degree ?degree .
        }}
        """)
        involvements = [
            {"muscle": _local(i["muscle"]), "degree": _local(i["degree"])}
            for i in inv_rows
        ]
        results.append({
            "id": ex_local,
            "name": _str(r["label"]),
            "involvements": involvements,
        })

    return results


def get_exercise(exercise_id: str) -> dict | None:
    """Return the full record for one exercise by its feg: local name."""
    query = f"""
    PREFIX feg: <{FEG}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?label ?eq ?compound ?combination ?laterality WHERE {{
      feg:{exercise_id} a feg:Exercise ; rdfs:label ?label .
      OPTIONAL {{ feg:{exercise_id} feg:equipment ?eq }}
      OPTIONAL {{ feg:{exercise_id} feg:isCompound ?compound }}
      OPTIONAL {{ feg:{exercise_id} feg:isCombination ?combination }}
      OPTIONAL {{ feg:{exercise_id} feg:laterality ?laterality }}
    }}
    """
    rows = _sparql(query)
    if not rows:
        return None

    r = rows[0]
    result: dict = {
        "id": exercise_id,
        "name": _str(r["label"]),
    }
    if r["eq"]:
        result["equipment"] = _local(r["eq"])
    if r["compound"]:
        result["is_compound"] = r["compound"].value == "true"
    if r["combination"]:
        result["is_combination"] = r["combination"].value == "true"
    if r["laterality"]:
        result["laterality"] = _local(r["laterality"])

    # Involvements
    inv_rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    SELECT ?muscle ?degree WHERE {{
      feg:{exercise_id} feg:hasInvolvement ?inv .
      ?inv feg:muscle ?muscle ; feg:degree ?degree .
    }}
    """)
    result["muscle_involvements"] = [
        {"muscle": _local(i["muscle"]), "degree": _local(i["degree"])}
        for i in inv_rows
    ]

    # Movement patterns
    mp_rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    SELECT ?mp WHERE {{ feg:{exercise_id} feg:movementPattern ?mp }}
    """)
    result["movement_patterns"] = [_local(r["mp"]) for r in mp_rows]

    # Joint actions
    pja_rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    SELECT ?ja WHERE {{ feg:{exercise_id} feg:primaryJointAction ?ja }}
    """)
    result["primary_joint_actions"] = [_local(r["ja"]) for r in pja_rows]

    sja_rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    SELECT ?ja WHERE {{ feg:{exercise_id} feg:supportingJointAction ?ja }}
    """)
    result["supporting_joint_actions"] = [_local(r["ja"]) for r in sja_rows]

    # Training modalities
    tm_rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    SELECT ?tm WHERE {{ feg:{exercise_id} feg:trainingModality ?tm }}
    """)
    result["training_modalities"] = [_local(r["tm"]) for r in tm_rows]

    return result


def find_substitutions(
    exercise_id: str,
    equipment_available: list[str] | None = None,
) -> list[dict]:
    """
    Return exercises that share the same primary movement pattern(s) and have
    overlapping PrimeMover muscles with the reference exercise.

    Optionally filter to equipment in equipment_available (feg: local names).
    Exercises with no equipment (bodyweight) are always included when filtering.
    """
    # Get reference exercise's primary movement patterns and prime movers
    mp_rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    SELECT ?mp WHERE {{ feg:{exercise_id} feg:movementPattern ?mp }}
    """)
    patterns = [_local(r["mp"]) for r in mp_rows]

    pm_rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    SELECT ?muscle WHERE {{
      feg:{exercise_id} feg:hasInvolvement ?inv .
      ?inv feg:muscle ?muscle ; feg:degree feg:PrimeMover .
    }}
    """)
    prime_movers = {_local(r["muscle"]) for r in pm_rows}

    if not patterns and not prime_movers:
        return []

    # Build pattern filter
    if patterns:
        pattern_values = " ".join(f"feg:{p}" for p in patterns)
        pattern_filter = f"VALUES ?mp {{ {pattern_values} }} ?candidate feg:movementPattern ?mp ."
    else:
        pattern_filter = ""

    # Build equipment filter
    if equipment_available:
        eq_values = ", ".join(f"feg:{e}" for e in equipment_available)
        eq_filter = f"""
        OPTIONAL {{ ?candidate feg:equipment ?eq }}
        FILTER (!BOUND(?eq) || ?eq IN ({eq_values}))
        """
    else:
        eq_filter = "OPTIONAL { ?candidate feg:equipment ?eq }"

    query = f"""
    PREFIX feg: <{FEG}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?candidate ?label WHERE {{
      ?candidate a feg:Exercise ; rdfs:label ?label .
      FILTER(?candidate != feg:{exercise_id})
      {pattern_filter}
      {eq_filter}
    }} ORDER BY ?label
    """
    rows = _sparql(query)

    results = []
    for r in rows:
        cand_id = _local(r["candidate"])

        # Check PrimeMover overlap
        cand_pm_rows = _sparql(f"""
        PREFIX feg: <{FEG}>
        SELECT ?muscle WHERE {{
          feg:{cand_id} feg:hasInvolvement ?inv .
          ?inv feg:muscle ?muscle ; feg:degree feg:PrimeMover .
        }}
        """)
        cand_pms = {_local(row["muscle"]) for row in cand_pm_rows}
        overlap = prime_movers & cand_pms

        if not overlap and prime_movers:
            continue  # No shared prime movers — skip

        eq_rows = _sparql(f"""
        PREFIX feg: <{FEG}>
        SELECT ?eq WHERE {{ feg:{cand_id} feg:equipment ?eq }}
        """)
        equipment = _local(eq_rows[0]["eq"]) if eq_rows else None

        results.append({
            "id": cand_id,
            "name": _str(r["label"]),
            "equipment": equipment,
            "shared_prime_movers": sorted(overlap),
        })

    return results


def get_muscle_hierarchy() -> dict:
    """
    Return the complete SKOS muscle hierarchy as a nested dict:
    { region: { group: [heads] } }

    Groups with useGroupLevel=true are flagged.
    """
    rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?concept ?label ?broader ?useGroupLevel WHERE {{
      {{ ?concept a feg:MuscleRegion }}
      UNION {{ ?concept a feg:MuscleGroup }}
      UNION {{ ?concept a feg:MuscleHead }}
      ?concept skos:prefLabel ?label .
      OPTIONAL {{ ?concept skos:broader ?broader }}
      OPTIONAL {{ ?concept feg:useGroupLevel ?useGroupLevel }}
    }}
    """)

    # Index all concepts
    concepts: dict[str, dict] = {}
    for r in rows:
        local = _local(r["concept"])
        concepts[local] = {
            "label": _str(r["label"]),
            "broader": _local(r["broader"]) if r["broader"] else None,
            "use_group_level": r["useGroupLevel"] is not None
            and r["useGroupLevel"].value == "true",
        }

    # Classify by level
    region_rows = _sparql(
        f"PREFIX feg: <{FEG}> SELECT ?c WHERE {{ ?c a feg:MuscleRegion }}"
    )
    group_rows = _sparql(
        f"PREFIX feg: <{FEG}> SELECT ?c WHERE {{ ?c a feg:MuscleGroup }}"
    )
    head_rows = _sparql(
        f"PREFIX feg: <{FEG}> SELECT ?c WHERE {{ ?c a feg:MuscleHead }}"
    )

    regions = {_local(r["c"]) for r in region_rows}
    groups = {_local(r["c"]) for r in group_rows}
    heads = {_local(r["c"]) for r in head_rows}

    # Build nested structure
    hierarchy: dict[str, Any] = {}

    for region in sorted(regions):
        info = concepts[region]
        hierarchy[region] = {
            "label": info["label"],
            "groups": {},
        }

    for group in sorted(groups):
        info = concepts[group]
        parent = info["broader"]
        if parent and parent in hierarchy:
            hierarchy[parent]["groups"][group] = {
                "label": info["label"],
                "use_group_level": info["use_group_level"],
                "heads": [],
            }

    for head in sorted(heads):
        info = concepts[head]
        parent = info["broader"]  # parent is a group
        if parent:
            # Find which region owns this group
            group_info = concepts.get(parent, {})
            region = group_info.get("broader")
            if region and region in hierarchy and parent in hierarchy[region]["groups"]:
                hierarchy[region]["groups"][parent]["heads"].append({
                    "id": head,
                    "label": info["label"],
                })

    return hierarchy


def query_by_joint_action(joint_action: str) -> list[dict]:
    """Return exercises where the given joint action appears as a primary joint action."""
    rows = _sparql(f"""
    PREFIX feg: <{FEG}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?ex ?label WHERE {{
      ?ex a feg:Exercise ; rdfs:label ?label ;
          feg:primaryJointAction feg:{joint_action} .
    }} ORDER BY ?label
    """)

    results = []
    for r in rows:
        ex_local = _local(r["ex"])
        mp_rows = _sparql(f"""
        PREFIX feg: <{FEG}>
        SELECT ?mp WHERE {{ feg:{ex_local} feg:movementPattern ?mp }}
        """)
        eq_rows = _sparql(f"""
        PREFIX feg: <{FEG}>
        SELECT ?eq WHERE {{ feg:{ex_local} feg:equipment ?eq }}
        """)
        results.append({
            "id": ex_local,
            "name": _str(r["label"]),
            "movement_patterns": [_local(row["mp"]) for row in mp_rows],
            "equipment": _local(eq_rows[0]["eq"]) if eq_rows else None,
        })

    return results


# ── MCP server wiring ─────────────────────────────────────────────────────────

app = Server("free-exercise-graph")

TOOLS: list[Tool] = [
    Tool(
        name="search_exercises",
        description=(
            "Search exercises by muscle involvement, movement pattern, and/or equipment. "
            "All filters are ANDed. Returns name, id, and muscle involvements for each match. "
            "With no filters, returns up to 50 exercises alphabetically."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "muscles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "feg: local names of muscles to filter by (e.g. ['GluteusMaximus', 'Hamstrings'])",
                },
                "movement_pattern": {
                    "type": "string",
                    "description": "feg: local name of movement pattern (e.g. 'HorizontalPush', 'Squat')",
                },
                "equipment": {
                    "type": "string",
                    "description": "feg: local name of equipment (e.g. 'Barbell', 'Dumbbell', 'Bodyweight')",
                },
                "degree": {
                    "type": "string",
                    "enum": ["PrimeMover", "Synergist", "Stabilizer", "PassiveTarget"],
                    "description": "Filter muscle involvement by degree",
                },
            },
        },
    ),
    Tool(
        name="get_exercise",
        description=(
            "Return the full record for one exercise: muscle involvements with degrees, "
            "joint actions, movement patterns, training modalities, equipment, and flags."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "exercise_id": {
                    "type": "string",
                    "description": "feg: local name of the exercise (e.g. 'ex_Barbell_Deadlift')",
                },
            },
            "required": ["exercise_id"],
        },
    ),
    Tool(
        name="find_substitutions",
        description=(
            "Find exercises that can substitute for a given exercise. "
            "Matches on shared primary movement pattern(s) and overlapping PrimeMover muscles. "
            "Optionally filters to exercises that use only the specified equipment. "
            "Bodyweight exercises are always included when equipment filtering is active."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "exercise_id": {
                    "type": "string",
                    "description": "feg: local name of the reference exercise",
                },
                "equipment_available": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "feg: local names of available equipment (e.g. ['Bands', 'Dumbbell']). Omit to include all equipment.",
                },
            },
            "required": ["exercise_id"],
        },
    ),
    Tool(
        name="get_muscle_hierarchy",
        description=(
            "Return the complete SKOS muscle hierarchy: regions → groups → heads. "
            "Groups with use_group_level=true should be referenced at group level, "
            "not individual heads."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="query_by_joint_action",
        description=(
            "Return all exercises where the given joint action appears as a primary joint action."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "joint_action": {
                    "type": "string",
                    "description": "feg: local name of the joint action (e.g. 'HipExtension', 'KneeFlexion')",
                },
            },
            "required": ["joint_action"],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "search_exercises":
            result = search_exercises(
                muscles=arguments.get("muscles"),
                movement_pattern=arguments.get("movement_pattern"),
                equipment=arguments.get("equipment"),
                degree=arguments.get("degree"),
            )
        elif name == "get_exercise":
            result = get_exercise(arguments["exercise_id"])
        elif name == "find_substitutions":
            result = find_substitutions(
                exercise_id=arguments["exercise_id"],
                equipment_available=arguments.get("equipment_available"),
            )
        elif name == "get_muscle_hierarchy":
            result = get_muscle_hierarchy()
        elif name == "query_by_joint_action":
            result = query_by_joint_action(arguments["joint_action"])
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    # Eagerly load the store so the first tool call is fast
    store()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
