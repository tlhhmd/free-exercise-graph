# Troubleshooting

Use this document when the repo is technically "working" but your local state or
generated artifacts do not match what you expected.

---

## `graph.ttl` Is Missing Or Stale

Rebuild the deterministic pipeline:

```bash
python3 pipeline/run.py --to build
```

Then validate:

```bash
python3 pipeline/validate.py --verbose
python3 test_shacl.py
```

If you changed source truth or deterministic stage semantics and the replay no
longer makes sense, read the reset guidance in
[system_contracts.md](/Users/talha/Code/free-exercise-graph/docs/system_contracts.md).

---

## The Static App Looks Stale After Pipeline Changes

Rebuild the full app artifact chain:

```bash
python3 pipeline/run.py --to build
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph --similarity-dir data/generated --out app
python3 app/build_observatory.py --out app
```

Then hard refresh the browser with `Cmd + Shift + R`.

---

## Substitute UI Is Missing Or Wrong

`app/exercise_substitute_ui.json` is not generated in the browser. It comes from
the offline similarity pipeline.

Rebuild:

```bash
python3 scripts/build_similarity_graph.py --input graph.ttl --out data/generated
python3 scripts/build_substitute_ui.py --input-dir data/generated --out data/generated
python3 app/build_site.py --from-graph --similarity-dir data/generated --out app
```

If the JSON file is missing after that, inspect `data/generated/` first.

---

## Builder View Is Missing

Builder View depends on `app/observatory.json`, not just `app/data.json`.

Rebuild it:

```bash
python3 app/build_observatory.py --out app
```

Then verify the exercise is one of the curated observatory entries.

Current curated exercises live in
[build_observatory.py](/Users/talha/Code/free-exercise-graph/app/build_observatory.py).

---

## When To Use `--reset-db`

Use `python3 pipeline/run.py --reset-db --yes-reset-db --to build` only when:

- deterministic tables are inconsistent
- source-record membership changed and replay is no longer safe
- you intentionally want a clean rebuild from source truth

Do not use it casually if you care about persisted enrichment state.

Back up first:

```bash
python3 pipeline/db_backup.py backup
python3 pipeline/export_enrichment.py
```

---

## When To Re-enrich

You do not need to re-enrich for every code change.

Re-enrich when:

- ontology terms used by enrichment changed
- prompt grounding changed
- a stripped value was added to the vocabulary
- a specific entity needs correction

Useful commands:

```bash
python3 pipeline/enrich.py --dry-run
python3 pipeline/enrich.py --force <entity_id>
python3 pipeline/enrich.py --restamp <term>
```

---

## CI Passed, But The Product Still Looks Wrong

CI is a minimum confidence check, not the full product-quality story.

CI proves things like:

- dependencies install
- SHACL unit tests pass
- the deterministic pipeline can rebuild
- the built graph is not obviously broken

CI does not prove:

- substitute ranking quality
- enrichment correctness
- Builder View narrative accuracy
- frontend UX correctness

For that split, see
[quality_surfaces.md](/Users/talha/Code/free-exercise-graph/docs/quality_surfaces.md).
