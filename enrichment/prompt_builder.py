"""
prompt_builder.py

Generic utilities for building LLM prompts from RDF ontology files.

Callers are responsible for loading graphs and supplying URIs. This module
has no knowledge of any specific project, namespace, or file layout.

Public API:
    skos_tree           - render a SKOS concept scheme as an indented tree
    group_level_muscles - list muscle groups where heads should not be used
    property_comment    - extract rdfs:comment from an OWL property definition
    render              - render a <<<placeholder>>> template file
"""

from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, SKOS


def _local(uri: URIRef) -> str:
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.split("/")[-1]


def skos_tree(
    g: Graph,
    scheme: URIRef,
    indent: int = 2,
    type_map: dict[str, str] | None = None,
    include_scope_notes: bool = False,
) -> str:
    """Render a SKOS concept scheme as an indented tree.

    Args:
        type_map: optional {str(rdf_type_uri): "annotation"} appended after the name
        include_scope_notes: if True, renders skos:scopeNote below the concept line
    """
    concepts = set(g.subjects(SKOS.inScheme, scheme))

    def is_root(c: URIRef) -> bool:
        return all(b not in concepts for b in g.objects(c, SKOS.broader))

    roots = sorted([c for c in concepts if is_root(c)], key=_local)

    def children_of(parent: URIRef) -> list:
        return sorted(
            [c for c in concepts if (c, SKOS.broader, parent) in g], key=_local
        )

    lines = []

    def render_node(node: URIRef, depth: int) -> None:
        pad = " " * (indent * depth)
        name = _local(node)

        annotation = ""
        if type_map:
            rdf_types = [str(t) for t in g.objects(node, RDF.type)]
            annotation = next((type_map[t] for t in rdf_types if t in type_map), "")

        comment = g.value(node, RDFS.comment)
        alt_labels = sorted(str(a) for a in g.objects(node, SKOS.altLabel))

        parts = [f"{pad}{name}"]
        if alt_labels:
            parts.append(f"(alt: {', '.join(alt_labels)})")
        if annotation:
            parts.append(annotation)
        if comment:
            parts.append(f"— {comment}")
        lines.append(" ".join(parts))

        if include_scope_notes:
            scope_note = g.value(node, SKOS.scopeNote)
            if scope_note:
                lines.append(f"{pad}  Note: {scope_note}")

        for child in children_of(node):
            render_node(child, depth + 1)

    for root in roots:
        render_node(root, 0)

    return "\n".join(lines)


def group_level_muscles(g: Graph, use_group_level_prop: URIRef) -> str:
    """Return a bullet list of MuscleGroup labels that carry useGroupLevel=true.

    Args:
        g: graph containing the muscle vocabulary
        use_group_level_prop: URIRef of the feg:useGroupLevel property
    """
    from rdflib import Literal

    muscles = []
    for subj in g.subjects(use_group_level_prop, Literal(True)):
        label = g.value(subj, RDFS.label) or _local(subj)
        muscles.append(str(label))
    return "\n".join(f"- {m}" for m in sorted(muscles))


def property_comment(g: Graph, prop: URIRef) -> str:
    """Return rdfs:comment from the OWL property definition. Returns empty string if not found."""
    comment = g.value(prop, RDFS.comment)
    return str(comment) if comment else ""


def render(template_path: Path | str, variables: dict[str, str]) -> str:
    """Render a template file, replacing <<<variable_name>>> placeholders."""
    text = Path(template_path).read_text()
    for key, value in variables.items():
        text = text.replace(f"<<<{key}>>>", value)
    return text
