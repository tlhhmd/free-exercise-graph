from __future__ import annotations

import json

from app.build_site import _build_similarity_id_map, _remap_substitute_ui_artifact


def test_substitute_ui_is_remapped_into_app_id_namespace(tmp_path):
    exercises = [
        {"id": "Romanian_Deadlift", "name": "Romanian Deadlift"},
        {"id": "Push_Up", "name": "Push-Up"},
        {"id": "Ab_Wheel_Kneeling_Rollout", "name": "Ab Wheel Kneeling Rollout"},
    ]
    similarity_dir = tmp_path
    (similarity_dir / "exercise_features.json").write_text(
        json.dumps(
            [
                {"id": "romanian_deadlift", "name": "Romanian Deadlift"},
                {"id": "push_up", "name": "Push-Up"},
                {"id": "ab_wheel_kneeling_rollout", "name": "Ab Wheel Kneeling Rollout"},
                {"id": "graph_only_exercise", "name": "Graph Only Exercise"},
            ]
        ),
        encoding="utf-8",
    )

    id_map = _build_similarity_id_map(exercises, similarity_dir)

    remapped = _remap_substitute_ui_artifact(
        {
            "romanian_deadlift": {
                "closestAlternatives": [
                    {"id": "push_up", "reason": "not biomechanically sensible, just a test"},
                    {"id": "graph_only_exercise", "reason": "should be dropped"},
                ],
                "equipmentAlternatives": [
                    {"id": "ab_wheel_kneeling_rollout", "reason": "test mapping"},
                ],
                "familyHighlights": [
                    {
                        "label": "More variations",
                        "items": [
                            {"id": "push_up", "reason": "duplicate should dedupe"},
                            {"id": "push_up", "reason": "duplicate should dedupe"},
                        ],
                    }
                ],
            }
        },
        id_map,
    )

    assert remapped == {
        "Romanian_Deadlift": {
            "closestAlternatives": [
                {"id": "Push_Up", "reason": "not biomechanically sensible, just a test"},
            ],
            "equipmentAlternatives": [
                {"id": "Ab_Wheel_Kneeling_Rollout", "reason": "test mapping"},
            ],
            "familyHighlights": [
                {
                    "label": "More variations",
                    "items": [
                        {"id": "Push_Up", "reason": "duplicate should dedupe"},
                    ],
                }
            ],
        }
    }
