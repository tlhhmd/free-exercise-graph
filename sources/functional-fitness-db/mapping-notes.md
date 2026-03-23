# Functional Fitness DB → FEG Ontology: Field Mapping Decisions

Source: Strength to Overcome — Functional Fitness Exercise Database v29
Fields: 31 (col 0 blank, cols 1–31 are data)
Exercises: ~3,240

---

## Field Decision Log

| # | Source Field | Status | Decision |
|---|---|---|---|
| 1 | Exercise | ✅ | `rdfs:label` + URI `feg:ex_{sanitize_id(name)}`. Collisions with free-exercise-db are intentional — same exercise, same node, multi-source triples. |
| 2 | Short YouTube Demonstration | ✅ | Drop — hyperlinks in Excel but openpyxl data_only=True loses them; only display text survives |
| 3 | In-Depth YouTube Explanation | ✅ | Drop — hyperlinks lost at fetch; only display text survives |
| 4 | Difficulty Level | ✅ | Drop — domain-expert judgment required to validate or remap the 8-tier scale; not qualified to assess |
| 5 | Target Muscle Group | ✅ | Crosswalk → `feg:MuscleRegion` (storage decision deferred) |
| 6 | Prime Mover Muscle | ✅ | Crosswalk → `feg:MuscleInvolvement` degree `feg:PrimeMover`. Needs `muscle_crosswalk.csv` (source anatomical names → `feg:` local names) |
| 7 | Secondary Muscle | ✅ | Same crosswalk → `feg:MuscleInvolvement` degree `feg:Synergist` |
| 8 | Tertiary Muscle | ✅ | Same crosswalk → `feg:MuscleInvolvement` degree `feg:Stabilizer` |
| 9 | Primary Equipment | ✅ | Crosswalk → `feg:equipment`. Novel items need ADR + MINOR bump on `equipment.ttl` |
| 10 | # Primary Items | ✅ | Drop — values 1 or 2; no signal for search, substitution, or muscle targeting |
| 11 | Secondary Equipment | ✅ | Flatten into `feg:equipment` — same crosswalk as Primary Equipment. No role distinction stored; both are required equipment for the exercise |
| 12 | # Secondary Items | ✅ | Drop — values 0–2; no signal |
| 13 | Posture | ✅ | Drop for now — backlogged. Strong clinical use case but 37 values blur multiple axes; needs kinesiologist validation before modeling |
| 14 | Single or Double Arm | ✅ | Drop — superseded by Laterality (field 30); "No Arms" captured by muscle involvements |
| 15 | Continuous or Alternating Arms | ✅ | Drop — too implementation-specific; not a property we'd query on |
| 16 | Grip | ✅ | Drop — not a property any of our four personas would query on |
| 17 | Load Position (Ending) | ✅ | Drop — endpoint-specific, not a stable exercise property |
| 18 | Continuous or Alternating Legs | ✅ | Drop — too implementation-specific; mirror of field 15 |
| 19 | Foot Elevation | ✅ | Drop — setup modifier, not a stable exercise property |
| 20 | Combination Exercises | ✅ | New property `feg:isCombination` (boolean). Combo Exercise→true, Single Exercise→false. Backfill required for free-exercise-db via LLM enrichment pass |
| 21 | Movement Pattern #1 | ✅ | Crosswalk with `target_property` column — routes to `feg:movementPattern` or `feg:jointAction` based on value. Novel movement patterns need ADR + MINOR bump on `movement_patterns.ttl` |
| 22 | Movement Pattern #2 | ✅ | Same crosswalk as field 21 |
| 23 | Movement Pattern #3 | ✅ | Same crosswalk as field 21 |
| 24 | Plane Of Motion #1 | ✅ | New property `feg:planeOfMotion` → new `planes_of_motion.ttl` (3 concepts: Sagittal, Frontal, Transverse). Backfill required for free-exercise-db via LLM enrichment pass |
| 25 | Plane Of Motion #2 | ✅ | Same property as field 24 |
| 26 | Plane Of Motion #3 | ✅ | Same property as field 24 |
| 27 | Body Region | ✅ | Keep as enrichment context — useful LLM anchor, especially for full body exercises. Storage decision deferred |
| 28 | Force Type | ✅ | Drop — superseded by movement patterns; Push/Pull already captured with more precision |
| 29 | Mechanics | ✅ | `feg:isCompound` boolean. Compound→true, Isolation→false. "Pull" = data error, flag for manual review during ingest |
| 30 | Laterality | ✅ | Replace `feg:isUnilateral` boolean with `feg:laterality` → 4-value SKOS vocabulary (Bilateral, Unilateral, Contralateral, Ipsilateral). Breaking change: MAJOR bump + ADR required. Backfill free-exercise-db via LLM enrichment pass |
| 31 | Primary Exercise Classification | ✅ | New property `feg:exerciseStyle` → new `exercise_styles.ttl`. Definition: "a category describing the training system, tradition, or methodological context an exercise belongs to." Distinct from `feg:trainingModality` (physiological adaptation). Needs ADR + MINOR bump on ontology. Values to review: Bodybuilding, Calisthenics, Powerlifting, Olympic Weightlifting, Plyometric, Mobility, Postural, Animal Flow, Ballistics, Grinds, Balance. Drop: Unsorted* |

---

## Decision Details

### Fields 1–3, 5, 10, 12, 14–15, 17–19, 27–28 — Drops
No decision needed. See table above for rationale.

### Fields 6–8 — Muscle Involvements
Muscle names in this source are anatomical (e.g. "Rectus Abdominis", "Biceps Femoris").
Our `muscles.ttl` uses colloquial names at head level. Need a `muscle_crosswalk.csv` mapping
source strings → `feg:` local names. Same pattern as `equipment_crosswalk.csv`.
Strip trailing spaces on ingest — several values have them (e.g. "Anterior Deltoids ").

### Field 9 + 11 — Equipment
Novel equipment not in current `equipment.ttl`:
Ab Wheel, Battle Ropes, Bulgarian Bag, Clubbell, Gymnastic Rings, Landmine, Macebell,
Miniband, Parallette Bars, Sandbag, Sledge Hammer, Slant Board, Stability Ball,
Steel Club, Suspension Trainer, Weight Vest, Wrist Roller.
These require an ADR and a MINOR version bump on `equipment.ttl`.

### Fields 21–23 — Movement Patterns / Joint Actions
Source uses a flat "Movement Pattern" field that conflates two distinct FEG concepts.
Crosswalk (`movement_pattern_crosswalk.csv`) must include a `target_property` column:
- `feg:movementPattern` — Hip Hinge, Knee Dominant, Horizontal Push/Pull, Vertical Push/Pull,
  Rotational, Anti-Extension, Anti-Flexion, Anti-Lateral Flexion, Anti-Rotational,
  Lateral Flexion, Lateral Locomotion, Loaded Carry, Locomotion, Isometric Hold, Hip Dominant
- `feg:jointAction` — Ankle Dorsiflexion, Ankle Plantar Flexion, Elbow Extension/Flexion,
  Hip Abduction/Adduction/Extension/ExternalRotation/Flexion/InternalRotation,
  Scapular Elevation, Shoulder Abduction/ExternalRotation/Flexion/InternalRotation,
  Shoulder Scapular Plane Elevation, Spinal Extension/Flexion, Wrist Extension/Flexion

Ingest script reads `target_property` and routes each value to the correct RDF property.
Novel movement pattern values (Anti-*, Isometric Hold, etc.) need ADR + MINOR bump on `movement_patterns.ttl`.
Drop: `Other`, `Unsorted*`.

### Field 29 — Mechanics
Data error: "Pull" appears as a Mechanics value (it's a Force Type value). Treat as unknown,
flag for review during ingest.

---

## Open Decisions

### Field 4 — Difficulty Level
**Source values:** Beginner, Novice, Intermediate, Advanced, Master, Expert, Grand Master, Legendary

**Options:**
1. All 8 as-is → new `difficulty_levels.ttl` vocabulary
2. Collapse to 5: Beginner / Novice / Intermediate / Advanced / Expert (drop top 3)
3. Skip entirely

**Rec:** Collapse to 5. Top 3 (Grand Master, Legendary + Master debatable) are novelty tiers
specific to this source's gamification. A 5-level scale is portable across sources and
meaningful to a broad audience (Beginner through Expert covers all real use cases).

---
