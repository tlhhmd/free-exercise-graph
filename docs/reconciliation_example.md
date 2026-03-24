# Reconciliation Case Study: Dead Bug

This document traces a single exercise — **Dead Bug** — through every stage of
the pipeline to show how multiple source records become one canonical, enriched
entity.

---

## 1. Source records

Three distinct records across two upstream datasets match this exercise:

| Source | Record ID | Equipment |
|---|---|---|
| `free-exercise-db` | `Dead_Bug` | Bodyweight |
| `functional-fitness-db` | `Bodyweight_Dead_Bug` | Bodyweight |
| `functional-fitness-db` | `Kettlebell_Dead_Bug` | Kettlebell |

The Bodyweight and Kettlebell variants are separate records in the same source
dataset. `identity.py` scores all three as high-confidence matches against the
canonical exercise based on muscle overlap, movement pattern, and name similarity,
and clusters them into a single canonical entity: `feg:ex_dead_bug`.

---

## 2. Source claims

`canonicalize.py` collects every structured claim from all three records:

| Source | Predicate | Value | Qualifier |
|---|---|---|---|
| free-exercise-db | equipment | Bodyweight | — |
| functional-fitness-db | equipment | Bodyweight | — |
| functional-fitness-db | equipment | Kettlebell | — |
| functional-fitness-db | movement_pattern | AntiExtension | — |
| functional-fitness-db | movement_pattern | AntiExtension | — |
| functional-fitness-db | laterality | **Contralateral** | — |
| functional-fitness-db | laterality | **Unilateral** | — |
| functional-fitness-db | muscle | RectusAbdominis | prime |
| functional-fitness-db | muscle | Obliques | secondary |
| functional-fitness-db | muscle | RectusFemoris | tertiary |
| functional-fitness-db | is_compound | true | — |
| functional-fitness-db | exercise_style | Postural | — |
| functional-fitness-db | plane_of_motion | SagittalPlane | — |

Most claims are consistent across records. Two things stand out:

- **Equipment is intentionally multi-valued.** Both `Bodyweight` and `Kettlebell`
  are correct — the exercise exists in both forms. The reconciler unions these
  rather than forcing a single value.
- **Laterality is genuinely ambiguous.** `Bodyweight_Dead_Bug` says `Contralateral`
  (the right arm and left leg move together — anatomically precise). `Kettlebell_Dead_Bug`
  says `Unilateral` (only one limb at a time is loaded — equipment-centric framing).
  Both are defensible.

---

## 3. Conflict detection and resolution

`reconcile.py` applies a deterministic resolution algebra over the source claims.
It detects one conflict:

```
laterality: Sources disagree — Contralateral (functional-fitness-db/Bodyweight_Dead_Bug)
                                vs Unilateral (functional-fitness-db/Kettlebell_Dead_Bug)
```

The reconciler has no rule to resolve a within-source laterality conflict automatically,
so it **defers** the conflict and excludes `laterality` from the resolved claims layer.
The exercise proceeds through the pipeline — the pipeline is never blocked by unresolved
conflicts.

All other claims resolve cleanly:

| Predicate | Resolved value | How |
|---|---|---|
| equipment | Bodyweight, Kettlebell | Union (multi-valued field) |
| movement_pattern | AntiExtension | Unanimous across records |
| muscle | RectusAbdominis (PrimeMover), Obliques (Synergist), RectusFemoris (Stabilizer) | Unanimous; degrees normalised from `prime/secondary/tertiary` → `PrimeMover/Synergist/Stabilizer` |
| is_compound | true | Unanimous |
| exercise_style | Postural | Unanimous |
| plane_of_motion | SagittalPlane | Unanimous |

Note the degree normalisation: the source uses informal terms (`prime`, `secondary`,
`tertiary`); the reconciler maps these to the controlled `feg:InvolvementDegree` vocabulary
before writing to `resolved_claims`.

---

## 4. LLM enrichment

`enrich.py` receives the resolved claims and is asked to fill any missing fields.
`laterality` is absent from resolved claims — the LLM sees the exercise name, its
instructions, and the other resolved claims, and must infer it.

The model assigns `Contralateral` — the anatomically precise framing — and resolves the
conflict in a way consistent with the more specific of the two source values.

The LLM also adds depth that no source provided:

| Predicate | Inferred value | Notes |
|---|---|---|
| laterality | Contralateral | Resolved deferred conflict |
| muscle | TransverseAbdominis (PrimeMover) | Correctly identified; absent from source |
| muscle | ErectorSpinae (Stabilizer) | Correctly identified; absent from source |
| muscle | Iliopsoas (Stabilizer) | Correctly identified; absent from source |
| primary_joint_action | SpinalStability | Core stabilisation is the defining action |
| supporting_joint_action | HipFlexion, KneeExtension | Limb movements in the exercise |

---

## 5. Final entity

The assembled entity combines asserted (source-derived) and inferred (LLM-derived) claims,
with asserted claims always taking precedence:

```turtle
feg:ex_dead_bug
    a feg:Exercise ;
    rdfs:label "Dead Bug" ;
    feg:equipment feg:Bodyweight, feg:Kettlebell ;
    feg:movementPattern feg:AntiExtension ;
    feg:isCompound true ;
    feg:isCombination false ;
    feg:laterality feg:Contralateral ;
    feg:planeOfMotion feg:SagittalPlane ;
    feg:exerciseStyle feg:Postural ;
    feg:muscleInvolvement [
        feg:muscle feg:RectusAbdominis ; feg:degree feg:PrimeMover
    ] , [
        feg:muscle feg:TransverseAbdominis ; feg:degree feg:PrimeMover
    ] , [
        feg:muscle feg:Obliques ; feg:degree feg:Synergist
    ] , [
        feg:muscle feg:GluteusMaximus ; feg:degree feg:Synergist
    ] , [
        feg:muscle feg:RectusFemoris ; feg:degree feg:Stabilizer
    ] , [
        feg:muscle feg:ErectorSpinae ; feg:degree feg:Stabilizer
    ] , [
        feg:muscle feg:Iliopsoas ; feg:degree feg:Stabilizer
    ] ;
    feg:primaryJointAction feg:SpinalStability ;
    feg:supportingJointAction feg:HipFlexion, feg:KneeExtension .
```

---

## What this demonstrates

| Capability | Where shown |
|---|---|
| Cross-source identity resolution | 3 records from 2 datasets → 1 canonical entity |
| Vocabulary normalisation | `prime/secondary/tertiary` → controlled involvement degrees |
| Union semantics for multi-valued fields | Both equipment variants preserved |
| Conflict detection and deferral | Laterality conflict recorded, pipeline not blocked |
| LLM enrichment filling asserted gaps | Deferred laterality resolved; muscle depth added |
| Claim precedence | Asserted claims from sources take precedence over inferred |
