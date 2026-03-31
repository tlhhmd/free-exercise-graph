from __future__ import annotations

from scripts.lib.substitute_ui import build_substitute_ui_artifacts


def _feature(
    exercise_id: str,
    name: str,
    *,
    movement_patterns: list[str],
    primary_joint_actions: list[str],
    prime_movers: list[str],
    equipment: list[str],
    laterality: str = "Bilateral",
    is_compound: bool = True,
    supporting_joint_actions: list[str] | None = None,
) -> dict:
    return {
        "equipment": equipment,
        "id": exercise_id,
        "isCombination": False,
        "isCompound": is_compound,
        "laterality": laterality,
        "movementPatterns": movement_patterns,
        "name": name,
        "planeOfMotion": ["SagittalPlane"],
        "primeMovers": prime_movers,
        "primaryJointActions": primary_joint_actions,
        "stabilizers": ["Core"],
        "style": ["Strength"],
        "supportingJointActions": supporting_joint_actions or [],
        "synergists": [],
    }


def _neighbor(
    exercise_id: str,
    *,
    score: float,
    shared_patterns: list[str],
    shared_primary: list[str],
    shared_prime: list[str],
    shared_equipment: list[str] | None = None,
    fallback: bool = False,
) -> dict:
    return {
        "breakdown": {
            "componentScores": {"sameMovementPattern": 5, "sharedPrimaryJointAction": 4, "sharedPrimeMover": 4},
            "jointActionCountDifference": 0,
            "sameCompoundStatus": True,
            "sameLaterality": "Bilateral",
            "sharedEquipment": shared_equipment or [],
            "sharedMovementPatterns": shared_patterns,
            "sharedPlanesOfMotion": ["SagittalPlane"],
            "sharedPrimaryJointActions": shared_primary,
            "sharedPrimeMovers": shared_prime,
            "sharedStabilizers": ["Core"],
            "sharedStyles": ["Strength"],
            "sharedSupportingJointActions": [],
            "sharedSynergists": [],
        },
        "fallback": fallback,
        "id": exercise_id,
        "score": score,
    }


def test_substitute_ui_separates_equipment_alternatives_from_closest():
    features = [
        _feature(
            "barbell_rdl",
            "Barbell Romanian Deadlift",
            movement_patterns=["HipHinge"],
            primary_joint_actions=["HipExtension"],
            prime_movers=["GluteusMaximus", "BicepsFemoris"],
            equipment=["Barbell"],
        ),
        _feature(
            "dumbbell_rdl",
            "Dumbbell Romanian Deadlift",
            movement_patterns=["HipHinge"],
            primary_joint_actions=["HipExtension"],
            prime_movers=["GluteusMaximus", "BicepsFemoris"],
            equipment=["Dumbbell"],
        ),
        _feature(
            "kettlebell_rdl",
            "Kettlebell Romanian Deadlift",
            movement_patterns=["HipHinge"],
            primary_joint_actions=["HipExtension"],
            prime_movers=["GluteusMaximus", "BicepsFemoris"],
            equipment=["Kettlebell"],
        ),
        _feature(
            "good_morning",
            "Barbell Good Morning",
            movement_patterns=["HipHinge"],
            primary_joint_actions=["HipExtension"],
            prime_movers=["GluteusMaximus", "BicepsFemoris"],
            equipment=["Barbell"],
        ),
    ]
    neighbors = {
        "barbell_rdl": [
            _neighbor("dumbbell_rdl", score=18, shared_patterns=["HipHinge"], shared_primary=["HipExtension"], shared_prime=["GluteusMaximus", "BicepsFemoris"]),
            _neighbor("kettlebell_rdl", score=17, shared_patterns=["HipHinge"], shared_primary=["HipExtension"], shared_prime=["GluteusMaximus", "BicepsFemoris"]),
            _neighbor("good_morning", score=16, shared_patterns=["HipHinge"], shared_primary=["HipExtension"], shared_prime=["GluteusMaximus", "BicepsFemoris"], shared_equipment=["Barbell"]),
        ]
    }
    communities = {"0": {"members": [feature["id"] for feature in features], "size": len(features)}}

    ui, debug = build_substitute_ui_artifacts(
        features=features,
        neighbors=neighbors,
        communities=communities,
        settings={
            "closestAlternativesMax": 5,
            "equipmentAlternativesMax": 4,
            "familyHighlightsMax": 4,
            "familyGroupsMax": 2,
            "familyPerGroupMax": 2,
        },
    )

    barbell_rdl = ui["barbell_rdl"]
    assert [item["id"] for item in barbell_rdl["closestAlternatives"]] == ["good_morning"]
    assert [item["id"] for item in barbell_rdl["equipmentAlternatives"]] == ["dumbbell_rdl", "kettlebell_rdl"]
    assert any(item["reason"].startswith("Same hip hinge pattern") for item in barbell_rdl["closestAlternatives"])
    assert any(excluded["reason"] == "reserved_for_equipment_bucket" for excluded in debug["barbell_rdl"]["excluded"])


def test_substitute_ui_dedupes_visible_close_variants():
    features = [
        _feature("source", "Barbell Row", movement_patterns=["HorizontalPull"], primary_joint_actions=["ShoulderExtension"], prime_movers=["LatissimusDorsi"], equipment=["Barbell"]),
        _feature("cand_a", "Barbell Bent Over Row", movement_patterns=["HorizontalPull"], primary_joint_actions=["ShoulderExtension"], prime_movers=["LatissimusDorsi"], equipment=["Barbell"]),
        _feature("cand_b", "Dumbbell Bent Over Row", movement_patterns=["HorizontalPull"], primary_joint_actions=["ShoulderExtension"], prime_movers=["LatissimusDorsi"], equipment=["Dumbbell"]),
        _feature("cand_c", "Chest Supported Row", movement_patterns=["HorizontalPull"], primary_joint_actions=["ShoulderExtension"], prime_movers=["LatissimusDorsi"], equipment=["Machine"]),
    ]
    neighbors = {
        "source": [
            _neighbor("cand_a", score=20, shared_patterns=["HorizontalPull"], shared_primary=["ShoulderExtension"], shared_prime=["LatissimusDorsi"], shared_equipment=["Barbell"]),
            _neighbor("cand_b", score=19, shared_patterns=["HorizontalPull"], shared_primary=["ShoulderExtension"], shared_prime=["LatissimusDorsi"]),
            _neighbor("cand_c", score=18, shared_patterns=["HorizontalPull"], shared_primary=["ShoulderExtension"], shared_prime=["LatissimusDorsi"]),
        ]
    }
    communities = {"0": {"members": [feature["id"] for feature in features], "size": len(features)}}

    ui, _debug = build_substitute_ui_artifacts(
        features=features,
        neighbors=neighbors,
        communities=communities,
        settings={
            "closestAlternativesMax": 5,
            "equipmentAlternativesMax": 4,
            "familyHighlightsMax": 4,
            "familyGroupsMax": 2,
            "familyPerGroupMax": 2,
        },
    )

    visible_closest = [item["id"] for item in ui["source"]["closestAlternatives"]]
    assert visible_closest == ["cand_a", "cand_c"]


def test_substitute_ui_builds_grouped_family_highlights():
    features = [
        _feature("source", "Barbell Deadlift", movement_patterns=["HipHinge"], primary_joint_actions=["HipExtension"], prime_movers=["GluteusMaximus"], equipment=["Barbell"]),
        _feature("close", "Rack Pull", movement_patterns=["HipHinge"], primary_joint_actions=["HipExtension"], prime_movers=["GluteusMaximus"], equipment=["Barbell"]),
        _feature("unilateral", "Single Leg Deadlift", movement_patterns=["HipHinge"], primary_joint_actions=["HipExtension"], prime_movers=["GluteusMaximus"], equipment=["Dumbbell"], laterality="Unilateral"),
        _feature("dumbbell", "Dumbbell Deadlift", movement_patterns=["HipHinge"], primary_joint_actions=["HipExtension"], prime_movers=["GluteusMaximus"], equipment=["Dumbbell"]),
        _feature("other", "Good Morning", movement_patterns=["HipHinge"], primary_joint_actions=["HipExtension"], prime_movers=["GluteusMaximus"], equipment=["Barbell"]),
    ]
    neighbors = {
        "source": [
            _neighbor("close", score=20, shared_patterns=["HipHinge"], shared_primary=["HipExtension"], shared_prime=["GluteusMaximus"], shared_equipment=["Barbell"]),
            _neighbor("other", score=18, shared_patterns=["HipHinge"], shared_primary=["HipExtension"], shared_prime=["GluteusMaximus"], shared_equipment=["Barbell"]),
        ],
        "close": [
            _neighbor("unilateral", score=15, shared_patterns=["HipHinge"], shared_primary=["HipExtension"], shared_prime=["GluteusMaximus"]),
            _neighbor("dumbbell", score=14, shared_patterns=["HipHinge"], shared_primary=["HipExtension"], shared_prime=["GluteusMaximus"]),
        ],
    }
    communities = {"0": {"members": [feature["id"] for feature in features], "size": len(features)}}

    ui, _debug = build_substitute_ui_artifacts(
        features=features,
        neighbors=neighbors,
        communities=communities,
        settings={
            "closestAlternativesMax": 1,
            "equipmentAlternativesMax": 0,
            "familyHighlightsMax": 4,
            "familyGroupsMax": 3,
            "familyPerGroupMax": 2,
        },
    )

    groups = ui["source"]["familyHighlights"]
    labels = [group["label"] for group in groups]
    assert "More dumbbell options" in labels
    assert "Unilateral options" in labels
