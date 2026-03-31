from __future__ import annotations

import re
from collections import defaultdict
from itertools import islice

_EQUIPMENT_TOKENS = {
    "barbell",
    "bodyweight",
    "cable",
    "clubbell",
    "dumbbell",
    "dumbbells",
    "ez",
    "ezbar",
    "kettlebell",
    "kettlebells",
    "landmine",
    "machine",
    "macebell",
    "resistance",
    "sandbag",
    "smith",
    "suspension",
    "trainer",
    "trap",
}
_LATERALITY_TOKENS = {
    "alternating",
    "bilateral",
    "contralateral",
    "double",
    "ipsilateral",
    "left",
    "one",
    "right",
    "single",
    "unilateral",
}
_STANCE_MODIFIER_PATTERNS = {
    "sumo": re.compile(r"\bsumo\b"),
    "wide_stance": re.compile(r"\bwide stance\b"),
    "narrow_stance": re.compile(r"\bnarrow stance\b"),
    "staggered": re.compile(r"\bstaggered\b"),
    "split_stance": re.compile(r"\bsplit stance\b"),
}
_LOADING_MODIFIER_PATTERNS = {
    "reverse_band": re.compile(r"\breverse bands?\b"),
    "banded": re.compile(r"\bbanded\b"),
    "chains": re.compile(r"\bchains?\b"),
    "tempo": re.compile(r"\btempo\b"),
    "paused": re.compile(r"\bpaused?\b"),
    "deficit": re.compile(r"\bdeficit\b"),
}
_RESISTANCE_BAND_TOKENS = {"miniband", "superband", "resistance band", "band"}


def _humanize(value: str | None) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ")
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_tokens(name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(name or "").lower())


def _title_text(name: str) -> str:
    return " ".join(_title_tokens(name))


def _title_stem(name: str) -> str:
    tokens = [
        token
        for token in _title_tokens(name)
        if token not in _EQUIPMENT_TOKENS and token not in _LATERALITY_TOKENS
    ]
    return " ".join(tokens)


def _modifier_tags(feature: dict, patterns: dict[str, re.Pattern[str]]) -> tuple[str, ...]:
    title = _title_text(feature.get("name", ""))
    return tuple(sorted(tag for tag, pattern in patterns.items() if pattern.search(title)))


def _dedupe_key(feature: dict) -> tuple:
    return (
        tuple(feature["movementPatterns"]),
        tuple(feature["primaryJointActions"]),
        tuple(feature["primeMovers"]),
        feature.get("laterality"),
        feature.get("isCompound"),
        _title_stem(feature["name"]),
    )


def _equipment_signature(feature: dict) -> tuple[str, ...]:
    return tuple(feature.get("equipment") or ["Bodyweight"])


def _shared(source: dict, target: dict, key: str) -> list[str]:
    return sorted(set(source.get(key, [])) & set(target.get(key, [])))


def _pair_summary(source: dict, target: dict, neighbor_entry: dict | None) -> dict:
    breakdown = (neighbor_entry or {}).get("breakdown", {})
    shared_patterns = breakdown.get("sharedMovementPatterns") or _shared(source, target, "movementPatterns")
    shared_primary = breakdown.get("sharedPrimaryJointActions") or _shared(source, target, "primaryJointActions")
    shared_prime = breakdown.get("sharedPrimeMovers") or _shared(source, target, "primeMovers")
    shared_equipment = breakdown.get("sharedEquipment") or _shared(source, target, "equipment")
    same_laterality = breakdown.get("sameLaterality")
    if same_laterality is None and source.get("laterality") == target.get("laterality"):
        same_laterality = source.get("laterality")
    same_compound = breakdown.get("sameCompoundStatus")
    if same_compound is None and source.get("isCompound") == target.get("isCompound"):
        same_compound = source.get("isCompound")

    source_equipment = set(source.get("equipment") or ["Bodyweight"])
    target_equipment = set(target.get("equipment") or ["Bodyweight"])
    target_unique_equipment = sorted(target_equipment - source_equipment)
    source_movement_patterns = tuple(sorted(source.get("movementPatterns", [])))
    target_movement_patterns = tuple(sorted(target.get("movementPatterns", [])))
    source_primary_actions = tuple(sorted(source.get("primaryJointActions", [])))
    target_primary_actions = tuple(sorted(target.get("primaryJointActions", [])))
    source_stance_modifiers = _modifier_tags(source, _STANCE_MODIFIER_PATTERNS)
    target_stance_modifiers = _modifier_tags(target, _STANCE_MODIFIER_PATTERNS)
    source_loading_modifiers = _modifier_tags(source, _LOADING_MODIFIER_PATTERNS)
    target_loading_modifiers = _modifier_tags(target, _LOADING_MODIFIER_PATTERNS)

    return {
        "candidateId": target["id"],
        "candidateName": target["name"],
        "combinationMismatch": source.get("isCombination") != target.get("isCombination"),
        "dedupeKey": _dedupe_key(target),
        "equipmentShift": target_equipment != source_equipment,
        "fallback": bool((neighbor_entry or {}).get("fallback", False)),
        "lateralityMatch": source.get("laterality") == target.get("laterality"),
        "neighborRank": (neighbor_entry or {}).get("_rank"),
        "score": float((neighbor_entry or {}).get("score", 0.0)),
        "sameCompound": same_compound is not None,
        "sameLaterality": same_laterality,
        "sameMovementPatternSet": bool(source_movement_patterns) and source_movement_patterns == target_movement_patterns,
        "samePrimaryJointActionSet": bool(source_primary_actions) and source_primary_actions == target_primary_actions,
        "sharedEquipment": shared_equipment,
        "sharedMovementPatterns": shared_patterns,
        "sharedPrimaryJointActions": shared_primary,
        "sharedPrimeMovers": shared_prime,
        "sourceLoadingModifiers": source_loading_modifiers,
        "sourceNameStem": _title_stem(source["name"]),
        "sourceStanceModifiers": source_stance_modifiers,
        "targetLoadingModifiers": target_loading_modifiers,
        "targetNameStem": _title_stem(target["name"]),
        "targetStanceModifiers": target_stance_modifiers,
        "targetUniqueEquipment": target_unique_equipment,
        "usefulEquipmentShift": bool(target_unique_equipment),
    }


def _is_close_match(summary: dict) -> bool:
    # Closest Alternatives are a post-rank UX bucket for near 1:1 swaps, not a generic "high score" list.
    return bool(
        summary["sameMovementPatternSet"]
        and summary["samePrimaryJointActionSet"]
        and summary["sharedPrimeMovers"]
        and not summary["combinationMismatch"]
        and summary["sameCompound"]
        and summary["lateralityMatch"]
        and summary["sourceStanceModifiers"] == summary["targetStanceModifiers"]
        and not summary["sourceLoadingModifiers"]
        and not summary["targetLoadingModifiers"]
        and not summary["fallback"]
    )


def _reason_for_closest(summary: dict) -> str:
    pattern = _humanize(summary["sharedMovementPatterns"][0]) if summary["sharedMovementPatterns"] else "movement"
    if len(summary["sharedPrimeMovers"]) >= 2:
        return f"Same {pattern.lower()} pattern and very similar muscle demand."
    if summary["sharedPrimaryJointActions"]:
        return f"Same {pattern.lower()} pattern and very similar joint action profile."
    return f"Very similar version of the same {pattern.lower()} family."


def _reason_for_equipment(source: dict, summary: dict) -> str:
    pattern = _humanize(summary["sharedMovementPatterns"][0]) if summary["sharedMovementPatterns"] else "movement"
    source_equipment = _equipment_signature(source)
    target_equipment = summary["targetUniqueEquipment"]
    if source_equipment and target_equipment:
        return (
            f"Same {pattern.lower()} pattern with "
            f"{_humanize(target_equipment[0]).lower()} instead of {_humanize(source_equipment[0]).lower()}."
        )
    return f"Very similar {pattern.lower()} with a different implement."


def _family_group_label(source: dict, target: dict, summary: dict) -> str:
    # Keep family labels user-oriented instead of mirroring raw equipment taxonomy.
    target_equipment = {_humanize(item).lower() for item in target.get("equipment", [])}
    if source.get("laterality") != target.get("laterality") and target.get("laterality"):
        return "Unilateral / staggered variations"
    if target_equipment & _RESISTANCE_BAND_TOKENS:
        return "Resistance band options"
    if target.get("movementPatterns"):
        return f"Related {_humanize(target['movementPatterns'][0]).lower()} variations"
    return "More variations"


def _reason_for_family(source: dict, target: dict, summary: dict) -> str:
    if source.get("laterality") != target.get("laterality") and target.get("laterality"):
        return f"Related {_humanize(target['laterality']).lower()} variation in the same family."
    if summary["targetUniqueEquipment"]:
        return "Related variation with a different setup."
    return "Related variation in the same family."


def _rank_family_candidate(summary: dict, target: dict) -> tuple:
    return (
        1 if summary["neighborRank"] is not None else 0,
        len(summary["sharedMovementPatterns"]),
        len(summary["sharedPrimaryJointActions"]),
        len(summary["sharedPrimeMovers"]),
        1 if summary["sameLaterality"] else 0,
        1 if summary["sameCompound"] else 0,
        summary["score"],
        target["name"],
    )


def build_substitute_ui_artifacts(
    *,
    features: list[dict],
    neighbors: dict[str, list[dict]],
    communities: dict[str, dict],
    settings: dict,
) -> tuple[dict, dict]:
    features_by_id = {item["id"]: item for item in features}
    community_by_member: dict[str, tuple[str, list[str]]] = {}
    for community_id, payload in communities.items():
        members = payload.get("members", [])
        for member_id in members:
            community_by_member[member_id] = (community_id, members)

    ui_artifact: dict[str, dict] = {}
    debug_artifact: dict[str, dict] = {}

    closest_max = int(settings.get("closestAlternativesMax", 5))
    equipment_max = int(settings.get("equipmentAlternativesMax", 4))
    family_max = int(settings.get("familyHighlightsMax", 6))
    family_groups_max = int(settings.get("familyGroupsMax", 3))
    family_per_group_max = int(settings.get("familyPerGroupMax", 2))

    for source in features:
        source_id = source["id"]
        ranked_neighbors = []
        for rank, entry in enumerate(neighbors.get(source_id, []), start=1):
            target = features_by_id.get(entry["id"])
            if target is None:
                continue
            ranked_entry = {**entry, "_rank": rank}
            ranked_neighbors.append((target, _pair_summary(source, target, ranked_entry)))

        selected_ids: set[str] = set()
        closest: list[dict] = []
        equipment_alternatives: list[dict] = []
        closest_seen_keys: dict[tuple, str] = {}
        equipment_seen_keys: set[tuple] = set()
        debug = {
            "closestAlternatives": [],
            "equipmentAlternatives": [],
            "familyHighlights": [],
            "excluded": [],
        }

        for target, summary in ranked_neighbors:
            if len(closest) >= closest_max:
                break
            if not _is_close_match(summary):
                debug["excluded"].append({
                    "id": target["id"],
                    "bucket": "closestAlternatives",
                    "reason": "failed_strict_match",
                    "sourceNeighborRank": summary["neighborRank"],
                })
                continue
            if summary["usefulEquipmentShift"] and summary["sourceNameStem"] == summary["targetNameStem"]:
                debug["excluded"].append({
                    "id": target["id"],
                    "bucket": "closestAlternatives",
                    "reason": "reserved_for_equipment_bucket",
                    "sourceNeighborRank": summary["neighborRank"],
                })
                continue
            if summary["dedupeKey"] in closest_seen_keys:
                debug["excluded"].append({
                    "id": target["id"],
                    "bucket": "closestAlternatives",
                    "reason": "deduped_visible_duplicate",
                    "duplicateOf": closest_seen_keys[summary["dedupeKey"]],
                    "sourceNeighborRank": summary["neighborRank"],
                })
                continue

            item = {
                "id": target["id"],
                "reason": _reason_for_closest(summary),
            }
            closest.append(item)
            selected_ids.add(target["id"])
            closest_seen_keys[summary["dedupeKey"]] = target["id"]
            debug["closestAlternatives"].append({
                "id": target["id"],
                "bucketReason": "strict_match",
                "sourceNeighborRank": summary["neighborRank"],
                "sourceScore": summary["score"],
            })

        for target, summary in ranked_neighbors:
            if len(equipment_alternatives) >= equipment_max:
                break
            if target["id"] in selected_ids:
                continue
            if not _is_close_match(summary) or not summary["usefulEquipmentShift"]:
                continue
            dedupe_key = (summary["targetNameStem"], tuple(summary["targetUniqueEquipment"]))
            if dedupe_key in equipment_seen_keys:
                debug["excluded"].append({
                    "id": target["id"],
                    "bucket": "equipmentAlternatives",
                    "reason": "deduped_equipment_variant",
                    "sourceNeighborRank": summary["neighborRank"],
                })
                continue

            item = {
                "id": target["id"],
                "reason": _reason_for_equipment(source, summary),
            }
            equipment_alternatives.append(item)
            selected_ids.add(target["id"])
            equipment_seen_keys.add(dedupe_key)
            debug["equipmentAlternatives"].append({
                "id": target["id"],
                "bucketReason": "same_pattern_different_equipment",
                "sourceNeighborRank": summary["neighborRank"],
                "sourceScore": summary["score"],
            })

        community_members = set(community_by_member.get(source_id, (None, []))[1])
        family_pool_ids: list[str] = []
        family_pool_ids.extend(
            target["id"]
            for target, _summary in ranked_neighbors
            if target["id"] not in selected_ids
        )
        for selected_id in selected_ids:
            family_pool_ids.extend(
                item["id"]
                for item in neighbors.get(selected_id, [])
                if item["id"] != source_id and item["id"] not in selected_ids
            )
        family_pool_ids.extend(member_id for member_id in community_members if member_id not in selected_ids and member_id != source_id)

        deduped_family_ids = []
        seen_family_ids = set()
        for candidate_id in family_pool_ids:
            if candidate_id in seen_family_ids:
                continue
            seen_family_ids.add(candidate_id)
            deduped_family_ids.append(candidate_id)

        family_candidates = []
        neighbor_lookup = {target["id"]: summary for target, summary in ranked_neighbors}
        for candidate_id in deduped_family_ids:
            target = features_by_id.get(candidate_id)
            if target is None:
                continue
            summary = neighbor_lookup.get(candidate_id)
            if summary is None:
                summary = _pair_summary(source, target, None)
            if not (
                summary["sharedMovementPatterns"]
                or summary["sharedPrimaryJointActions"]
                or summary["sharedPrimeMovers"]
            ):
                debug["excluded"].append({
                    "id": candidate_id,
                    "bucket": "familyHighlights",
                    "reason": "too_loose_for_family_bucket",
                })
                continue
            family_candidates.append((target, summary))

        family_candidates.sort(key=lambda item: _rank_family_candidate(item[1], item[0]), reverse=True)
        family_groups: dict[str, list[dict]] = defaultdict(list)
        used_family_keys: set[tuple] = set()
        total_family_items = 0

        for target, summary in family_candidates:
            if total_family_items >= family_max:
                break
            group_label = _family_group_label(source, target, summary)
            if len(family_groups[group_label]) >= family_per_group_max:
                continue
            if len(family_groups) >= family_groups_max and group_label not in family_groups:
                continue
            if summary["dedupeKey"] in used_family_keys:
                continue

            family_groups[group_label].append({
                "id": target["id"],
                "reason": _reason_for_family(source, target, summary),
            })
            used_family_keys.add(summary["dedupeKey"])
            total_family_items += 1
            debug["familyHighlights"].append({
                "id": target["id"],
                "bucketReason": group_label,
                "sourceNeighborRank": summary["neighborRank"],
                "sourceScore": summary["score"],
            })

        ui_artifact[source_id] = {
            "closestAlternatives": closest,
            "equipmentAlternatives": equipment_alternatives,
            "familyHighlights": [
                {"label": label, "items": items}
                for label, items in islice(family_groups.items(), family_groups_max)
                if items
            ],
        }
        debug_artifact[source_id] = debug

    return ui_artifact, debug_artifact
