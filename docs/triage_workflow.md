# Triage Workflow

`pipeline/triage.py` is the human-in-the-loop review step for ambiguous identity matches.

The pipeline does not block on ambiguity. Instead, `identity.py` defers uncertain pairs into
`possible_matches`, and triage lets a human resolve them deliberately.

---

## When to Use Triage

Run triage when:

- `identity.py --dry-run` shows deferred matches you care about
- you changed identity logic and want to review the ambiguous boundary
- you are cleaning up the canonical entity layer before a major release/demo

Command:

```bash
python3 pipeline/triage.py
```

---

## Decisions

- `m` = merge
- `s` = separate
- `v` = variant_of
- `?` = skip for later

Merge decisions are applied immediately.

After one or more merges, rerun:

```bash
python3 pipeline/reconcile.py
python3 pipeline/build.py
python3 pipeline/validate.py --verbose
```

---

## Correction Loop

The intended HITL loop is:

1. Detect an ambiguity or bad result
2. Review it in triage or in the built graph
3. Decide the right fix surface:
   - identity rule
   - source crosswalk
   - ontology term / shape
   - prompt grounding
4. Apply the fix
5. Re-run deterministic stages
6. Re-enrich affected entities only
7. Rebuild + revalidate

Useful targeted commands:

```bash
python3 pipeline/enrich.py --force <entity_id>
python3 pipeline/enrich.py --restamp <term>
```

---

## What Triage Is For

Triage is for ambiguity in canonical identity, not for every classification issue.

Use triage when the question is:

- “Are these the same exercise?”
- “Are these peers or variants?”
- “Should this source record be absorbed into that entity?”

Do **not** use triage when the question is:

- “Is this the right movement pattern?”
- “Should this vocabulary term exist?”
- “Did the model miss a muscle?”

Those belong to ontology, prompt, crosswalk, or enrichment review work.

---

## Recommended Review Order

1. High-score pairs first
2. Pairs affecting flagship/use-case exercises
3. Pairs that show up repeatedly in demos or quality reports
4. Long-tail cleanup later

---

## Related Docs

- [system_contracts.md](/Users/talha/Code/free-exercise-graph/docs/system_contracts.md)
- [quality_surfaces.md](/Users/talha/Code/free-exercise-graph/docs/quality_surfaces.md)
- [reconciliation_example.md](/Users/talha/Code/free-exercise-graph/docs/reconciliation_example.md)
