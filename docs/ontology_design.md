# Ontology Design Reference

This document distills the recurring design principles, structural patterns, and
modeling rules that govern the free-exercise-graph ontology. It is derived from
the full ADR history in `DECISIONS.md` and from the working methodology in
`.claude/skills/ontology-review/`. Read it before making any vocabulary or schema
decision. It is a living document — update it when a new principle is established
or an existing one is revised.

---

## Core orientation

The ontology exists to serve three things in order:

1. **Product and users** — exercise discovery, filtering, substitution, program design.
2. **The enrichment pipeline** — LLM-guided annotation, validation, repair.
3. **Downstream consumers** — SPARQL queries, the static app, the MCP server.

Formal semantic correctness is a means to those ends, not an end in itself.
When a formally imprecise choice serves the product better than a precise one,
take it — and document the imprecision honestly in `rdfs:comment` or `skos:scopeNote`.

---

## Vocabulary design

### Vocabularies are for users, not ontologists

Labels are interfaces for gym-goers, coaches, and exercise scientists — not for
anatomists. Prefer colloquial terms over formal anatomy terms where both are accurate.
Preserve formal names as `skos:altLabel` for discoverability. Never invent colloquial
terms without grounding in exercise science.

Examples of this principle applied:
- "Lats" not "Latissimus Dorsi Region" (ADR-018)
- "Calves" not "Triceps Surae" (ADR-026)
- "Bodyweight" not "Body Only" (ADR-036)
- "Rotator Cuff" over "Supraspinatus / Infraspinatus / TeresMinor / Subscapularis"
  when those heads are not independently trained (ADR-046, ADR-047)

### SKOS for controlled vocabularies; OWL classes for schema

Use SKOS `skos:broader`/`skos:narrower` for hierarchy within controlled vocabularies
(muscles, movement patterns, joint actions). Use OWL classes for the schema layer
(Exercise, MuscleInvolvement, JointAction). Don't use OWL subclasses to represent
vocabulary hierarchy — SKOS is simpler, more flexible, and doesn't require inference
to be useful. The vocabulary is explicitly asserted; inference is not the mechanism.
(ADR-006, ADR-017)

### Single canonical parent; skos:related for functional associations

Every vocabulary concept has exactly one `skos:broader` parent. Multiple-parent
hierarchies create ambiguity in property-path queries. Use `skos:related` for
secondary functional associations that are real but not structural.

Examples:
- Middle Trapezius: canonical parent `feg:Traps`, `skos:related feg:MiddleBack` (ADR-019)
- Gluteus Medius: canonical parent `feg:Glutes`, `skos:related feg:Abductors` (ADR-020)
- Psoas: canonical parent `feg:LowerBack`, `skos:related feg:Quadriceps` (ADR-025)

Queries over `skos:broader+` will not surface `skos:related` associations.
Queries that want functional associations must union both.

### Specificity preference with useGroupLevel exceptions

The muscle vocabulary follows a head > group > region specificity preference.
The enrichment pipeline and prompt instruct the LLM to use the most specific
applicable term. The exception: when a `MuscleGroup` carries `feg:useGroupLevel true`,
the group IS the appropriate term — its heads exist for anatomical completeness
but are not meaningfully distinguished in exercise programming.

Current `useGroupLevel true` groups: RotatorCuff, ErectorSpinae, Gastrocnemius,
WristFlexors, WristExtensors, Obliques, Scalenes, Rhomboids. (ADR-047)

The SHACL shape enforces this: any involvement referencing a head whose parent
group has `useGroupLevel true` is a SHACL violation.

### No external anatomy ontology import

The muscle vocabulary is built and maintained in-house. FMA is too granular and
medically oriented; Uberon is cross-species. Both add maintenance overhead without
retrieval benefit. The vocabulary is authoritative by virtue of using standard
anatomical terminology (Gray's Anatomy, Terminologia Anatomica), not by linking
to an external ontology. (ADR-016)

### Add vocabulary when there is present signal

Add a concept when it has real retrieval, annotation, UI, or pipeline value now.
Signals that warrant addition:
- The LLM consistently assigns a term that is not in the vocabulary (ADR-022, ADR-027, ADR-094)
- An exercise has no valid classification and the gap is genuine
- A user query cannot be answered without the concept

Signals that do NOT warrant addition:
- Anatomy or theory permit the concept but no exercise needs it
- The concept is a degenerate extension of an existing one (ADR-091: isometric joint action variants rejected)
- The concept would redundantly encode what another layer already captures (ADR-108: isolation movement patterns rejected)

---

## Layer separation

The ontology has three distinct vocabulary layers. Keep them separate.

| Layer | Property | Purpose | Naming convention |
|---|---|---|---|
| Navigation / program design | `feg:movementPattern` | Exercise discovery, programming categories, substitution families | Training terms: HipHinge, HorizontalPull, CoreFlexion |
| Mechanical precision | `feg:primaryJointAction` / `feg:supportingJointAction` | Biomechanical description, substitution reasoning | Anatomical terms: HipExtension, SpinalFlexion |
| Muscular | `feg:hasInvolvement → feg:muscle` | Muscle targeting, involvement degree | Colloquial exercise science: Lats, Anterior Deltoid |

These layers are orthogonal and complementary. A barbell row is `HorizontalPull`
(pattern), `ShoulderExtension + ScapularRetraction + ElbowFlexion` (joint actions),
and `LatissimusDorsi PrimeMover / Rhomboids Synergist / ...` (muscle involvement).
Collapsing layers produces naming collisions, confused queries, and product bugs.

### Movement patterns are compound-movement archetypes

Movement patterns classify multi-joint, load-transfer exercises with identifiable
biomechanical signatures. Isolation exercises — those whose JA profile is entirely
single-joint, non-load-transfer — are intentionally unpattern-classified. Retrieval
for isolation exercises is via muscle group and joint action, not movement pattern.
(ADR-108)

Adding isolation-tier movement patterns (ArmFlexion, CalfRaise, etc.) would
redundantly encode what the joint action layer already captures. Rejected.

### Joint actions describe movement, not position

Joint actions are what joints are doing under load — concentric or eccentric motion.
Sustained static positions (isometric holds, setup positions) are not joint actions.
Use `feg:movementPattern` to express isometric exercise archetypes (AntiExtension,
AntiRotation → `feg:SpinalStability`). Do not add isometric variants to the joint
action vocabulary. (ADR-091)

### Cross-cutting attributes live as properties, not in hierarchy

Attributes that cut across multiple movement patterns or muscle groups belong as
properties on `feg:Exercise`, not as hierarchy nodes. Examples:

- Laterality (bilateral/unilateral/contralateral/ipsilateral): `feg:laterality` (ADR-075)
- Structural complexity: `feg:isCompound` (ADR-053)
- Combination movements: `feg:isCombination` (ADR-076)
- Plane of motion: `feg:planeOfMotion` (ADR-077)
- Exercise style: `feg:exerciseStyle` (ADR-078)

Adding these as hierarchy nodes would require redundant sub-patterns
(SingleLegSquat, SingleLegHinge, etc.) and make the hierarchy combinatorially explosive.

### Equipment is a property, not an identity dimension

A barbell Romanian deadlift and a dumbbell Romanian deadlift are the same exercise
with different equipment values. Equipment is how an exercise is performed, not
what it is. This principle also governs entity resolution: strip equipment tokens
before name-matching. (ADR-001, ADR-092)

---

## Structural patterns

### Range umbrella pattern

When a property needs to accept instances from a multi-level vocabulary hierarchy,
use a shared superclass as the range anchor rather than a union type. `feg:Muscle`
is the superclass for `feg:MuscleRegion`, `feg:MuscleGroup`, and `feg:MuscleHead`.
This makes `feg:muscle rdfs:range feg:Muscle` accept any level uniformly.

The formal imprecision ("Shoulders is a Muscle") is real but inconsequential:
`feg:Muscle` functions as a vocabulary anchor, not an anatomical claim. The
`rdfs:comment` on `feg:Muscle` states this explicitly.

### Reify when role vocabulary is rich; use subproperties when it is binary

Reification adds a named node between two concepts. Pay that cost when:
- The relationship has a rich role vocabulary (4+ values), AND
- The named node needs to be manipulated independently (repair queries, deduplication)

`feg:MuscleInvolvement` satisfies both: four involvement degrees
(PrimeMover, Synergist, Stabilizer, PassiveTarget) and the node participates
in repair and deduplication queries. (ADR-002)

For binary distinctions, use `rdfs:subPropertyOf`. `feg:primaryJointAction` and
`feg:supportingJointAction` are subproperties of `feg:jointAction`. RDFS inference
collapses both into a single `feg:jointAction` query. One assertion per action,
no node overhead, no reification complexity. (ADR-058)

### Semantic disjointness for error prevention

Assert `owl:disjointWith` when two classes are semantically disjoint and confusion
between them is a real failure mode. `feg:Muscle owl:disjointWith feg:JointAction`
prevents joint action concept names from leaking into muscle involvements — a
documented LLM failure mode that occurred in production. The SHACL constraint
and the `owl:disjointWith` declaration reinforce each other. (ADR-061)

### Named individuals for flat enumerations

Flat, closed enumerations (InvolvementDegree, TrainingModality, Equipment,
Laterality, PlaneOfMotion, ExerciseStyle) are modeled as `owl:NamedIndividual`
instances of their respective classes. No hierarchy needed. Consistent pattern
across all enumerated vocabularies.

### URI conventions

- Exercises: `feg:ex_{id}` — `ex_` prefix prevents leading-numeral NCName issues
- MuscleInvolvements: `feg:inv_ex_{id}_{feg_local_name}_{degree}` — no spaces, no percent-encoding
- Hyphens in source IDs are normalized to underscores for URI hygiene
- `feg:legacySourceId` preserves the raw upstream ID for provenance (ADR-040)

---

## Rules as ontology — not prose

### SHACL is the authoritative source for pipeline rules

SHACL shapes enforce structural constraints AND inject instructional content
into the enrichment prompt. Do not maintain parallel rule sets.

- `sh:message` on SPARQL constraints → validation failure text
- `rdfs:comment` on property shapes → LLM enrichment instructions
- `skos:scopeNote` on vocabulary concepts → concept-level guidance

When a vocabulary change warrants a new constraint, add it to SHACL. The prompt
builder reads from SHACL at import time — the prompt automatically reflects
the updated constraint on next run. (ADR-045, ADR-071)

### Machine-readable signals over prose notes

Prefer a machine-readable property over a prose `skos:scopeNote` when the
behavior needs to be enforced by the pipeline. `feg:useGroupLevel true` replaced
prose scope notes on five muscle groups because the boolean is queryable by
the prompt builder and enforceable by SHACL. Prose notes are for documentation;
machine-readable properties are for pipeline behavior. (ADR-047)

### Post-ingest repair for vocabulary policy enforcement

The enrichment pipeline produces semantically reasonable but occasionally
vocabulary-inconsistent output. A post-build repair layer in `build.py` enforces
vocabulary policy at output time without touching source fidelity:

- `useGroupLevel` normalization: replace heads with their parent group at build time (ADR-096)
- Ancestor double-counting repair: strip lower-specificity terms when a more
  specific term for the same muscle mass is already present (ADR-070)

Repair is ontology-driven (reads `feg:useGroupLevel`, `skos:broader+`), not
SHACL-report-driven. SHACL validates; repair corrects. These are separate jobs.

---

## Versioning and governance

### Semantic versioning, independently per file

Every ontology file carries `owl:versionInfo` with an independent semantic version:
- **MAJOR**: breaking changes (remove or rename URIs)
- **MINOR**: additive changes (new concepts, new properties)
- **PATCH**: non-breaking corrections (labels, comments)

Files evolve at different rates for different reasons. Independent versioning
makes it observable which vocabulary changed and when. (ADR-029)

### Every non-trivial decision gets an ADR

`DECISIONS.md` is the institutional memory of this project. Write the ADR before
or immediately after making a change. The ADR records not just what was decided
but what was rejected and why — that is what makes it useful when the question
re-emerges.

Annotation-only changes (scope notes, labels, comments) are PATCH-level and
do not require an ADR. Concept addition, removal, or rename requires an ADR.

### Competency questions before vocabulary changes

Before adding or removing a concept, state the competency question it answers:
what query, filter, inference, or UI field fails or degrades today without it?
A concept that cannot be justified by a competency question is probably premature.

---

## Exercise domain specifics

### Involvement degree rules

- **PrimeMover**: the muscle's primary biomechanical function directly produces
  the exercise's defining joint action. Active via secondary function = Synergist.
- **Synergist**: assists or fine-tunes the prime mover.
- **Stabilizer**: isometrically holds a joint. Does not contribute to primary movement.
- **PassiveTarget**: tissue being lengthened. Mobility and SoftTissue exercises only.
- Every exercise needs at least one PrimeMover, OR at least one PassiveTarget
  (for Mobility/SoftTissue).
- `Core` (the convenience MuscleGroup) must always be Stabilizer. Use specific
  abdominals (RectusAbdominis, Obliques, TransverseAbdominis) for dedicated core exercises.
- A muscle may not appear more than once across an exercise's involvements.
- An exercise may not list both a muscle and any of its SKOS ancestors (double-counting).

### Movement pattern assignment rules

- Use the most specific child pattern, not the parent (Squat not KneeDominant).
- Compound exercises may have more than one pattern.
- Isolation exercises have no movement pattern. Return empty, do not force a label.
- Push and Pull require multi-joint force production. Single-joint isolation
  movements (bicep curls, lateral raises) have no movement pattern.

### Joint action assignment rules

- `primaryJointAction`: the joint actions that directly produce the defining movement.
  Typically 1–3. Leaf-level concepts only.
- `supportingJointAction`: contributions relevant for substitution, fatigue, or
  coordination. Not a biomechanical inventory — omit incidental actions.
- Setup positions are not joint actions. Only assign actions that occur during movement.
- Anti-movement exercises (plank = AntiExtension) → `feg:SpinalStability`.
  Do NOT assign SpinalExtension, SpinalRotation, etc. to isometric resistance exercises.
- A joint action may not appear in both primary and supporting.

### TrainingModality: assign only when defining

Assign `feg:trainingModality` only when the modality is a defining characteristic
of the exercise, not its typical training context. Most resistance training exercises
have no modality. Plyometrics and Mobility exercises nearly always do. Power modality
is for Olympic lifts and derivatives — explosive force under load, not
stretch-shortening cycle (which is Plyometrics). (ADR-021, ADR-050)
