import streamlit as st
import streamlit.components.v1 as components
import json
from pathlib import Path
from rdflib import Graph, Namespace, SKOS

# --- 1. CONFIG & PATHS ---
st.set_page_config(page_title="FEG Gold Verifier", layout="wide")

_HERE = Path(__file__).parent
_ROOT = _HERE.parent if _HERE.name == "evals" else _HERE
SEED_PATH = _ROOT / "evals" / "seed.json"
GOLD_PATH = _ROOT / "evals" / "gold.json"
ONTOLOGY_DIR = _ROOT / "ontology"


# --- 2. ONTOLOGY ENGINE (Source of Truth) ---
@st.cache_data
def get_ontology_data():
    g = Graph()
    for ttl in ONTOLOGY_DIR.glob("*.ttl"):
        g.parse(ttl, format="turtle")

    FEG = Namespace("https://placeholder.url#")

    def _local(uri):
        return str(uri).split("#")[-1] if "#" in str(uri) else str(uri).split("/")[-1]

    # Map hierarchy: {Child: [Parents]}
    hierarchy = {}
    muscles = sorted([_local(s) for s in g.subjects(SKOS.inScheme, FEG.MuscleScheme)])
    for m in muscles:
        hierarchy[m] = [_local(o) for o in g.objects(FEG[m], SKOS.broader)]

    patterns = sorted(
        [_local(s) for s in g.subjects(SKOS.inScheme, FEG.MovementPatternScheme)]
    )
    modalities = sorted(
        [_local(s) for s in g.subjects(SKOS.inScheme, FEG.TrainingModalityScheme)]
    )
    degrees = sorted(
        [_local(s) for s in g.subjects(SKOS.inScheme, FEG.InvolvementDegreeScheme)]
    )

    return muscles, patterns, modalities, degrees, hierarchy


MUSCLES, PATTERNS, MODALITIES, DEGREES, HIERARCHY = get_ontology_data()


# --- 3. VALIDATION LOGIC ---
def check_double_counting(selected_muscles):
    flags = []
    for m in selected_muscles:
        parents = HIERARCHY.get(m, [])
        for p in parents:
            if p in selected_muscles:
                flags.append(
                    f"⚠️ **Double Counting:** `{m}` is a sub-part of `{p}`. Pick one."
                )
    return flags


def get_breadcrumb(muscle):
    path = [muscle]
    curr = muscle
    while HIERARCHY.get(curr):
        parent = HIERARCHY[curr][0]  # Follow first parent path
        path.insert(0, parent)
        curr = parent
    return " > ".join(path)


# --- 4. HIERARCHY EXPLORER (D3.js MODAL) ---
@st.dialog("Muscle Hierarchy Explorer", width="large")
def muscle_explorer():
    if "explorer_focus" not in st.session_state:
        st.session_state.explorer_focus = MUSCLES[0]

    focus = st.session_state.explorer_focus
    parents = HIERARCHY.get(focus, [])
    children = [m for m, p_list in HIERARCHY.items() if focus in p_list]

    st.markdown(f"**Path:** `{get_breadcrumb(focus)}`")

    # D3 Layout Data
    tree_nodes = [{"id": focus, "type": "focus", "x": 400, "y": 200}]
    for i, p in enumerate(parents):
        tree_nodes.append(
            {
                "id": p,
                "type": "parent",
                "x": 400 + (i - len(parents) / 2) * 200,
                "y": 50,
            }
        )
    for i, c in enumerate(children):
        tree_nodes.append(
            {
                "id": c,
                "type": "child",
                "x": 400 + (i - len(children) / 2) * 150,
                "y": 350,
            }
        )

    html_code = f"""
    <div id="viz" style="background:#111; border-radius:10px;"></div>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script>
        const svg = d3.select("#viz").append("svg").attr("width", 800).attr("height", 400);
        const data = {json.dumps(tree_nodes)};
        
        // Draw Links
        svg.selectAll("line").data(data.filter(d => d.type !== 'focus')).enter().append("line")
            .attr("x1", 400).attr("y1", 200).attr("x2", d => d.x).attr("y2", d => d.y)
            .attr("stroke", "#444").attr("stroke-width", 2);

        // Draw Nodes
        const nodes = svg.selectAll("g").data(data).enter().append("g")
            .attr("transform", d => `translate(${{d.x}}, ${{d.y}})`);
        
        nodes.append("circle").attr("r", 10)
            .attr("fill", d => d.type === 'focus' ? '#00ffa2' : (d.type === 'parent' ? '#ff4b4b' : '#60b4ff'));
        
        nodes.append("text").attr("dy", 25).attr("text-anchor", "middle")
            .text(d => d.id).style("fill", "white").style("font-size", "12px").style("font-family", "sans-serif");
    </script>
    """
    components.html(html_code, height=420)

    # Navigation Controls
    col_p, col_c = st.columns(2)
    with col_p:
        st.caption("Zoom Out (Parents)")
        for p in parents:
            if st.button(f"↑ {p}", key=f"p_{p}"):
                st.session_state.explorer_focus = p
                st.rerun()
    with col_c:
        st.caption("Zoom In (Children)")
        for c in children:
            if st.button(f"↓ {c}", key=f"c_{c}"):
                st.session_state.explorer_focus = c
                st.rerun()

    st.divider()
    if st.button(
        f"🎯 Use '{focus}' in Annotation", type="primary", use_container_width=True
    ):
        st.session_state.last_explorer_selection = focus
        st.toast(f"Copying {focus}... Use '+' in table and select it.")


# --- 5. DATA STATE ---
if "gold_data" not in st.session_state:
    if GOLD_PATH.exists():
        st.session_state.gold_data = json.loads(GOLD_PATH.read_text())
    else:
        st.session_state.gold_data = json.loads(SEED_PATH.read_text())
    st.session_state.seed_data = json.loads(SEED_PATH.read_text())

if "idx" not in st.session_state:
    st.session_state.idx = 0

# --- 6. MAIN UI ---
idx = st.session_state.idx
gold_ex = st.session_state.gold_data[idx]
seed_ex = st.session_state.seed_data[idx]

# Nav Bar
nav_l, nav_c, nav_r = st.columns([1, 3, 1])
with nav_l:
    if st.button("← Previous", use_container_width=True) and idx > 0:
        st.session_state.idx -= 1
        st.rerun()
with nav_c:
    st.markdown(
        f"<h2 style='text-align: center;'>{gold_ex['id']}</h2>", unsafe_allow_html=True
    )
with nav_r:
    if (
        st.button("Next →", use_container_width=True)
        and idx < len(st.session_state.gold_data) - 1
    ):
        st.session_state.idx += 1
        st.rerun()

st.divider()

col_seed, col_gold = st.columns(2)

with col_seed:
    with st.container(border=True):
        st.subheader("🧱 Seed Reference")
        st.write("**Patterns:**", ", ".join(seed_ex.get("movement_patterns", [])))
        st.write("**Modalities:**", ", ".join(seed_ex.get("training_modalities", [])) or "None")
        st.write("**Unilateral:**", "✅" if seed_ex.get("is_unilateral") else "❌")
        st.table(seed_ex.get("muscle_involvements", []))

with col_gold:
    with st.container(border=True):
        st.subheader("🏆 Gold Standard")

        with st.form("gold_form"):
            new_patterns = st.multiselect(
                "Movement Patterns",
                options=PATTERNS,
                default=[
                    p for p in gold_ex.get("movement_patterns", []) if p in PATTERNS
                ],
            )

            f_a, f_b = st.columns(2)
            with f_a:
                new_modalities = st.multiselect(
                    "Training Modalities",
                    options=MODALITIES,
                    default=[
                        m for m in gold_ex.get("training_modalities", []) if m in MODALITIES
                    ],
                )
            with f_b:
                st.write("")  # Spacer
                new_unilateral = st.checkbox(
                    "Is Unilateral", value=gold_ex.get("is_unilateral", False)
                )

            st.markdown("**Muscle Involvements**")
            new_invs = st.data_editor(
                gold_ex.get("muscle_involvements", []),
                column_config={
                    "muscle": st.column_config.SelectboxColumn(
                        "Muscle", options=MUSCLES, required=True
                    ),
                    "degree": st.column_config.SelectboxColumn(
                        "Degree", options=DEGREES, required=True
                    ),
                },
                num_rows="dynamic",
                use_container_width=True,
                key=f"editor_{idx}",
            )

            # Validation Flags
            muscles_in_editor = [i["muscle"] for i in new_invs if "muscle" in i]
            for flag in check_double_counting(muscles_in_editor):
                st.warning(flag)

            c_save, c_reset = st.columns(2)
            with c_save:
                if st.form_submit_button(
                    "💾 Save Changes", type="primary", use_container_width=True
                ):
                    if not new_patterns:
                        st.error("Min 1 Pattern required.")
                    else:
                        st.session_state.gold_data[idx].update(
                            {
                                "movement_patterns": new_patterns,
                                "training_modalities": new_modalities,
                                "is_unilateral": new_unilateral,
                                "muscle_involvements": new_invs,
                            }
                        )
                        GOLD_PATH.write_text(
                            json.dumps(st.session_state.gold_data, indent=2)
                        )
                        st.toast("Saved!")
                        st.rerun()
            with c_reset:
                if st.button("🔄 Reset to Seed", use_container_width=True):
                    st.session_state.gold_data[idx] = json.loads(json.dumps(seed_ex))
                    st.rerun()

        # Modal Launcher inside Gold Column
        if st.button("🔍 Explore Muscle Hierarchy", use_container_width=True):
            muscle_explorer()

        if "last_explorer_selection" in st.session_state:
            st.info(
                f"Last selection from explorer: **{st.session_state.last_explorer_selection}**"
            )
