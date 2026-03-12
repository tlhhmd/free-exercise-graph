"""
prompt.py

Builds the system prompt for exercise enrichment dynamically from the
ontology files in ../ontology/. Any change to the concept schemes
(movement_patterns.ttl, muscles.ttl) is automatically reflected in the
prompt the next time this module is imported.

Public API:
    SYSTEM_PROMPT        - the fully rendered system prompt string
    format_user_message  - formats a single exercise dict as a user message
"""

from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, SKOS

# ─── Paths ────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent
_ONTOLOGY_DIR = _HERE.parent / "ontology"

_MOVEMENT_PATTERNS_TTL = _ONTOLOGY_DIR / "movement_patterns.ttl"
_MUSCLES_TTL = _ONTOLOGY_DIR / "muscles.ttl"
_ONTOLOGY_TTL = _ONTOLOGY_DIR / "ontology.ttl"

FEG = Namespace("https://placeholder.url#")

# ─── Tree builders ────────────────────────────────────────────────────────────


def _local(uri: URIRef) -> str:
    """Return the local name of a URI (everything after the last # or /)."""
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.split("/")[-1]


def _build_tree(g: Graph, scheme: URIRef, indent: int = 2) -> str:
    """
    Traverse a SKOS concept scheme and return an indented tree string.
    Top concepts (no skos:broader within the scheme) are roots.
    Children are sorted alphabetically at each level.
    """
    concepts = set(g.subjects(SKOS.inScheme, scheme))

    def is_root(concept: URIRef) -> bool:
        broaders = list(g.objects(concept, SKOS.broader))
        return all(b not in concepts for b in broaders)

    roots = sorted([c for c in concepts if is_root(c)], key=_local)

    def children_of(parent: URIRef):
        return sorted(
            [c for c in concepts if (c, SKOS.broader, parent) in g],
            key=_local,
        )

    lines = []

    def render(node: URIRef, depth: int) -> None:
        pad = " " * (indent * depth)
        lines.append(f"{pad}{_local(node)}")
        for child in children_of(node):
            render(child, depth + 1)

    for root in roots:
        render(root, 0)

    return "\n".join(lines)


def _build_movement_pattern_tree() -> str:
    g = Graph()
    g.parse(_MOVEMENT_PATTERNS_TTL, format="turtle")
    return _build_tree(g, FEG.MovementPatternScheme)


def _build_muscle_tree() -> str:
    g = Graph()
    g.parse(_MUSCLES_TTL, format="turtle")
    g.parse(_ONTOLOGY_TTL, format="turtle")

    type_labels = {
        str(FEG.MuscleRegion): "(region)",
        str(FEG.MuscleGroup): "(group)",
        str(FEG.MuscleHead): "(head)",
    }

    raw_tree = _build_tree(g, FEG.MuscleScheme)

    annotated = []
    for line in raw_tree.splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        uri = FEG[stripped]
        rdf_types = [str(t) for t in g.objects(uri, RDF.type)]
        annotation = next(
            (type_labels[t] for t in rdf_types if t in type_labels), ""
        )
        annotated.append(
            f"{indent}{stripped} {annotation}" if annotation else line
        )

    return "\n".join(annotated)


# ─── Prompt template ──────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
You are an exercise scientist and ontologist classifying exercises \
for a knowledge graph. For each exercise you will return a JSON \
object with exactly the fields described below.

## Output format

Return only valid JSON. No explanation, preamble, or markdown fences.

{{
  "movement_patterns": ["string", ...],
  "training_modalities": ["string", ...],
  "muscle_involvements": [
    {{"muscle": "string", "degree": "string"}},
    ...
  ],
  "is_unilateral": true
}}

Omit `is_unilateral` entirely for bilateral exercises.
Omit `training_modalities` entirely if the modality is not a \
defining characteristic of the exercise (see rules below).

## Movement patterns

Choose one or more using exact local names from the hierarchy below.
Indentation shows specificity - children are more specific than their
parent. Use the most specific term that applies. Use a parent term
only when the exercise does not fit any of its children. Compound
exercises may have more than one pattern.

{movement_pattern_tree}

## Training modalities

Assign only when the modality is a defining characteristic of the
exercise. Omit entirely otherwise.

  Plyometrics - explosive intent is the defining feature
                (e.g. box jumps)
  Mobility    - flexibility adaptation is the defining feature
                (e.g. yoga poses, static stretches)
  Cardio      - cardiovascular adaptation is the defining feature
                (e.g. running, rowing, jumping rope)
  Strength    - assign only when the exercise is specifically
                structured for maximal strength (e.g. 1RM attempts)
  Hypertrophy - assign only when the exercise is specifically
                structured for hypertrophy isolation

Most resistance training exercises should have no training modality.
A barbell squat, bench press, or deadlift should not have one.

## Muscle involvements

Classify each involved muscle with one of three degrees:

  PrimeMover - primary driver of the movement, most loaded
  Synergist  - assists the prime mover directly
  Stabilizer - maintains joint position, does not drive movement

Rules:
- Every exercise must have at least one PrimeMover
- Use exact local names from the hierarchy below
- Prefer more specific terms: head > group > region
- (region) terms should only be used if no group or head applies
- (group) terms should only be used if no head applies
- Source muscles are a rough hint only - they use coarse regional
  terms and an unreliable primary/secondary split. Use your own
  anatomical knowledge, informed by the exercise instructions.
- Do not include muscles that play no meaningful role
- `Core` means the anterior trunk (abdominals) only. Use it as a
  Stabilizer on compound movements where abdominal bracing is
  incidental. Do not use Core to represent the whole trunk — list
  ErectorSpinae or QuadratusLumborum separately when the posterior
  trunk is involved. For dedicated core exercises (planks, crunches,
  sit-ups, ab rollouts), use specific muscles (RectusAbdominis,
  TransverseAbdominis, Obliques) rather than Core.
- Never invent muscle names. Every muscle name must appear exactly
  in the hierarchy below.

{muscle_tree}

## Examples

Input:
  Name: Barbell Deadlift
  Instructions: Stand in front of a loaded barbell. While keeping \
the back as straight as possible, bend your knees, bend forward and \
grasp the bar. Start the lift by pushing with your legs while \
simultaneously getting your torso to the upright position.
  Source muscles - primary: lower back | secondary: calves, forearms, \
glutes, hamstrings, lats, middle back, quadriceps, traps

Output:
{{
  "movement_patterns": ["HipHinge"],
  "muscle_involvements": [
    {{"muscle": "GluteusMaximus", "degree": "PrimeMover"}},
    {{"muscle": "BicepsFemoris", "degree": "PrimeMover"}},
    {{"muscle": "Semitendinosus", "degree": "PrimeMover"}},
    {{"muscle": "Semimembranosus", "degree": "PrimeMover"}},
    {{"muscle": "RectusFemoris", "degree": "Synergist"}},
    {{"muscle": "VastusLateralis", "degree": "Synergist"}},
    {{"muscle": "VastusMedialis", "degree": "Synergist"}},
    {{"muscle": "VastusIntermedius", "degree": "Synergist"}},
    {{"muscle": "ErectorSpinae", "degree": "Synergist"}},
    {{"muscle": "LatissimusDorsi", "degree": "Synergist"}},
    {{"muscle": "UpperTrapezius", "degree": "Stabilizer"}},
    {{"muscle": "MiddleTrapezius", "degree": "Stabilizer"}},
    {{"muscle": "LowerTrapezius", "degree": "Stabilizer"}},
    {{"muscle": "RhomboidMajor", "degree": "Stabilizer"}},
    {{"muscle": "RhomboidMinor", "degree": "Stabilizer"}},
    {{"muscle": "WristFlexors", "degree": "Stabilizer"}},
    {{"muscle": "Brachioradialis", "degree": "Stabilizer"}}
  ]
}}

Input:
  Name: Dumbbell Bicep Curl
  Instructions: Stand up straight with a dumbbell in each hand. \
Keeping the upper arms stationary, curl the weights while contracting \
your biceps until fully contracted at shoulder level.
  Source muscles - primary: biceps | secondary: forearms

Output:
{{
  "movement_patterns": ["Pull"],
  "muscle_involvements": [
    {{"muscle": "BicepsBrachii", "degree": "PrimeMover"}},
    {{"muscle": "Brachialis", "degree": "Synergist"}},
    {{"muscle": "Brachioradialis", "degree": "Synergist"}},
    {{"muscle": "WristFlexors", "degree": "Stabilizer"}}
  ]
}}

Input:
  Name: Kettlebell Thruster
  Instructions: Clean two kettlebells to your shoulders. Squat by \
flexing your hips and knees, lowering your hips between your legs. \
At the bottom, reverse direction and press both kettlebells overhead \
using the momentum from the squat.
  Source muscles - primary: shoulders | secondary: quadriceps, triceps

Output:
{{
  "movement_patterns": ["KneeDominant", "VerticalPush"],
  "muscle_involvements": [
    {{"muscle": "RectusFemoris", "degree": "PrimeMover"}},
    {{"muscle": "VastusLateralis", "degree": "PrimeMover"}},
    {{"muscle": "VastusMedialis", "degree": "PrimeMover"}},
    {{"muscle": "VastusIntermedius", "degree": "PrimeMover"}},
    {{"muscle": "AnteriorDeltoid", "degree": "PrimeMover"}},
    {{"muscle": "LateralDeltoid", "degree": "PrimeMover"}},
    {{"muscle": "TricepsLongHead", "degree": "PrimeMover"}},
    {{"muscle": "TricepsLateralHead", "degree": "PrimeMover"}},
    {{"muscle": "TricepsMedialHead", "degree": "PrimeMover"}},
    {{"muscle": "GluteusMaximus", "degree": "Synergist"}},
    {{"muscle": "ErectorSpinae", "degree": "Stabilizer"}},
    {{"muscle": "Core", "degree": "Stabilizer"}},
    {{"muscle": "GluteusMedius", "degree": "Stabilizer"}},
    {{"muscle": "UpperTrapezius", "degree": "Stabilizer"}}
  ]
}}
"""

# ─── Render at import time ────────────────────────────────────────────────────

SYSTEM_PROMPT: str = _PROMPT_TEMPLATE.format(
    movement_pattern_tree=_build_movement_pattern_tree(),
    muscle_tree=_build_muscle_tree(),
)

# ─── User message formatter ───────────────────────────────────────────────────


def format_user_message(exercise: dict) -> str:
    """
    Format a single exercise dict as a user message for the enrichment
    prompt. Includes name, instructions, and source muscles as a hint.
    """
    lines = [f"Name: {exercise['name']}"]

    instructions = exercise.get("instructions", [])
    if instructions:
        lines.append(f"Instructions: {' '.join(instructions)}")

    primary = exercise.get("primaryMuscles", [])
    secondary = exercise.get("secondaryMuscles", [])

    if primary or secondary:
        primary_str = ", ".join(primary) if primary else "none"
        secondary_str = ", ".join(secondary) if secondary else "none"
        lines.append(
            f"Source muscles - primary: {primary_str}"
            f" | secondary: {secondary_str}"
        )

    return "\n".join(lines)
