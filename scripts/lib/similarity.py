from __future__ import annotations

import re
from collections import defaultdict
from itertools import islice

from scripts.lib.feature_normalize import NormalizedExerciseFeature

_INDEX_FIELDS = (
    "movement_patterns",
    "prime_movers",
)


def _humanize(value: str) -> str:
    text = value.replace("_", " ").replace("-", " ")
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return re.sub(r"\s+", " ", text).strip()


def _round_score(value: float) -> float:
    return round(value, 4)


def _shared_summary(
    label: str,
    shared_values: list[str],
    contribution: float,
) -> tuple[float, str] | None:
    if not shared_values or contribution <= 0:
        return None
    display = ", ".join(_humanize(value) for value in islice(shared_values, 2))
    if len(shared_values) > 2:
        display = f"{display} +{len(shared_values) - 2}"
    return (contribution, f"Shared {label}: {display}")


def summarize_breakdown(breakdown: dict) -> str:
    reasons: list[tuple[float, str]] = []
    summary_fields = (
        ("movement patterns", breakdown["sharedMovementPatterns"], breakdown["componentScores"].get("sameMovementPattern", 0.0)),
        ("primary joint actions", breakdown["sharedPrimaryJointActions"], breakdown["componentScores"].get("sharedPrimaryJointAction", 0.0)),
        ("prime movers", breakdown["sharedPrimeMovers"], breakdown["componentScores"].get("sharedPrimeMover", 0.0)),
        ("supporting joint actions", breakdown["sharedSupportingJointActions"], breakdown["componentScores"].get("sharedSupportingJointAction", 0.0)),
        ("synergists", breakdown["sharedSynergists"], breakdown["componentScores"].get("sharedSynergist", 0.0)),
        ("stabilizers", breakdown["sharedStabilizers"], breakdown["componentScores"].get("sharedStabilizer", 0.0)),
        ("equipment", breakdown["sharedEquipment"], breakdown["componentScores"].get("sharedEquipment", 0.0)),
        ("styles", breakdown["sharedStyles"], breakdown["componentScores"].get("sharedExerciseStyle", 0.0)),
        ("planes", breakdown["sharedPlanesOfMotion"], breakdown["componentScores"].get("samePlaneOfMotion", 0.0)),
    )
    for label, values, contribution in summary_fields:
        candidate = _shared_summary(label, values, contribution)
        if candidate:
            reasons.append(candidate)

    laterality = breakdown.get("sameLaterality")
    if laterality:
        reasons.append((breakdown["componentScores"].get("sameLaterality", 0.0), f"Same laterality: {_humanize(laterality)}"))
    if breakdown.get("sameCompoundStatus") is not None:
        status = "compound" if breakdown["sameCompoundStatus"] else "isolation"
        reasons.append((breakdown["componentScores"].get("sameCompoundStatus", 0.0), f"Same movement profile: {status}"))

    reasons.sort(key=lambda item: (-item[0], item[1]))
    if not reasons:
        return "Closest available graph match."
    return "; ".join(text for _, text in reasons[:3])


def score_pair(
    left: NormalizedExerciseFeature,
    right: NormalizedExerciseFeature,
    weights: dict[str, float],
    *,
    include_breakdown: bool,
) -> dict:
    shared_patterns = sorted(left.movement_patterns & right.movement_patterns)
    shared_primary = sorted(left.primary_joint_actions & right.primary_joint_actions)
    shared_supporting = sorted(left.supporting_joint_actions & right.supporting_joint_actions)
    shared_prime = sorted(left.prime_movers & right.prime_movers)
    shared_synergists = sorted(left.synergists & right.synergists)
    shared_stabilizers = sorted(left.stabilizers & right.stabilizers)
    shared_equipment = sorted(left.equipment & right.equipment)
    shared_planes = sorted(left.plane_of_motion & right.plane_of_motion)
    shared_styles = sorted(left.style & right.style)

    component_scores = {
        "sameMovementPattern": len(shared_patterns) * weights.get("sameMovementPattern", 0.0),
        "sharedPrimaryJointAction": len(shared_primary) * weights.get("sharedPrimaryJointAction", 0.0),
        "sharedSupportingJointAction": len(shared_supporting) * weights.get("sharedSupportingJointAction", 0.0),
        "sharedPrimeMover": len(shared_prime) * weights.get("sharedPrimeMover", 0.0),
        "sharedSynergist": len(shared_synergists) * weights.get("sharedSynergist", 0.0),
        "sharedStabilizer": len(shared_stabilizers) * weights.get("sharedStabilizer", 0.0),
        "sharedEquipment": len(shared_equipment) * weights.get("sharedEquipment", 0.0),
        "samePlaneOfMotion": len(shared_planes) * weights.get("samePlaneOfMotion", 0.0),
        "sharedExerciseStyle": len(shared_styles) * weights.get("sharedExerciseStyle", 0.0),
        "sameLaterality": weights.get("sameLaterality", 0.0)
        if left.laterality and left.laterality == right.laterality
        else 0.0,
        "sameCompoundStatus": weights.get("sameCompoundStatus", 0.0)
        if left.is_compound == right.is_compound
        else 0.0,
        "combinationMismatchPenalty": weights.get("combinationMismatchPenalty", 0.0)
        if left.is_combination != right.is_combination
        else 0.0,
        "ballisticMismatchPenalty": weights.get("ballisticMismatchPenalty", 0.0)
        if left.is_ballistic != right.is_ballistic
        else 0.0,
        "primaryActionCountMismatchPenalty": abs(left.primary_joint_action_count - right.primary_joint_action_count)
        * weights.get("primaryActionCountMismatchPenalty", 0.0),
    }
    total_score = _round_score(sum(component_scores.values()))

    breakdown = {
        "componentScores": {key: _round_score(value) for key, value in component_scores.items() if value},
        "jointActionCountDifference": abs(left.primary_joint_action_count - right.primary_joint_action_count),
        "sameCompoundStatus": left.is_compound if left.is_compound == right.is_compound else None,
        "sameLaterality": left.laterality if left.laterality and left.laterality == right.laterality else None,
        "sharedEquipment": shared_equipment,
        "sharedMovementPatterns": shared_patterns,
        "sharedPlanesOfMotion": shared_planes,
        "sharedPrimaryJointActions": shared_primary,
        "sharedPrimeMovers": shared_prime,
        "sharedStabilizers": shared_stabilizers,
        "sharedStyles": shared_styles,
        "sharedSupportingJointActions": shared_supporting,
        "sharedSynergists": shared_synergists,
    }
    payload = {
        "reason": summarize_breakdown(breakdown),
        "score": total_score,
    }
    if include_breakdown:
        payload["breakdown"] = breakdown
    return payload


def _candidate_index(features: list[NormalizedExerciseFeature]) -> dict[str, dict[str, set[str]]]:
    index: dict[str, dict[str, set[str]]] = {field: defaultdict(set) for field in _INDEX_FIELDS}
    for feature in features:
        for field in _INDEX_FIELDS:
            for value in getattr(feature, field):
                index[field][value].add(feature.id)
    return index


def _candidate_ids(
    feature: NormalizedExerciseFeature,
    index: dict[str, dict[str, set[str]]],
) -> set[str]:
    candidate_ids: set[str] = set()
    for field in _INDEX_FIELDS:
        for value in getattr(feature, field):
            candidate_ids.update(index[field].get(value, set()))
    candidate_ids.discard(feature.id)
    return candidate_ids


def _neighbor_payload(pair_payload: dict, other_id: str, *, fallback: bool) -> dict:
    payload = {
        "id": other_id,
        "reason": pair_payload["reason"],
        "score": pair_payload["score"],
    }
    if fallback:
        payload["fallback"] = True
    if "breakdown" in pair_payload:
        payload["breakdown"] = pair_payload["breakdown"]
    return payload


def _sorted_neighbors(neighbors: list[dict]) -> list[dict]:
    return sorted(neighbors, key=lambda item: (-item["score"], item["id"]))


def build_similarity_outputs(
    features: list[NormalizedExerciseFeature],
    weights: dict[str, float],
    settings: dict[str, int | bool | float],
) -> tuple[list[dict], dict[str, list[dict]], dict]:
    include_breakdown = bool(settings.get("emitDebugBreakdowns", False))
    min_score = float(settings.get("minScore", 0))
    top_n = int(settings.get("topNeighborsPerExercise", 12))

    by_id = {feature.id: feature for feature in features}
    all_ids = sorted(by_id)
    index = _candidate_index(features)
    candidate_pair_count = 0
    neighbors: dict[str, list[dict]] = {}
    selected_edge_map: dict[tuple[str, str], dict] = {}
    fallback_neighbor_entries = 0
    threshold_neighborless = 0

    for feature in features:
        candidates = sorted(_candidate_ids(feature, index))
        candidate_pair_count += len(candidates)
        selected: list[dict] = []
        for other_id in candidates:
            payload = score_pair(feature, by_id[other_id], weights, include_breakdown=include_breakdown)
            if payload["score"] < min_score:
                continue
            selected.append(_neighbor_payload(payload, other_id, fallback=False))
        selected = _sorted_neighbors(selected)[:top_n]
        if not selected:
            threshold_neighborless += 1
            fallback_candidates: list[dict] = []
            for other_id in all_ids:
                if other_id == feature.id:
                    continue
                payload = score_pair(feature, by_id[other_id], weights, include_breakdown=include_breakdown)
                fallback_candidates.append(_neighbor_payload(payload, other_id, fallback=True))
            fallback_candidates = _sorted_neighbors(fallback_candidates)
            selected = fallback_candidates[:top_n]
            fallback_neighbor_entries += len(selected)
        neighbors[feature.id] = selected
        for neighbor in selected:
            left_id, right_id = sorted((feature.id, neighbor["id"]))
            existing = selected_edge_map.get((left_id, right_id))
            edge = {
                "reason": neighbor["reason"],
                "score": neighbor["score"],
                "source": left_id,
                "target": right_id,
            }
            if "breakdown" in neighbor:
                edge["breakdown"] = neighbor["breakdown"]
            if existing is None or edge["score"] > existing["score"]:
                selected_edge_map[(left_id, right_id)] = edge

    edges = [selected_edge_map[key] for key in sorted(selected_edge_map)]

    metrics = {
        "candidate_pair_count": candidate_pair_count,
        "edge_count": len(edges),
        "exercise_count": len(features),
        "fallback_neighbor_entries": fallback_neighbor_entries,
        "neighborless_after_threshold_count": threshold_neighborless,
        "scored_pair_count": candidate_pair_count,
        "top_neighbors_per_exercise": top_n,
    }
    return edges, neighbors, metrics
