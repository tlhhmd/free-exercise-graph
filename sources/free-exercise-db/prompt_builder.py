"""
prompt_builder.py

Generic utilities for building LLM prompts from RDF ontology files.

Callers are responsible for loading graphs and supplying URIs. This module
has no knowledge of any specific project, namespace, or file layout.

Public API:
    skos_tree                   - render a SKOS concept scheme as an indented tree
    group_level_muscles         - list muscle groups where heads should not be used
    property_comment            - extract rdfs:comment from a SHACL property shape
    sparql_constraint_comments  - extract instructional comments from SPARQL constraints
    render                      - render a <<<placeholder>>> template file
"""

from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

SH = Namespace("http://www.w3.org/ns/shacl#")


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

        parts = [f"{pad}{name}"]
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


def property_comment(g: Graph, target_class: URIRef, path: URIRef) -> str:
    """Return rdfs:comment from the property shape for the given path on the
    shape targeting target_class. Returns empty string if not found."""
    for shape in g.subjects(SH.targetClass, target_class):
        for prop_shape in g.objects(shape, SH.property):
            if (prop_shape, SH.path, path) in g:
                comment = g.value(prop_shape, RDFS.comment)
                if comment:
                    return str(comment)
    return ""


def sparql_constraint_comments(g: Graph) -> list[str]:
    """Return rdfs:comment from SPARQL constraints that carry one.
    Constraints without rdfs:comment are structural validation rules, not LLM instructions."""
    comments = []
    for shape in g.subjects(RDF.type, SH.NodeShape):
        for sparql_node in g.objects(shape, SH.sparql):
            comment = g.value(sparql_node, RDFS.comment)
            if comment:
                comments.append(str(comment))
    return comments


def render(template_path: Path | str, variables: dict[str, str]) -> str:
    """Render a template file, replacing <<<variable_name>>> placeholders."""
    text = Path(template_path).read_text()
    for key, value in variables.items():
        text = text.replace(f"<<<{key}>>>", value)
    return text
