# Quality Surfaces

This repo has four quality surfaces. They are related, but they do different jobs.

---

## 1. `test_shacl.py`

Purpose:
- fast unit-style regression checks for SHACL constraints
- confirms the ontology/shape rules still behave as intended

What it proves:
- malformed examples still fail
- exempt cases still pass
- shape changes did not accidentally loosen or tighten constraints

Run:

```bash
python3 test_shacl.py
```

Use this when:
- editing `ontology/shapes.ttl`
- changing ontology semantics
- changing build semantics that affect emitted triples

---

## 2. `pipeline/validate.py`

Purpose:
- graph-level data quality scorecard

Dimensions:
- validity
- uniqueness
- integrity
- timeliness
- completeness

Run:

```bash
python3 pipeline/validate.py --verbose
python3 pipeline/validate.py --shacl --verbose
```

What it proves:
- the built graph is structurally healthy
- inferred claims resolve to known vocabulary terms
- enrichment warnings needing restamp are visible
- expected product fields are present or missing in a measurable way

Use this when:
- evaluating a graph build
- preparing a release/demo
- reviewing data quality drift over time

---

## 3. `evals/`

Purpose:
- measure enrichment accuracy against a human-annotated gold standard
- seed a representative annotation workbook from the live canonical DB
- keep accuracy scoring aligned with the same effective claim surface used by the build

Run:

```bash
python3 evals/build_gold_sheet.py
python3 evals/eval.py
```

Useful options:

```bash
python3 evals/build_gold_sheet.py --limit 60
python3 evals/build_gold_sheet.py --batch-size 10
python3 evals/build_gold_sheet.py --entity-id good_morning --entity-id sit_up
python3 evals/eval.py --gold evals/submitted --verbose
python3 evals/eval.py --gold evals/submitted --field movement_patterns
python3 evals/eval.py --archive-scored
```

What it proves:
- the current canonical-entity enrichment output is accurate on reviewed examples
- muscle scoring reflects the same merged resolved+inferred surface the graph uses
- regressions in movement patterns, joint actions, laterality, or other enriched fields are measurable

Use this when:
- refreshing the gold set
- checking enrichment quality after prompt, schema, or pipeline changes
- comparing model or ontology changes on real examples

Notes:
- batches are seeded from `pipeline.db`, not from retired per-source `enriched/*.json`
- the default output is five 10-exercise workbooks in `evals/unreviewed/`
- reviewed files should be placed in `evals/submitted/`
- `--archive-scored` moves successfully processed submitted files into `evals/scored/`
- rows or fields left as `Pending` are skipped by `eval.py`

---

## 4. CI

Purpose:
- minimum release confidence

CI should prove:
- dependencies install
- SHACL unit tests pass
- the deterministic pipeline can rebuild from source truth
- the rebuilt graph is not obviously broken

CI is not the full product-quality story. It is the minimum “the repo still works” story.

---

## Which One Should I Run?

- changed shapes or ontology behavior: run `test_shacl.py`
- changed pipeline/build logic: run `pipeline/run.py --to build` and `pipeline/validate.py --verbose`
- changed enrichment semantics or want accuracy numbers: run `evals/build_gold_sheet.py` and `evals/eval.py`
- preparing to show or ship the project: run all four surfaces

---

## Accuracy Is Separate

`pipeline/validate.py` does **not** prove enrichment correctness.

It proves well-formedness, integrity, timeliness, and coverage.
Accuracy belongs to:

- `evals/`
- gold-standard annotation workbook
- `eval.py`

That separation is intentional.
