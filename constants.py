"""
constants.py — Single source of truth for project-wide constants.

When migrating the namespace, update FEG_NS here and run sync_namespaces.py
to propagate the change to all TTL, SPARQL, and Python files.
"""

# Current namespace — placeholder pending DNS setup on talha.foo.
# Target: https://feg.talha.foo/ontology# (ontology terms)
#         https://feg.talha.foo/data#     (data instances)
FEG_NS = "https://placeholder.url#"
