# Quality Surfaces

This repo has three quality surfaces. They are related, but they do different jobs.

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

## 3. CI

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
- preparing to show or ship the project: run all three surfaces

---

## Accuracy Is Separate

`pipeline/validate.py` does **not** prove enrichment correctness.

It proves well-formedness, integrity, timeliness, and coverage.
Accuracy belongs to:

- `evals/`
- gold-standard annotation
- future `eval.py`

That separation is intentional.
