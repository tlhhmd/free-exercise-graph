# Lessons Learned

A running log of hard-won insights from building this project. Not a decision record — ADRs live in DECISIONS.md. This is the meta-level: what patterns held, what backfired, where our instincts were wrong, and what we'd do differently on the next project.

---

## Ontology and Vocabulary Design

**Vocabularies are interfaces, not taxonomies.** The design principle that has held up best: "would a gym-goer understand this?" steered us away from several bad decisions (FMA import, Antagonist as involvement degree, ExplosiveHinge as a movement sub-pattern). Every time we ignored it and tried to be anatomically correct, we had to reverse course.

**The SKOS/OWL split is the right call.** SKOS for controlled vocabularies, OWL for schema structure. OWL subclasses would have required a reasoner to infer movement pattern membership — SKOS with explicit LLM assignment is simpler and more auditable. We never regretted this choice.

**Hierarchies should match how users query, not how anatomy works.** Calves nested under LowerLeg (ADR-026) rather than as a peer of it. TibialisAnterior as a sibling of Calves under LowerLeg rather than under Calves. These felt counterintuitive at first but are how a gym-goer navigates a filter: "lower leg → calves" not "calves → tibialis."

**`skos:related` is genuinely useful for cross-cutting functional associations.** Middle Trapezius being canonical under Traps but `skos:related` to MiddleBack (ADR-019, ADR-020) is semantically honest. The mistake would have been multiple `skos:broader` parents, which breaks hierarchy traversal queries. `skos:related` keeps the hierarchy clean while preserving the association.

**useGroupLevel was the right abstraction.** scopeNotes (ADR-046) encoding the same rule five times as prose was immediately the wrong call. The boolean property (ADR-047) that the prompt builder reads via SPARQL was obviously better — one consistent instruction generated from data rather than five copies of prose. Lesson: if you find yourself writing the same prompt rule more than twice, it belongs in the ontology as a machine-readable property, not in prose.

**Dropping things is often the right call.** Antagonist (involvement degree), ExplosiveHinge (movement sub-pattern), inverse properties, progression/regression — all designed, all dropped. The instinct to model everything upfront is a trap. V1 use cases should drive what gets built. Every dropped concept is a maintenance cost avoided.

**Version bumps compound into re-enrichment debt.** Every vocabulary MINOR version bump means the previously enriched exercises that were stamped at the old version are technically stale. At 4,095 entities this becomes painful. Batch vocabulary changes — don't bump for one concept, wait until you have a cohesive set of changes. This wasn't formally established as a rule and should be.

---

## Pipeline Architecture

**The identity-first pipeline is the right architecture for multi-source data.** Running entity resolution before enrichment means each canonical entity gets one LLM call, not one call per source record. At 4,095 canonical entities vs. ~5,000+ raw records, that's meaningful savings. The morph-KGC / per-source-ingest approach (ADR-037–043) was the wrong direction — it built source-specific pipelines that didn't compose well. The SQLite-backed identity-first pipeline composes perfectly.

**SQLite as the pipeline intermediate store was the right call.** Simple, local, no infrastructure dependency, resume-safe by construction. Every stage reads from and writes to the same DB. The WAL mode + foreign keys pattern is the right default. The only thing to watch: multiple concurrent writers (enrich.py with --concurrency > 1) need their own connections — don't share a connection across threads.

**Resumability should be designed in from the start, not bolted on.** `enrichment_stamps` is the right primitive — a stamp table per entity that lets any stage skip already-processed entities. Every pipeline stage should have this. We had it in enrich.py from day one but had to retrofit it for batch. The lesson: any stage that touches an external API or does expensive work needs a stamp table.

**Deterministic pipeline stages are underrated.** reconcile.py does no LLM calls and produces deterministic output. That means it can be re-run freely, its output is reproducible, and failures are easy to debug. Every stage that can be made deterministic should be. Reserve the non-determinism budget for the stages that genuinely need it (enrich.py).

**The SHACL shapes as single source of truth for prompt rules (ADR-045) is the most important architectural insight.** Having prompt rules in prose AND validation constraints in SHACL is two parallel sources of truth that diverge silently. Co-locating them in SHACL means a new constraint automatically becomes a new prompt rule. The `rdfs:comment` on property shapes → prompt builder pattern is the right way to do this.

**Repair queries as SPARQL UPDATE (ADR-048) is the right pattern for post-ingestion cleanup.** The alternative — fixing things in Python — encodes business logic in imperative code that's harder to read and audit. SPARQL UPDATE queries are declarative, stored in files, version-controlled, and human-readable. The useGroupLevel collapse, dedup, and cross-degree dedup are all expressed clearly as SPARQL.

---

## LLM Enrichment

**Constrained decoding (response_schema / structured output) is non-negotiable.** Without it, every LLM call needs aggressive validation and retry logic to handle hallucinated vocabulary terms. With it, the model physically cannot produce an invalid term. This shifts quality risk from "did it hallucinate" to "did it choose the right degree/pattern" — a much smaller surface area.

**Sparse input exercises need an explicit rule.** When an entity has only a name and equipment (no source muscles, no instructions), the LLM has nothing to anchor on and will either hallucinate or under-classify. The explicit rule — "classify using standard biomechanical convention for that named movement" — is required. Without it, sparse inputs are the most common failure mode.

**Few-shot examples matter more than prose rules for degree disambiguation.** The RDL vs Back Squat example (hamstrings as PrimeMover in RDL, Synergist in Back Squat) communicates the PrimeMover vs Synergist distinction better than any number of prose rules. Concrete contrasts are more effective than abstract definitions. Every time a failure mode appears in enrichment output, the right response is a new example pair, not more prose.

**Context caching is worth implementing.** At ~9,000 tokens in the system prompt, caching saves ~97% of input token cost per call. The implementation complexity (cache lifecycle, TTL management, file persistence) is about two days of work for potentially thousands of dollars in savings on a large run. Always worth it for prompts > 4K tokens.

**The `useGroupLevel` collapse problem reveals a general LLM instruction compliance issue.** The model consistently used `RhomboidMajor`/`RhomboidMinor` as PrimeMover on row exercises despite explicit prompt instruction to use the group. The fix was a SPARQL repair query — a post-LLM correction pass. Lesson: don't fight the model on individual term preferences with more prompt text. If the model has a strong prior for a specific term, accept the term and normalize in a repair pass.

**Thinking models add cost and latency with marginal benefit on constrained tasks.** We disabled thinking by default on Gemini 3.1 Pro (thinking_budget=0). Constrained decoding already handles the most common LLM failure modes. Thinking is useful for open-ended reasoning; it's wasteful for "pick the right term from this list."

---

## API and Infrastructure

**Free tier rate limits are not a strategy for large enrichment jobs.** 250 RPD on Gemini 3.1 Pro = 16 days for 4,095 entities. This was foreseeable before starting the job. For any enrichment job > ~500 entities, budget for paid API usage upfront. $2–60 to finish in hours is almost always worth it over weeks.

**The Gemini Batch API on the free developer tier is severely constrained.** Max ~200 inline requests per job, one active job at a time. This makes it worse than synchronous for the free tier — serial 200-entity batches every 24h vs. 250 synchronous calls per day. The batch API is a paid-tier feature in practice.

**Always test API capabilities with a minimal probe before designing an architecture around them.** We spent time designing batch_export.py and batch_ingest.py before discovering the inline request limit. Three test calls first would have revealed the constraint.

**Cancelled batch jobs may still consume quota against daily limits.** The batch job testing exhausted the daily submission quota even though all jobs were cancelled before processing. Quota consumption is tied to submission, not completion.

**Provider abstraction pays off immediately.** The AnthropicProvider / GeminiProvider abstraction (a two-day investment) made provider switching a CLI flag. When the free tier turned out to be inadequate, we didn't need to rewrite the pipeline — just change `--provider`. Any enrichment pipeline with more than one candidate model should abstract the provider from day one.

**The google-genai SDK (not google-generativeai) is the correct package.** google-generativeai is deprecated. google-genai is the current SDK with a different client initialization pattern (`genai.Client(api_key=...)` not `genai.configure()`). The SDK names are confusingly similar and the deprecation warning is easy to miss.

---

## Project Governance

**ADR discipline compounds in value over time.** By ADR-040, we stopped second-guessing decisions that had already been made. The institutional memory function of ADRs becomes more valuable, not less, as the project grows. The hard rule — no vocabulary change without an ADR — has been violated zero times since it was established, which is the right outcome.

**"Discuss before building" should be a first principle, not an afterthought.** Several wrong directions (morph-KGC pipeline, per-source enrichment, scopeNote-as-rule) were built before being abandoned. In each case, the design question was answerable in an hour of discussion. The cost of building then reversing was always higher than the cost of discussing first.

**The portfolio framing matters to design choices.** Knowing this is a portfolio piece targeting senior KG roles shapes decisions: ADR discipline over move-fast-and-break, ontology governance over pragmatic shortcuts, provenance (DCAT + PROV-O) over bare minimum. These choices are correct regardless of portfolio value, but the framing helps justify the upfront investment when shortcuts are tempting.

**Completed items should be removed from TODO.md, not checked off.** This keeps TODO.md signal-rich. A file with 80% checked items is noise. A file with only open items is useful. The discipline of removing items as they complete is harder than it sounds but worth maintaining.

**The `.gitignore` as an ISSO signal.** API keys, pipeline runtime files, derived artifacts, and context cache IDs should all be gitignored from day one. It's easier to add exclusions early than to remove committed secrets later. When in doubt about whether a file should be committed, it probably shouldn't be.

---

## What We'd Do Differently

1. **Budget for paid API usage from the start.** Don't design the enrichment timeline around free tier limits. The cost of running 4,095 enrichments on a capable model is $2–60 depending on the model. That should be a line item in the project, not a surprise.

2. **Test API constraints with 3-request probes before building infrastructure.** The batch API limit discovery cost a session of work. A five-minute probe first would have saved it.

3. **Batch vocabulary changes.** Don't bump version for a single concept addition. Accumulate a set of related changes and bump once. This minimizes stale-enrichment debt.

4. **Build the validate.py quality scorecard earlier.** We're building the graph without a quality measurement instrument. The 6-dimension scorecard should have been designed alongside the enrichment pipeline, not after it.

5. **Design the triage queue tooling (possible_matches) before running identity.py at scale.** Near-duplicate pairs accumulate and sit unresolved. A review tool should exist before the data does.
