# Contributing

This document covers the operational ground rules for working on `free-exercise-graph`.
Read `DECISIONS.md` for the full ADR history before making any ontology or pipeline change.

---

## Where to Start

1. **Read `DECISIONS.md`** — every non-trivial decision is documented there. Check it before touching ontology files or pipeline behaviour. ADRs are numbered sequentially; the highest number is the most recent.
2. **Read `TODO.md`** — current open items in priority order.
3. **Run the pipeline** to confirm your local environment is healthy before making changes.

```bash
pip install -e .
python3 sources/free-exercise-db/build.py
python3 test_shacl.py
```

---

## What Requires an ADR

Write an ADR in `DECISIONS.md` before (or immediately after) making any of the following:

| Change type | Examples |
|---|---|
| Vocabulary additions | New muscle concept, new movement pattern, new joint action |
| Vocabulary removals | Retiring a concept, merging two concepts |
| URI renames | Any change to a `feg:` local name |
| Version bumps | Any `owl:versionInfo` change in an ontology file |
| Pipeline behaviour | Enrichment prompt rule change, new output field, build logic changes |
| SHACL constraint changes | Tightening or relaxing `sh:minCount`, adding a new shape |

**Hard rule: never add or remove vocabulary concepts without an ADR.** This includes muscles,
movement patterns, joint actions, training modalities, and involvement degrees.

ADRs are numbered sequentially (ADR-001, ADR-002, …). Add new ones at the bottom of
`DECISIONS.md`. Record: the decision, the rationale, and any alternatives considered.

---

## Vocabulary Versioning

All ontology files carry `owl:versionInfo` (semver). Bump the version in the relevant file
whenever you make a change:

| Change type | Version component |
|---|---|
| Removing concepts, renaming URIs | MAJOR |
| Adding new concepts or properties | MINOR |
| Correcting labels, comments, editorial notes | PATCH |

Bump only the file(s) that changed. After bumping a version, run `check_stale.py` to
identify enriched exercises that need re-enrichment against the new vocabulary.

```bash
python3 sources/free-exercise-db/check_stale.py --verbose
```

---

## Which Outputs Are Committed vs. Derived

| File | Status | Notes |
|---|---|---|
| `sources/free-exercise-db/enriched/{id}.json` | **Committed** | The dataset — primary output of `enrich.py` |
| `sources/free-exercise-db/ingested.ttl` | Gitignored (derived) | Rebuilt from `enriched/` by `build.py` |
| `sources/free-exercise-db/raw/exercises.json` | **Committed, read-only** | Upstream source — never modify directly |

`quarantine/` (failed enrichments) is gitignored — transient debugging data.

---

## Safe Scripts to Run

| Script | Effect |
|---|---|
| `fetch.py` | Overwrites `raw/exercises.json` from upstream — only run intentionally |
| `enrich.py` | Writes one JSON file per exercise to `enriched/`; costs API tokens |
| `check_stale.py` | Read-only; exits 0/1 |
| `build.py` | Writes `ingested.ttl` (gitignored) |
| `validate.py` | Writes `quality_report.csv`; exits 0/1 |
| `test_shacl.py` | Read-only; exits 0/1 — CI gate for `build.py` regressions |

---

## Namespace

All URIs use `https://placeholder.url#` (prefix `feg:`) — a placeholder pending a permanent
domain. Do not use this namespace for any external publication until it is replaced.

---

## Pipeline Dependency Order

```
fetch.py → enrich.py → check_stale.py → build.py → validate.py
```

`test_shacl.py` can run at any point — it uses in-memory test fixtures, not `ingested.ttl`.
