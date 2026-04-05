# Eval Instructions

This file is for the reviewer completing the eval.

You will review one CSV per exercise.

Folders:
- [unreviewed](/Users/talha/Code/free-exercise-graph/evals/unreviewed)
- [submitted](/Users/talha/Code/free-exercise-graph/evals/submitted)
- [scored](/Users/talha/Code/free-exercise-graph/evals/scored)

Workflow:
- take one CSV from `evals/unreviewed/`
- review it in place
- when it is ready to count, move or copy it into `evals/submitted/`
- after it has been scored, move it into `evals/scored/` or use the archive flag

Do not rename the `field` values.

---

## File Format

Each review file has these columns:

- `field`
- `predicted_value`
- `corrected_value`
- `status (pending/accepted/modified/flagged)`
- `comments`

Statuses:

- `pending`
- `accepted`
- `modified`
- `flagged`

Default status is `pending`.

Only reviewed rows count. `pending` rows are ignored by the scorer.

---

## What The Rows Mean

Context rows:
- `entity_id`
- `exercise_name`

Scored field rows:
- `movement_patterns`
- `primary_joint_actions`
- `supporting_joint_actions`
- `training_modalities`
- `plane_of_motion`
- `exercise_style`
- `laterality`
- `is_compound`
- `is_combination`

Repeated paired rows:
- `muscle_involvement_01_muscle`
- `muscle_involvement_01_involvementdegree`
- `muscle_involvement_02_muscle`
- `muscle_involvement_02_involvementdegree`
- and so on

There is no overall exercise status.

If at least one scored row in a file has been reviewed, that exercise can contribute to scoring.

---

## How To Review Normal Field Rows

For non-muscle rows:

- use `accepted` when the prediction is correct
- use `modified` when the prediction is wrong and you entered a corrected value
- use `flagged` when you want to leave a note but not count that row yet
- leave `pending` when you have not reviewed it

Rules:

- if `status` is `accepted`, the scorer uses `predicted_value`
- if `status` is `modified`, the scorer uses `corrected_value`
- if `status` is `flagged`, the scorer skips that row
- if `status` is `pending`, the scorer skips that row

Format:

- list fields use comma-separated local names
- booleans use `TRUE` or `FALSE`
- laterality uses `Bilateral`, `Unilateral`, `Contralateral`, or `Ipsilateral`

`comments` is for reviewer notes only.

---

## How To Review Muscle Rows

Each involvement is split across two rows:

- `muscle_involvement_XX_muscle`
- `muscle_involvement_XX_involvementdegree`

Rules:

- if a muscle row is correct, mark that row `accepted`
- if a degree row is correct, mark that row `accepted`
- if either one is wrong, mark that row `modified` and fill `corrected_value`
- if you want to remove an involvement, mark one or both rows `modified` and leave the corrected value blank
- if you want to add an involvement, use one of the blank numbered pairs and fill both corrected values with `modified`
- `flagged` and `pending` rows are skipped

How to handle common cases:

- correct predicted involvement: mark both rows `accepted`
- wrong degree only: keep the muscle row `accepted`; mark the degree row `modified` and fix it
- wrong muscle only: keep the degree row `accepted`; mark the muscle row `modified` and fix it
- wrong muscle and degree: mark both rows `modified` and fix both
- predicted involvement should not exist: mark the involved rows `modified` and leave corrected values blank
- missing involvement: use one blank numbered pair and fill both corrected values with `modified`

Important:

- a muscle involvement only counts when both the muscle row and the degree row are reviewed
- if one side is still `pending` or `flagged`, that involvement is skipped
- do not type combined values like `MuscleName | Degree` into one cell

---

## Minimal Review Rule

The simplest safe rule is:

- if it is right, set `accepted`
- if it is wrong, set `modified` and fix it
- if you are unsure, leave it `pending`

That rule is enough to use the scorer correctly.

---

## Running The Scorer

When one or more reviewed CSVs are in `evals/submitted/`:

```bash
python3 evals/eval.py
```

Useful variants:

```bash
python3 evals/eval.py --gold evals/submitted --verbose
python3 evals/eval.py --gold evals/submitted --field movement_patterns
python3 evals/eval.py --gold evals/submitted --field muscle
python3 evals/eval.py --gold evals/submitted/some_exercise.csv
python3 evals/eval.py --archive-scored
```

What gets scored:

- every reviewed `.csv` file in `evals/submitted/`
- only rows with `accepted` or `modified`
- `flagged` and `pending` rows are ignored

If you use `--archive-scored`, successfully processed files are moved from `evals/submitted/` to `evals/scored/`.

---

## Common Mistakes To Avoid

- editing `field` names
- using labels or prose instead of ontology local names
- marking a row `accepted` and also filling `corrected_value`
- marking a row `modified` but forgetting to fill `corrected_value`
- using `flagged` and expecting the row to be scored
- forgetting that a muscle involvement needs both the muscle and degree rows reviewed
- typing combined muscle and degree values into one corrected cell
