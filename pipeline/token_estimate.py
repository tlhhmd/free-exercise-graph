"""
token_estimate.py

Estimates token counts for the enrichment prompt across all exercises.
Run from the repo root.

Usage:
    python pipeline/token_estimate.py
"""

import json
import statistics
from pathlib import Path

# pip install tiktoken
import tiktoken

EXERCISES_PATH = Path("dist/exercises.json")

# approximate system prompt length - update when you write the real one
SYSTEM_PROMPT = """
You are an exercise scientist classifying exercises for a knowledge graph.
For each exercise, return a JSON object with the following fields:

movement_patterns: list of one or more movement patterns from this list:
  KneeDominant, Squat, SplitSquat, Lunge, HipHinge, Push, HorizontalPush,
  VerticalPush, Pull, HorizontalPull, VerticalPull, Carry, Rotation,
  Core, Locomotion

training_modalities: list of zero or more from:
  Strength, Hypertrophy, Cardio, Mobility, Plyometrics

muscle_involvements: list of objects with:
  muscle: muscle name string
  degree: one of PrimeMover, Synergist, Stabilizer

is_unilateral: true if performed one limb at a time, omit if bilateral

Return only valid JSON. No explanation or preamble.
"""


def format_exercise(exercise):
    """Format one exercise as it would appear in the user prompt."""
    lines = [f"Name: {exercise.get('name', '')}"]

    instructions = exercise.get("instructions", [])
    if instructions:
        lines.append(f"Instructions: {' '.join(instructions)}")

    primary = exercise.get("primaryMuscles", [])
    if primary:
        lines.append(f"Primary muscles: {', '.join(primary)}")

    secondary = exercise.get("secondaryMuscles", [])
    if secondary:
        lines.append(f"Secondary muscles: {', '.join(secondary)}")

    return "\n".join(lines)


def main():
    enc = tiktoken.encoding_for_model("gpt-4o")  # close enough for estimates

    with open(EXERCISES_PATH, encoding="utf-8") as f:
        exercises = json.load(f)

    system_tokens = len(enc.encode(SYSTEM_PROMPT))
    print(f"System prompt tokens: {system_tokens}")
    print(f"Total exercises: {len(exercises)}\n")

    input_counts = []
    for exercise in exercises:
        user_prompt = format_exercise(exercise)
        user_tokens = len(enc.encode(user_prompt))
        total_input = system_tokens + user_tokens
        input_counts.append(total_input)

    # output estimate - rough, based on expected JSON structure
    # muscle involvements dominate: avg 5 muscles * ~15 tokens each = 75
    # plus movement pattern, modality, structure overhead = ~125
    estimated_output = 200

    print("=== Input token distribution ===")
    print(f"  Min:    {min(input_counts)}")
    print(f"  Max:    {max(input_counts)}")
    print(f"  Mean:   {statistics.mean(input_counts):.0f}")
    print(f"  Median: {statistics.median(input_counts):.0f}")
    print(f"  P95:    {sorted(input_counts)[int(len(input_counts)*0.95)]}")

    total_input = sum(input_counts)
    total_output = estimated_output * len(exercises)

    print("\n=== Total token estimates ===")
    print(f"  Input tokens:  {total_input:,}")
    print(f"  Output tokens: {total_output:,} (estimated)")

    print("\n=== Cost estimates (Haiku 4.5) ===")
    haiku_input_cost = total_input / 1_000_000 * 1.00
    haiku_output_cost = total_output / 1_000_000 * 5.00
    haiku_standard = haiku_input_cost + haiku_output_cost
    print(f"  Standard:  ${haiku_standard:.2f}")
    print(f"  Batch API: ${haiku_standard * 0.5:.2f}")

    print("\n=== Cost estimates (Sonnet 4.5) ===")
    sonnet_input_cost = total_input / 1_000_000 * 3.00
    sonnet_output_cost = total_output / 1_000_000 * 15.00
    sonnet_standard = sonnet_input_cost + sonnet_output_cost
    print(f"  Standard:  ${sonnet_standard:.2f}")
    print(f"  Batch API: ${sonnet_standard * 0.5:.2f}")


if __name__ == "__main__":
    main()
