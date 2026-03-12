# Project Status

_Keep this file current. It is referenced from CLAUDE.md._

## Done

- Full ontology designed and documented (ADR-001 through ADR-029)
- All six vocabulary files with versioning
- SHACL shapes for validation
- `enrich.py` — async, idempotent, validates output, stamps versions
- `check_stale.py` — detects stale enrichments after vocab changes
- `prompt.py` — dynamic prompt from TTL files with few-shot examples
- ~30 exercises successfully enriched (sample run)
- Vocabulary gaps discovered and fixed: Psoas, TibialisAnterior, Core (muscle group),
  Mobility (pattern), SoftTissue (pattern), TrunkStability (renamed from Core)

## Pending (priority order)

1. **Eval framework** — gold standard dataset (30-50 exercises), rubric, `evals/eval.py`. Build before running full 873.
2. **encode.py** — enriched JSON → RDF Turtle (pipeline incomplete without this)
3. **review.py** — Marimo UI for quarantine triage
4. **Crosswalk document** — map source dataset's flat muscle terms to our hierarchy
5. **SPARQL query library** — `queries/` directory with analytical queries
6. **GOVERNANCE.md** — formal change management process document
7. **README.md** — project overview with knowledge management and governance framing
8. **Run full 873** — only after eval framework is in place
9. **pyproject.toml** — ruff config, dependencies

## Open Questions

- Namespace placeholder needs a real URI before public release
- Entity resolution (duplicate exercises) deferred to v2
- `Mobility` vs `SoftTissue` boundary may need revisiting as more exercises are seen
- Whether to add a `Mobility` training modality distinct from the movement pattern of the same name
