"""
enrichment/schema.py

Pydantic output model for FEG exercise enrichment — shared across all source pipelines.

The ExerciseEnrichment model is the contract between the LLM and the pipeline's
inferred_claims table. Validators enforce ontology constraints at parse time.

Call setup_validators(graphs) once after loading ontology graphs before validating any output.
"""

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, PrivateAttr, ValidationError, model_validator
from rdflib import Graph, Literal as RDFLiteral, Namespace, URIRef
from rdflib.namespace import RDF, SKOS

# Ensure project root is on the path so `constants` is importable regardless of
# which directory the calling script runs from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from constants import FEG_NS

FEG = Namespace(FEG_NS)

# ─── Validator state (populated by setup_validators) ──────────────────────────

_ANCESTOR_MAP: dict[str, frozenset[str]] = {}
_USE_GROUP_LEVEL_HEADS: frozenset[str] = frozenset()
_HEAD_TO_GROUP_MAP: dict[str, str] = {}
_KNOWN_VOCAB: dict[str, frozenset[str]] = {}
_ALTLABEL_NORM: dict[str, dict[str, str]] = {}
# Maps {vocab_key: {altlabel_value: canonical_local_name}}


# ─── Models ───────────────────────────────────────────────────────────────────


class MuscleInvolvement(BaseModel):
    muscle: str
    degree: Literal["PrimeMover", "Synergist", "Stabilizer", "PassiveTarget"]


class ExerciseEnrichment(BaseModel):
    movement_patterns: list[str] = []
    training_modalities: list[str] = []
    muscle_involvements: list[MuscleInvolvement]
    primary_joint_actions: list[str] = []
    supporting_joint_actions: list[str] = []
    is_compound: bool | None = None
    laterality: Literal["Bilateral", "Unilateral", "Contralateral", "Ipsilateral"] | None = None
    is_combination: bool | None = None
    plane_of_motion: list[str] = []
    exercise_style: list[str] = []

    # Collects (predicate, stripped_value) pairs during validation — persisted to
    # enrichment_warnings by _write_inferred so vocab updates can trigger re-enrichment.
    _warnings: list[tuple[str, str]] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def auto_correct_cross_vocab(self) -> "ExerciseEnrichment":
        """Remove cross-vocab placements only when the term is also correctly placed.

        If ScapularUpwardRotation appears in muscle_involvements AND in
        supporting_joint_actions, strip it from muscle_involvements and keep the
        correct placement. If it appears in muscle_involvements but NOT in any
        joint action field, leave it for check_vocabulary to reject.
        Same logic applies in reverse (muscle term in joint action fields).
        """
        if not _KNOWN_VOCAB:
            return self

        joint_action_vocab = _KNOWN_VOCAB.get("joint_actions", frozenset())
        muscle_vocab = _KNOWN_VOCAB.get("muscles", frozenset())
        movement_pattern_vocab = _KNOWN_VOCAB.get("movement_patterns", frozenset())

        placed_joint_actions = set(self.primary_joint_actions) | set(self.supporting_joint_actions)
        placed_muscles = {inv.muscle for inv in self.muscle_involvements}
        placed_patterns = set(self.movement_patterns)

        # Joint action term in muscle_involvements AND correctly in joint actions → strip
        self.muscle_involvements = [
            inv for inv in self.muscle_involvements
            if not (inv.muscle in joint_action_vocab and inv.muscle in placed_joint_actions)
        ]

        # Muscle term in joint action fields AND correctly in muscle_involvements → strip
        self.primary_joint_actions = [
            ja for ja in self.primary_joint_actions
            if not (ja in muscle_vocab and ja in placed_muscles)
        ]
        self.supporting_joint_actions = [
            ja for ja in self.supporting_joint_actions
            if not (ja in muscle_vocab and ja in placed_muscles)
        ]

        # Movement pattern term in joint action fields AND correctly in movement_patterns → strip
        self.primary_joint_actions = [
            ja for ja in self.primary_joint_actions
            if not (ja in movement_pattern_vocab and ja in placed_patterns)
        ]
        self.supporting_joint_actions = [
            ja for ja in self.supporting_joint_actions
            if not (ja in movement_pattern_vocab and ja in placed_patterns)
        ]

        return self

    @model_validator(mode="after")
    def check_vocabulary(self) -> "ExerciseEnrichment":
        """Strip unknown vocab terms and warn — do not hard-fail."""
        warns = []

        ja_vocab = _KNOWN_VOCAB.get("joint_actions", set())
        bad_pja = [ja for ja in self.primary_joint_actions if ja not in ja_vocab]
        if bad_pja:
            self.primary_joint_actions = [ja for ja in self.primary_joint_actions if ja in ja_vocab]
            for ja in bad_pja:
                self._warnings.append(("primary_joint_action", ja))
                warns.append(f"stripped unknown primary_joint_action: {ja!r}")

        bad_sja = [ja for ja in self.supporting_joint_actions if ja not in ja_vocab]
        if bad_sja:
            self.supporting_joint_actions = [ja for ja in self.supporting_joint_actions if ja in ja_vocab]
            for ja in bad_sja:
                self._warnings.append(("supporting_joint_action", ja))
                warns.append(f"stripped unknown supporting_joint_action: {ja!r}")

        mp_vocab = _KNOWN_VOCAB.get("movement_patterns", set())
        bad_mp = [mp for mp in self.movement_patterns if mp not in mp_vocab]
        if bad_mp:
            self.movement_patterns = [mp for mp in self.movement_patterns if mp in mp_vocab]
            for mp in bad_mp:
                self._warnings.append(("movement_pattern", mp))
                warns.append(f"stripped unknown movement_pattern: {mp!r}")

        tm_vocab = _KNOWN_VOCAB.get("training_modalities", set())
        bad_tm = [tm for tm in self.training_modalities if tm not in tm_vocab]
        if bad_tm:
            self.training_modalities = [tm for tm in self.training_modalities if tm in tm_vocab]
            for tm in bad_tm:
                self._warnings.append(("training_modality", tm))
                warns.append(f"stripped unknown training_modality: {tm!r}")

        mu_vocab = _KNOWN_VOCAB.get("muscles", set())
        bad_mu = [inv.muscle for inv in self.muscle_involvements if inv.muscle not in mu_vocab]
        if bad_mu:
            self.muscle_involvements = [inv for inv in self.muscle_involvements if inv.muscle in mu_vocab]
            for m in bad_mu:
                self._warnings.append(("muscle", m))
                warns.append(f"stripped unknown muscle: {m!r}")

        pom_vocab = _KNOWN_VOCAB.get("planes_of_motion", set())
        bad_pom = [pom for pom in self.plane_of_motion if pom not in pom_vocab]
        if bad_pom:
            self.plane_of_motion = [pom for pom in self.plane_of_motion if pom in pom_vocab]
            for pom in bad_pom:
                self._warnings.append(("plane_of_motion", pom))
                warns.append(f"stripped unknown plane_of_motion: {pom!r}")

        es_vocab = _KNOWN_VOCAB.get("exercise_styles", set())
        bad_es = [es for es in self.exercise_style if es not in es_vocab]
        if bad_es:
            self.exercise_style = [es for es in self.exercise_style if es in es_vocab]
            for es in bad_es:
                self._warnings.append(("exercise_style", es))
                warns.append(f"stripped unknown exercise_style: {es!r}")

        if warns:
            print(f"  ⚠ vocab: {'; '.join(warns)}", file=sys.stderr)

        return self

    @model_validator(mode="after")
    def check_prime_mover(self) -> "ExerciseEnrichment":
        degrees = {inv.degree for inv in self.muscle_involvements}
        if "PrimeMover" not in degrees and "PassiveTarget" not in degrees:
            raise ValueError(
                "At least one PrimeMover or PassiveTarget involvement required"
            )
        return self

    @model_validator(mode="after")
    def check_core_stabilizer(self) -> "ExerciseEnrichment":
        """Correct Core to Stabilizer if assigned a different degree — do not hard-fail."""
        corrected = []
        for inv in self.muscle_involvements:
            if inv.muscle == "Core" and inv.degree != "Stabilizer":
                print(f"  ⚠ corrected Core from {inv.degree!r} to 'Stabilizer'", file=sys.stderr)
                corrected.append(MuscleInvolvement(muscle="Core", degree="Stabilizer"))
            else:
                corrected.append(inv)
        self.muscle_involvements = corrected
        return self

    @model_validator(mode="after")
    def check_use_group_level(self) -> "ExerciseEnrichment":
        """Auto-correct useGroupLevel heads to their parent group."""
        if not any(inv.muscle in _USE_GROUP_LEVEL_HEADS for inv in self.muscle_involvements):
            return self
        seen: set[str] = set()
        corrected: list[MuscleInvolvement] = []
        for inv in self.muscle_involvements:
            muscle = _HEAD_TO_GROUP_MAP.get(inv.muscle, inv.muscle)
            if muscle not in seen:
                seen.add(muscle)
                corrected.append(MuscleInvolvement(muscle=muscle, degree=inv.degree))
        self.muscle_involvements = corrected
        return self

    @model_validator(mode="after")
    def check_no_duplicate_muscles(self) -> "ExerciseEnrichment":
        """Keep first occurrence of each muscle, strip duplicates, warn."""
        seen: set[str] = set()
        deduped = []
        for inv in self.muscle_involvements:
            if inv.muscle in seen:
                print(f"  ⚠ stripped duplicate muscle: {inv.muscle!r}", file=sys.stderr)
            else:
                seen.add(inv.muscle)
                deduped.append(inv)
        self.muscle_involvements = deduped
        return self

    @model_validator(mode="after")
    def check_no_ancestor_overlap(self) -> "ExerciseEnrichment":
        """Strip ancestor when both ancestor and descendant are present, warn."""
        muscles = {inv.muscle for inv in self.muscle_involvements}
        to_remove: set[str] = set()
        warns = []
        for m in muscles:
            for anc in _ANCESTOR_MAP.get(m, frozenset()):
                if anc in muscles and anc not in to_remove:
                    to_remove.add(anc)
                    warns.append(f"stripped ancestor {anc!r} (descendant {m!r} present)")
        if to_remove:
            self.muscle_involvements = [inv for inv in self.muscle_involvements if inv.muscle not in to_remove]
            print(f"  ⚠ ancestor overlap: {'; '.join(warns)}", file=sys.stderr)
        return self


# ─── Pre-validation normalisation ────────────────────────────────────────────


def normalize_casing(obj: dict) -> dict:
    """Normalize vocab terms before Pydantic validation.

    Two passes:
    1. altLabel normalization — maps known altLabel synonyms to canonical names
       (e.g. 'ShoulderDepression' → 'ScapularDepression')
    2. Case normalization — corrects wrong capitalisation
       (e.g. 'BrachioRadialis' → 'Brachioradialis')

    Operates on a shallow copy of the dict — does not mutate the original.
    Must be called after setup_validators() has populated _KNOWN_VOCAB.
    """
    if not _KNOWN_VOCAB:
        return obj

    obj = dict(obj)

    list_field_map = {
        "movement_patterns":        "movement_patterns",
        "training_modalities":      "training_modalities",
        "primary_joint_actions":    "joint_actions",
        "supporting_joint_actions": "joint_actions",
        "plane_of_motion":          "planes_of_motion",
        "exercise_style":           "exercise_styles",
    }

    # Pass 1: altLabel → canonical name
    if _ALTLABEL_NORM:
        if involvements := obj.get("muscle_involvements"):
            alt_map = _ALTLABEL_NORM.get("muscles", {})
            obj["muscle_involvements"] = [
                {**dict(inv), "muscle": alt_map.get(inv.get("muscle", ""), inv.get("muscle", ""))}
                for inv in involvements
            ]
        for field, vocab_key in list_field_map.items():
            alt_map = _ALTLABEL_NORM.get(vocab_key, {})
            if values := obj.get(field):
                obj[field] = [alt_map.get(v, v) for v in values]

    # Pass 2: case normalization
    lower_maps = {
        field: {term.lower(): term for term in terms}
        for field, terms in _KNOWN_VOCAB.items()
    }

    if involvements := obj.get("muscle_involvements"):
        corrected = []
        for inv in involvements:
            inv = dict(inv)
            raw = inv.get("muscle", "")
            lmap = lower_maps.get("muscles", {})
            inv["muscle"] = lmap.get(raw.lower(), lmap.get(raw.replace(" ", "").lower(), raw))
            corrected.append(inv)
        obj["muscle_involvements"] = corrected

    for field, vocab_key in list_field_map.items():
        lmap = lower_maps.get(vocab_key, {})
        if values := obj.get(field):
            obj[field] = [lmap.get(v.lower(), lmap.get(v.replace(" ", "").lower(), v)) for v in values]

    return obj


# ─── Validator setup ──────────────────────────────────────────────────────────


def setup_validators(graphs: dict[str, Graph]) -> None:
    """Precompute lookup tables needed by ExerciseEnrichment validators.

    Must be called once after loading ontology graphs, before validating any output.
    graphs must contain at least a "muscles" key.
    """
    global _ANCESTOR_MAP, _USE_GROUP_LEVEL_HEADS, _HEAD_TO_GROUP_MAP, _KNOWN_VOCAB, _ALTLABEL_NORM

    from enrichment._vocab import extract_vocab_sets

    muscle_graph = graphs["muscles"]

    def local(uri: URIRef) -> str:
        return str(uri).split("#")[-1]

    def ancestors_of(uri: URIRef) -> frozenset[str]:
        result: set[str] = set()
        queue = list(muscle_graph.objects(uri, SKOS.broader))
        while queue:
            parent = queue.pop()
            name = local(parent)
            if name not in result:
                result.add(name)
                queue.extend(muscle_graph.objects(parent, SKOS.broader))
        return frozenset(result)

    all_muscles = (
        set(muscle_graph.subjects(RDF.type, FEG.Muscle))
        | set(muscle_graph.subjects(RDF.type, FEG.MuscleRegion))
        | set(muscle_graph.subjects(RDF.type, FEG.MuscleGroup))
        | set(muscle_graph.subjects(RDF.type, FEG.MuscleHead))
    )
    _ANCESTOR_MAP = {local(m): ancestors_of(m) for m in all_muscles}

    head_to_group: dict[str, str] = {}
    for group in muscle_graph.subjects(FEG.useGroupLevel, RDFLiteral(True)):
        for head in muscle_graph.subjects(SKOS.broader, group):
            if (head, RDF.type, FEG.MuscleHead) in muscle_graph:
                head_to_group[local(head)] = local(group)
    _USE_GROUP_LEVEL_HEADS = frozenset(head_to_group)
    _HEAD_TO_GROUP_MAP = head_to_group

    _KNOWN_VOCAB = {k: frozenset(v) for k, v in extract_vocab_sets(graphs, FEG).items()}

    # Build altLabel → canonical name maps for each vocab graph
    vocab_graph_keys = {
        "joint_actions":     "joint_actions",
        "movement_patterns": "movement_patterns",
        "muscles":           "muscles",
        "training_modalities": "modalities",
        "planes_of_motion":  "planes_of_motion",
        "exercise_styles":   "exercise_styles",
    }
    altlabel_norm: dict[str, dict[str, str]] = {}
    for vocab_key, graph_key in vocab_graph_keys.items():
        if graph_key not in graphs:
            continue
        g = graphs[graph_key]
        m: dict[str, str] = {}
        for subj in g.subjects(SKOS.altLabel, None):
            canonical = str(subj).split("#")[-1]
            for alt in g.objects(subj, SKOS.altLabel):
                m[str(alt)] = canonical
        if m:
            altlabel_norm[vocab_key] = m
    _ALTLABEL_NORM = altlabel_norm
