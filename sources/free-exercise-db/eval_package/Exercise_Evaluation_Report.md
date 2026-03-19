# Exercise Classification Evaluation Report

**Date:** March 19, 2026
**Subject:** Review of LLM Enrichment for `exercises.json`
**Evaluators:** Senior Fitness Consultant & Lead Ontologist

---

## 1. Executive Summary
This report evaluates the semantic enrichment of the Free Exercise Graph dataset. While the LLM successfully identified general muscle regions, it frequently failed to adhere to strict ontological constraints regarding muscle granularity and biomechanical roles [cite: 1, 7]. Key areas of concern include the violation of "Group-Level" usage flags and the over-classification of Prime Movers in compound movements [cite: 1, 6].

---

## 2. Core Ontological Violations

### 2.1 Group-Level Rule Defiance
The ontology specifies a `feg:useGroupLevel` property for certain muscle groups where individual heads cannot be meaningfully targeted in a training context [cite: 1]. 
* The instructions explicitly list groups such as **Obliques**, **Rhomboids**, **Rotator Cuff**, and **Gastrocnemius** as mandatory group-level terms [cite: 7]. 
* The enrichment in `exercises.json` frequently defaulted to specific heads (e.g., `RhomboidMajor`, `MedialGastrocnemius`), which violates the hierarchy defined in the muscle vocabulary [cite: 5, 6].

### 2.2 Inconsistent Role Assignment
The definitions for involvement degrees were applied inconsistently across the dataset [cite: 3, 7].
* **Prime Mover**: The muscle primarily responsible for producing the movement [cite: 3].
* **Synergist**: A muscle that assists the prime mover meaningfully but is not the primary target [cite: 3].
* **Stabilizer**: A muscle that contracts to stabilize a joint without contributing directly to the movement [cite: 3].
* **Evaluation**: In many instances, the LLM elevated stabilizers to synergists or synergists to prime movers, diluting the data's utility for exercise substitution queries [cite: 6, 7].

---

## 3. Detailed Exercise Review (Select Samples)

| Exercise ID | Status | Feedback & Corrections |
| :--- | :---: | :--- |
| `90_90_Hamstring` | 🚩 **FLAG** | **Ontology**: Violated the preference for group-level usage for Hamstrings [cite: 5, 6]. **Biomechanical**: `Core` recruitment is listed as a `Stabilizer` but is negligible in a supine stretch [cite: 6]. |
| `Ab_Roller` | 🚩 **FLAG** | **Biomechanical**: `LatissimusDorsi` functions as a **Stabilizer** to prevent shoulder hyperextension, not a `Synergist` [cite: 6]. **Ontology**: `TrainingModality` is empty; it should be categorized as `Strength` or trunk stability [cite: 2, 4]. |
| `Advanced_Kettlebell_Windmill` | 🚩 **FLAG** | **Biomechanical**: `AnteriorDeltoid` and `LateralDeltoid` act as **Stabilizers** for isometric lockouts, not `Synergists` producing movement [cite: 6]. |
| `Alternate_Hammer_Curl` | 🚩 **FLAG** | **Biomechanical**: Neutral grip mechanics require `Brachialis` and `Brachioradialis` to be elevated to **PrimeMover** status alongside Biceps [cite: 6]. |
| `Atlas_Stones` | 🚩 **FLAG** | **Ontology**: Violated the `useGroupLevel` rule for **Rhomboids** [cite: 1, 6]. **Biomechanical**: Correct use of `WristFlexors` as stabilizers [cite: 6]. |
| `Clean_and_Press` | 🚩 **FLAG** | **Ontology**: Excessive `PrimeMover` count (10+ entries) [cite: 6]. **Correction**: `GluteusMaximus` and `AnteriorDeltoid` are the primary phase drivers [cite: 6]. |
| `Dumbbell_Side_Bend` | ✅ **PASS** | Correct application of the `Obliques` group-level rule [cite: 1] and the `is_unilateral` flag [cite: 6]. |

---

## 4. Recommendations for Pipeline Adjustment
1. **Strict Hierarchy Enforcement**: Implement hard filters to reject head-level IDs for any muscle marked `feg:useGroupLevel true` in the ontology [cite: 1, 5].
2. **Modality Logic**: Ensure all "Stretches" or "SMR" exercises automatically trigger the `Mobility` modality assignment [cite: 2, 7].
3. **Phase Separation**: For multi-phase exercises, identify only absolute primary drivers for each phase to avoid "Prime Mover Bloat" [cite: 6, 7].
