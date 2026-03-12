import marimo as mo
from pathlib import Path
import json

app = mo.App(width="medium")


@app.cell
def _imports():
    import marimo as mo
    import json
    from pathlib import Path

    return mo, json, Path


@app.cell
def _data_setup(mo, Path, json):
    _here = Path(__file__).parent
    _root = _here.parent if _here.name == "evals" else _here
    gold_path = _root / "evals" / "gold.json"

    # Load Data
    if gold_path.exists():
        try:
            raw_data = json.loads(gold_path.read_text())
        except:
            raw_data = [{"id": "error_loading_json", "muscle_involvements": []}]
    else:
        raw_data = [{"id": "file_not_found", "muscle_involvements": []}]

    # Static Options
    MUSCLES = sorted(
        [
            "Biceps",
            "Triceps",
            "Quads",
            "Glutes",
            "Lats",
            "Hamstrings",
            "Pectorals",
            "Shoulders",
            "Abs",
            "Calves",
            "Forearms",
            "Traps",
        ]
    )
    PATTERNS = sorted(["Push", "Pull", "Squat", "Hinge", "Lunge", "Carry", "Isolation"])
    MODALITIES = ["Strength", "Hypertrophy", "Cardio", "Mobility", "Plyometrics"]
    DEGREES = ["PrimeMover", "Synergist", "Stabilizer"]

    # Global state objects
    get_idx, set_idx = mo.state(0)
    get_inv, set_inv = mo.state(raw_data[0].get("muscle_involvements", []))

    return (
        DEGREES,
        MODALITIES,
        PATTERNS,
        MUSCLES,
        get_idx,
        get_inv,
        gold_path,
        raw_data,
        set_idx,
        set_inv,
    )


@app.cell
def _logic(get_idx, set_idx, set_inv, raw_data, MUSCLES):
    def go(delta):
        _current = get_idx()
        _new_idx = max(0, min(len(raw_data) - 1, _current + delta))
        set_idx(_new_idx)
        # Reset the table state for the new record
        set_inv(raw_data[_new_idx].get("muscle_involvements", []))

    def add_row(_):
        _current_invs = get_inv()
        set_inv(_current_invs + [{"muscle": MUSCLES[0], "degree": "PrimeMover"}])

    def remove_row(target_index):
        _current_invs = get_inv()
        set_inv([row for i, row in enumerate(_current_invs) if i != target_index])

    return add_row, go, remove_row


@app.cell
def _involvement_table(get_inv, MUSCLES, DEGREES, mo, remove_row):
    # mo.ui.array creates a dynamic group of UI elements.
    # Each row is a dictionary containing the specific inputs.
    involvement_rows = mo.ui.array(
        [
            mo.ui.dictionary(
                {
                    "muscle": mo.ui.dropdown(
                        MUSCLES, value=r.get("muscle", MUSCLES[0])
                    ),
                    "degree": mo.ui.dropdown(
                        DEGREES, value=r.get("degree", DEGREES[0])
                    ),
                    "remove_btn": mo.ui.button(
                        label="✕", on_click=lambda _v, i=idx: remove_row(i)
                    ),
                }
            )
            for idx, r in enumerate(get_inv())
        ]
    )
    return (involvement_rows,)


@app.cell
def _form_elements(MODALITIES, PATTERNS, get_idx, mo, raw_data):
    _idx = get_idx()
    _ex = raw_data[_idx]

    # Filter values to ensure they exist in options to prevent KeyErrors
    _init_p = [p for p in _ex.get("movement_patterns", []) if p in PATTERNS]
    _init_m = [m for m in _ex.get("training_modalities", []) if m in MODALITIES]

    patterns_sel = mo.ui.multiselect(PATTERNS, value=_init_p, label="Patterns")
    modalities_sel = mo.ui.multiselect(MODALITIES, value=_init_m, label="Modalities")
    unilateral_sw = mo.ui.switch(
        value=_ex.get("is_unilateral", False), label="Unilateral"
    )

    return modalities_sel, patterns_sel, unilateral_sw


@app.cell
def _save_logic(
    mo,
    gold_path,
    json,
    raw_data,
    get_idx,
    involvement_rows,
    patterns_sel,
    modalities_sel,
    unilateral_sw,
):
    def save_to_disk(_):
        _idx = get_idx()

        # involvement_rows.value is a list of dicts: [{'muscle': '...', 'degree': '...'}, ...]
        _cleaned_invs = [
            {"muscle": r["muscle"], "degree": r["degree"]}
            for r in involvement_rows.value
        ]

        raw_data[_idx].update(
            {
                "movement_patterns": patterns_sel.value,
                "training_modalities": modalities_sel.value,
                "is_unilateral": unilateral_sw.value,
                "muscle_involvements": _cleaned_invs,
            }
        )

        gold_path.write_text(json.dumps(raw_data, indent=2))
        mo.status.toast("Changes saved to gold.json", kind="success")

    save_btn = mo.ui.button(
        label="💾 Save Changes", on_click=save_to_disk, kind="success"
    )
    return (save_btn,)


@app.cell
def _app_layout(
    get_idx,
    mo,
    raw_data,
    go,
    add_row,
    involvement_rows,
    patterns_sel,
    modalities_sel,
    unilateral_sw,
    save_btn,
):
    _idx = get_idx()
    _ex = raw_data[_idx]

    _prev_btn = mo.ui.button(
        label="← Prev", on_click=lambda _: go(-1), disabled=(_idx == 0)
    )
    _next_btn = mo.ui.button(
        label="Next →", on_click=lambda _: go(1), disabled=(_idx == len(raw_data) - 1)
    )
    _add_btn = mo.ui.button(label="+ Add Muscle Row", on_click=add_row)

    # To layout the mo.ui.array nicely, we iterate over its .elements
    _table_view = (
        mo.vstack(
            [
                mo.hstack(
                    [row["muscle"], row["degree"], row["remove_btn"]],
                    justify="start",
                    gap=1,
                )
                for row in involvement_rows.elements
            ]
        )
        if involvement_rows.elements
        else mo.md("_No involvements added for this exercise._")
    )

    # The final visual output
    return mo.vstack(
        [
            mo.hstack([_prev_btn, _next_btn, save_btn], justify="start", gap=2),
            mo.md(f"# {_ex['id'].replace('_', ' ')}"),
            mo.md("---"),
            mo.hstack(
                [patterns_sel, modalities_sel, unilateral_sw], align="end", gap=2
            ),
            mo.md("### Muscle Involvements"),
            _table_view,
            _add_btn,
            mo.md("---"),
            mo.md(f"**Progress:** `{_idx + 1} / {len(raw_data)}`"),
        ]
    )


if __name__ == "__main__":
    app.run()
