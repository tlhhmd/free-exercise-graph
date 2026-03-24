# Governance

This document covers the formal change management process for `free-exercise-graph` — how decisions are made, how vocabulary evolves, and who owns what. For day-to-day operational ground rules (scripts, ADR format, versioning), see `CONTRIBUTING.md`.

---

## Decision Authority

This is a single-owner project. **Talha Ahmad** has final authority on all vocabulary, ontology, and architectural decisions.

Contributors may open issues, propose ADRs, or submit pull requests. All changes to controlled vocabularies (`muscles.ttl`, `movement_patterns.ttl`, `joint_actions.ttl`, `involvement_degrees.ttl`, `training_modalities.ttl`) require explicit approval before merge.

---

## Change Intake

### Vocabulary change requests

To propose a new concept or change to an existing one:

1. Open a GitHub issue describing the change, the rationale, and the affected vocabulary file.
2. Draft an ADR in `DECISIONS.md` (see `CONTRIBUTING.md` for format). The ADR must record the decision, the rationale, and alternatives considered.
3. The ADR is reviewed and approved before any code changes are made.
4. After approval: bump the affected vocabulary file's `owl:versionInfo`, implement the change, and run `check_stale.py` to identify exercises needing re-enrichment.

### Pipeline changes

Changes to enrichment prompt rules, build logic, or SHACL constraints follow the same ADR-first process. Changes that affect what gets written to `enriched/*.json` are treated as vocabulary-level changes.

---

## Release Process

There are no versioned releases in the traditional sense. The `main` branch is the canonical state of the graph. "Release" means:

- `python3 pipeline/run.py --to build` completes without error
- `python3 pipeline/validate.py` reports no failures
- All SHACL unit tests pass (exit 0 from `test_shacl.py`)
- CI passes

Breaking changes (concept removals, URI renames) require:
1. An ADR documenting the reason
2. A MAJOR version bump on the affected ontology file
3. A re-enrichment pass to refresh affected exercises

---

## Breaking Change Policy

A change is **breaking** if it:
- Removes a concept URI (muscle, movement pattern, joint action, involvement degree, training modality)
- Renames a concept URI
- Changes the cardinality or domain/range of a core property in a way that invalidates existing data

Breaking changes are only made when the ontological case is clear and the enrichment cost of re-tagging is justified. All breaking changes are documented with MAJOR version bumps and re-enrichment.

A change is **non-breaking** (additive) if it:
- Adds a new concept to an existing vocabulary
- Adds new `rdfs:label`, `skos:altLabel`, or `rdfs:comment` entries
- Adds a new property that existing data simply omits

---

## Deprecation Policy

Concepts are not deleted without a deprecation period. The process:

1. Mark the concept with `owl:deprecated true` and a `rdfs:comment` explaining the replacement.
2. Document the deprecation in an ADR.
3. Run `check_stale.py` to identify exercises referencing the deprecated concept.
4. Re-enrich affected exercises against the updated vocabulary.
5. Remove the deprecated concept in a subsequent MAJOR version bump.

---

## Namespace Ownership

All URIs currently use `https://placeholder.url#` (prefix `feg:`) — a placeholder pending a permanent domain. The intended namespace is:

- Ontology terms: `https://feg.talha.foo/ontology#`
- Data instances: `https://feg.talha.foo/data#`

**Talha Ahmad** owns the `talha.foo` domain and is responsible for maintaining namespace resolution. The namespace migration requires a MAJOR version bump on all ontology files and a full re-enrichment pass. See TODO.md for the migration plan.

No data using the `feg:` namespace should be published externally until the permanent namespace is in place.

---

## Conflict Resolution

In the event of disagreement between contributors on a vocabulary or architecture decision:

1. Both positions should be documented in the relevant GitHub issue.
2. The final decision rests with **Talha Ahmad**.
3. The decision is recorded in an ADR regardless of which position prevails, including the rationale for the choice.

The ADR system is the record of institutional memory. Decisions made verbally or informally are not binding until recorded.
