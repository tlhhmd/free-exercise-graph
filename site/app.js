/**
 * free-exercise-graph — SPA
 * Vanilla JS, no build step, no dependencies.
 */

const DEGREE_ORDER = ["PrimeMover", "Synergist", "Stabilizer", "PassiveTarget"];
const DEGREE_CLASS = {
  PrimeMover:  "prime",
  Synergist:   "synergist",
  Stabilizer:  "stabilizer",
  PassiveTarget: "passive",
};
const DEGREE_LABEL = {
  PrimeMover:   "Prime Mover",
  Synergist:    "Synergist",
  Stabilizer:   "Stabilizer",
  PassiveTarget: "Passive Target",
};

// ── State ────────────────────────────────────────────────────────────────────

const state = {
  exercises: [],
  vocab: {},
  activeTab: "exercises",
  search: "",
  filters: {
    muscles: [],      // muscle IDs
    patterns: [],     // pattern IDs
    equipment: [],    // equipment IDs
    joints: [],       // joint action IDs
    compound: false,
  },
  bodyView: "front",
  sheetExercise: null,
};

// ── Data loading ─────────────────────────────────────────────────────────────

async function loadData() {
  const [exRes, vocRes] = await Promise.all([
    fetch("data.json"),
    fetch("vocab.json"),
  ]);
  state.exercises = await exRes.json();
  state.vocab = await vocRes.json();
  init();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function el(id) { return document.getElementById(id); }

function labelFor(id) {
  // Try vocab lookup first, then split camelCase
  for (const p of (state.vocab.patterns || [])) {
    if (p.id === id) return p.label;
  }
  for (const j of (state.vocab.joints || [])) {
    for (const a of j.actions) if (a.id === id) return a.label;
    if (j.id === id) return j.label;
  }
  for (const e of (state.vocab.equipment || [])) {
    if (e.id === id) return e.label;
  }
  // camelCase split fallback
  return id.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2");
}

function muscleLabel(id) {
  for (const r of (state.vocab.muscles?.regions || [])) {
    for (const g of r.groups) if (g.id === id) return g.label;
    if (r.id === id) return r.label;
  }
  return labelFor(id);
}

// ── Filtering ─────────────────────────────────────────────────────────────────

function filteredExercises() {
  const q = state.search.toLowerCase().trim();
  const { muscles, patterns, equipment, joints, compound } = state.filters;

  return state.exercises.filter(ex => {
    if (q && !ex.name.toLowerCase().includes(q)) return false;
    if (compound && !ex.compound) return false;
    if (patterns.length && !patterns.some(p => ex.patterns.includes(p))) return false;
    if (equipment.length && !equipment.some(e => ex.equipment.includes(e))) return false;
    if (joints.length && !joints.some(j => ex.primaryJA.includes(j) || ex.supportingJA.includes(j))) return false;
    if (muscles.length) {
      const exMuscles = ex.muscles.map(m => m[0]);
      if (!muscles.some(m => exMuscles.includes(m))) return false;
    }
    return true;
  });
}

function hasActiveFilters() {
  const f = state.filters;
  return f.muscles.length || f.patterns.length || f.equipment.length || f.joints.length || f.compound;
}

// ── Substitution ─────────────────────────────────────────────────────────────

function getSubstitutes(ex, limit = 8) {
  return state.exercises
    .filter(e => e.id !== ex.id)
    .map(e => {
      const sharedPattern = ex.patterns.filter(p => e.patterns.includes(p)).length;
      const sharedJA = ex.primaryJA.filter(ja => e.primaryJA.includes(ja)).length;
      const diffEquip = ex.equipment.length > 0 && ex.equipment.some(eq => !e.equipment.includes(eq));
      const score = sharedPattern * 3 + sharedJA * 2 + (diffEquip ? 1 : 0);
      const reasons = [];
      if (sharedPattern) reasons.push(ex.patterns.filter(p => e.patterns.includes(p)).map(labelFor).join(", "));
      if (sharedJA && !sharedPattern) reasons.push(ex.primaryJA.filter(ja => e.primaryJA.includes(ja)).map(labelFor).join(", "));
      return { ex: e, score, reason: reasons[0] || "" };
    })
    .filter(r => r.score >= 3)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

// ── Rendering: exercise list ──────────────────────────────────────────────────

function renderExerciseList() {
  const results = filteredExercises();
  el("result-count").textContent = `${results.length.toLocaleString()} exercise${results.length !== 1 ? "s" : ""}`;

  const list = el("exercise-list");
  if (!results.length) {
    list.innerHTML = '<div class="empty">No exercises match your filters.</div>';
    return;
  }

  // Virtualise: render max 200 at a time (prevents long paint on initial load)
  const toRender = results.slice(0, 200);
  list.innerHTML = toRender.map(ex => {
    const badge = ex.combination
      ? `<span class="badge badge-combo">Combo</span>`
      : ex.compound
        ? `<span class="badge badge-compound">Compound</span>`
        : `<span class="badge badge-isolation">Isolation</span>`;

    const topMuscles = ex.muscles
      .filter(m => m[1] === "PrimeMover" || m[1] === "Synergist")
      .slice(0, 3)
      .map(([m, d]) => `<span class="muscle-pill pill-${DEGREE_CLASS[d]}">${muscleLabel(m)}</span>`)
      .join("");

    const pattern = ex.patterns.slice(0, 2).map(p =>
      `<span style="color:var(--text-2)">${labelFor(p)}</span>`).join(" · ");

    return `<div class="exercise-card" data-id="${ex.id}">
      <div class="card-header">
        <span class="card-name">${ex.name}</span>
        ${badge}
      </div>
      <div class="card-meta">
        ${topMuscles}
        ${pattern ? `<span style="font-size:12px;color:var(--text-2)">${pattern}</span>` : ""}
      </div>
    </div>`;
  }).join("");

  if (results.length > 200) {
    list.innerHTML += `<div class="empty" style="padding:16px">Showing 200 of ${results.length}. Refine your search to see more.</div>`;
  }

  // Bind clicks
  list.querySelectorAll(".exercise-card").forEach(card => {
    card.addEventListener("click", () => openSheet(card.dataset.id));
  });
}

// ── Rendering: detail sheet ───────────────────────────────────────────────────

function openSheet(exerciseId) {
  const ex = state.exercises.find(e => e.id === exerciseId);
  if (!ex) return;
  state.sheetExercise = exerciseId;

  const badges = [];
  if (ex.combination) badges.push(`<span class="badge badge-combo">Combination</span>`);
  else if (ex.compound) badges.push(`<span class="badge badge-compound">Compound</span>`);
  else badges.push(`<span class="badge badge-isolation">Isolation</span>`);
  if (ex.laterality) badges.push(`<span class="badge" style="background:var(--surface-2)">${labelFor(ex.laterality)}</span>`);
  if (ex.modality) badges.push(`<span class="badge" style="background:var(--accent-soft);color:var(--accent)">${labelFor(ex.modality)}</span>`);

  // Muscles
  const musclesByDegree = {};
  for (const [m, d] of ex.muscles) {
    (musclesByDegree[d] = musclesByDegree[d] || []).push(m);
  }
  const muscleBarsHtml = DEGREE_ORDER
    .filter(d => musclesByDegree[d]?.length)
    .map(d => {
      const cls = DEGREE_CLASS[d];
      return musclesByDegree[d].map(m => `
        <div class="muscle-bar">
          <span class="muscle-bar-name">${muscleLabel(m)}</span>
          <div class="muscle-bar-track"><div class="muscle-bar-fill bar-${cls}"></div></div>
          <span class="degree-tag deg-${cls}">${DEGREE_LABEL[d]}</span>
        </div>`).join("");
    }).join("");

  // Patterns
  const patternsHtml = ex.patterns.length
    ? ex.patterns.map(p => `<span class="tag tag-primary">${labelFor(p)}</span>`).join("")
    : `<span class="tag" style="color:var(--text-2)">None</span>`;

  // Joint actions
  const primaryJAHtml = ex.primaryJA.map(ja => `<span class="tag tag-primary">${labelFor(ja)}</span>`).join("");
  const supportingJAHtml = ex.supportingJA.map(ja => `<span class="tag">${labelFor(ja)}</span>`).join("");

  // Equipment
  const equipHtml = ex.equipment.length
    ? ex.equipment.map(e => `<span class="tag">${labelFor(e)}</span>`).join("")
    : `<span class="tag">Bodyweight</span>`;

  // Style
  const styleHtml = ex.style.length
    ? ex.style.map(s => `<span class="tag">${labelFor(s)}</span>`).join("")
    : "";

  // Substitutes
  const subs = getSubstitutes(ex);
  const subsHtml = subs.length
    ? subs.map(({ ex: s, reason }) => `
        <div class="sub-card" data-id="${s.id}">
          <div>${s.name}</div>
          ${reason ? `<div class="sub-why">${reason}</div>` : ""}
        </div>`).join("")
    : `<div style="font-size:13px;color:var(--text-2)">No close substitutes found.</div>`;

  el("sheet-content").innerHTML = `
    <div class="sheet-title">${ex.name}</div>
    <div class="sheet-badges">${badges.join("")}</div>

    <div class="section-label">Muscles</div>
    <div class="degree-legend">
      <span class="legend-item"><span class="legend-dot" style="background:var(--deg-prime)"></span>Prime Mover</span>
      <span class="legend-item"><span class="legend-dot" style="background:var(--deg-synergist)"></span>Synergist</span>
      <span class="legend-item"><span class="legend-dot" style="background:var(--deg-stabilizer)"></span>Stabilizer</span>
    </div>
    <div class="muscle-bars">${muscleBarsHtml || '<span style="font-size:13px;color:var(--text-2)">No data</span>'}</div>

    <div class="section-label">Movement Patterns</div>
    <div class="tag-list">${patternsHtml}</div>

    ${primaryJAHtml ? `<div class="section-label">Primary Joint Actions</div><div class="tag-list">${primaryJAHtml}</div>` : ""}
    ${supportingJAHtml ? `<div class="section-label">Supporting Joint Actions</div><div class="tag-list">${supportingJAHtml}</div>` : ""}

    <div class="section-label">Equipment</div>
    <div class="tag-list">${equipHtml}</div>

    ${styleHtml ? `<div class="section-label">Style</div><div class="tag-list">${styleHtml}</div>` : ""}

    <div class="section-label">Substitutes</div>
    <div class="sub-list">${subsHtml}</div>
  `;

  el("sheet-overlay").classList.add("open");
  document.body.style.overflow = "hidden";

  // Sub card navigation
  el("sheet-content").querySelectorAll(".sub-card").forEach(card => {
    card.addEventListener("click", e => {
      e.stopPropagation();
      el("detail-sheet").scrollTop = 0;
      openSheet(card.dataset.id);
    });
  });
}

window.app = window.app || {};
app.closeSheet = function(e) {
  if (e.target === el("sheet-overlay")) {
    el("sheet-overlay").classList.remove("open");
    document.body.style.overflow = "";
    state.sheetExercise = null;
  }
};

// ── Rendering: filter panels ──────────────────────────────────────────────────

function renderFilterPanels() {
  // Patterns
  const patternTags = el("pattern-tags");
  const parents = state.vocab.patterns?.filter(p => !p.parent) || [];
  patternTags.innerHTML = state.vocab.patterns?.map(p => {
    const active = state.filters.patterns.includes(p.id);
    return `<span class="filter-tag ${active ? "active" : ""}" data-type="pattern" data-id="${p.id}"
      style="${p.parent ? "padding-left:18px;font-size:12px" : "font-weight:500"}"
    >${p.label} <span style="opacity:.6;font-size:11px">${p.count}</span></span>`;
  }).join("") || "";

  // Muscle groups
  const muscleTags = el("muscle-filter-tags");
  const groups = state.vocab.muscles?.regions?.flatMap(r => r.groups) || [];
  muscleTags.innerHTML = groups.map(g => {
    const active = state.filters.muscles.includes(g.id);
    return `<span class="filter-tag ${active ? "active" : ""}" data-type="muscle" data-id="${g.id}"
    >${g.label} <span style="opacity:.6;font-size:11px">${g.count}</span></span>`;
  }).join("");

  // Equipment
  const equipTags = el("equipment-tags");
  equipTags.innerHTML = state.vocab.equipment?.map(e => {
    const active = state.filters.equipment.includes(e.id);
    return `<span class="filter-tag ${active ? "active" : ""}" data-type="equipment" data-id="${e.id}"
    >${e.label} <span style="opacity:.6;font-size:11px">${e.count}</span></span>`;
  }).join("") || "";

  // Bind filter tag clicks
  document.querySelectorAll(".filter-tag").forEach(tag => {
    tag.addEventListener("click", () => {
      const { type, id } = tag.dataset;
      const arr = type === "pattern" ? state.filters.patterns
                : type === "muscle"  ? state.filters.muscles
                :                      state.filters.equipment;
      const idx = arr.indexOf(id);
      if (idx === -1) arr.push(id); else arr.splice(idx, 1);
      updateClearBtn();
      renderFilterPanels();
      renderExerciseList();
    });
  });
}

// ── Rendering: muscles tab ────────────────────────────────────────────────────

function renderMuscleList() {
  const regions = state.vocab.muscles?.regions || [];
  el("muscle-list").innerHTML = regions.flatMap(r =>
    r.groups.map(g => {
      const active = state.filters.muscles.includes(g.id);
      return `<div class="muscle-group-row ${active ? "active" : ""}" data-muscle="${g.id}">
        <span>${g.label}</span>
        <span class="muscle-count">${g.count} exercises</span>
      </div>`;
    })
  ).join("");

  el("muscle-list").querySelectorAll(".muscle-group-row").forEach(row => {
    row.addEventListener("click", () => {
      const id = row.dataset.muscle;
      const idx = state.filters.muscles.indexOf(id);
      if (idx === -1) state.filters.muscles.push(id); else state.filters.muscles.splice(idx, 1);
      switchTab("exercises");
      updateClearBtn();
      renderFilterPanels();
      renderExerciseList();
    });
  });
}

app.setBodyView = function(view) {
  state.bodyView = view;
  el("anatomy-front").style.display = view === "front" ? "" : "none";
  el("anatomy-back").style.display  = view === "back"  ? "" : "none";
  el("btn-front").classList.toggle("active", view === "front");
  el("btn-back").classList.toggle("active", view === "back");
};

// ── Rendering: vocabulary tab ─────────────────────────────────────────────────

function renderVocab() {
  // Movement patterns
  const patternItems = state.vocab.patterns || [];
  el("vocab-patterns").innerHTML = patternItems.map(p => {
    const active = state.filters.patterns.includes(p.id);
    return `<div class="vocab-item ${active ? "active" : ""} ${p.parent ? "child" : ""}"
      data-type="pattern" data-id="${p.id}">
      <span>${p.label}</span>
      <span class="vocab-item-count">${p.count}</span>
    </div>`;
  }).join("");

  // Joint actions (grouped by joint)
  el("vocab-joints").innerHTML = (state.vocab.joints || []).flatMap(j =>
    j.actions.map(a => {
      const active = state.filters.joints.includes(a.id);
      return `<div class="vocab-item ${active ? "active" : ""} child"
        data-type="joint" data-id="${a.id}" data-joint="${j.id}">
        <span>${a.label} <span style="color:var(--text-2);font-size:12px">${j.label}</span></span>
        <span class="vocab-item-count">${a.count}</span>
      </div>`;
    })
  ).join("");

  // Equipment
  el("vocab-equipment").innerHTML = (state.vocab.equipment || []).map(e => {
    const active = state.filters.equipment.includes(e.id);
    return `<div class="vocab-item ${active ? "active" : ""}"
      data-type="equipment" data-id="${e.id}">
      <span>${e.label}</span>
      <span class="vocab-item-count">${e.count}</span>
    </div>`;
  }).join("");

  // Vocab item click → filter and navigate to exercises
  document.querySelectorAll(".vocab-item[data-type]").forEach(item => {
    item.addEventListener("click", () => {
      const { type, id } = item.dataset;
      let arr;
      if (type === "pattern")   arr = state.filters.patterns;
      else if (type === "joint") arr = state.filters.joints;
      else                       arr = state.filters.equipment;
      const idx = arr.indexOf(id);
      if (idx === -1) arr.push(id); else arr.splice(idx, 1);
      switchTab("exercises");
      updateClearBtn();
      renderFilterPanels();
      renderExerciseList();
    });
  });
}

// ── Vocab accordion toggle ────────────────────────────────────────────────────

function initVocabAccordions() {
  document.querySelectorAll(".vocab-section-header").forEach(header => {
    header.addEventListener("click", () => {
      const section = header.dataset.section;
      const items = el(`vocab-${section}`);
      const open = items.classList.toggle("open");
      header.classList.toggle("open", open);
    });
  });
}

// ── Tab switching ─────────────────────────────────────────────────────────────

function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  el(`view-${tab}`).classList.add("active");
  document.querySelector(`.nav-btn[data-tab="${tab}"]`).classList.add("active");

  if (tab === "muscles") renderMuscleList();
  if (tab === "vocab") renderVocab();
}

// ── Filter chip toggles ───────────────────────────────────────────────────────

function initFilterChips() {
  document.querySelectorAll(".filter-chip[data-panel]").forEach(chip => {
    chip.addEventListener("click", () => {
      const panel = el(`panel-${chip.dataset.panel}`);
      const isOpen = panel.classList.toggle("open");
      chip.classList.toggle("active", isOpen);
      if (isOpen) renderFilterPanels();
    });
  });

  el("filter-compound").addEventListener("click", () => {
    state.filters.compound = !state.filters.compound;
    el("filter-compound").classList.toggle("active", state.filters.compound);
    updateClearBtn();
    renderExerciseList();
  });

  el("clear-filters").addEventListener("click", () => {
    state.filters = { muscles: [], patterns: [], equipment: [], joints: [], compound: false };
    el("filter-compound").classList.remove("active");
    document.querySelectorAll(".filter-chip[data-panel]").forEach(c => c.classList.remove("active"));
    document.querySelectorAll(".filter-panel").forEach(p => p.classList.remove("open"));
    updateClearBtn();
    renderFilterPanels();
    renderExerciseList();
  });
}

function updateClearBtn() {
  el("clear-filters").style.display = hasActiveFilters() ? "" : "none";
}

// ── Anatomy map clicks ────────────────────────────────────────────────────────

function initAnatomyMap() {
  document.querySelectorAll(".muscle-region").forEach(region => {
    region.addEventListener("click", () => {
      const muscles = region.dataset.muscles.split(",");
      // Toggle: if all already active, remove; otherwise add new ones
      const allActive = muscles.every(m => state.filters.muscles.includes(m));
      if (allActive) {
        state.filters.muscles = state.filters.muscles.filter(m => !muscles.includes(m));
      } else {
        muscles.forEach(m => { if (!state.filters.muscles.includes(m)) state.filters.muscles.push(m); });
      }
      // Highlight
      document.querySelectorAll(".muscle-region").forEach(r => {
        const rm = r.dataset.muscles.split(",");
        r.classList.toggle("highlighted", rm.some(m => state.filters.muscles.includes(m)));
      });
      switchTab("exercises");
      updateClearBtn();
      renderFilterPanels();
      renderExerciseList();
    });
  });
}

// ── Search ────────────────────────────────────────────────────────────────────

function initSearch() {
  el("search-input").addEventListener("input", e => {
    state.search = e.target.value;
    renderExerciseList();
  });
}

// ── Nav ───────────────────────────────────────────────────────────────────────

function initNav() {
  document.querySelectorAll(".nav-btn[data-tab]").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
  initNav();
  initSearch();
  initFilterChips();
  initAnatomyMap();
  initVocabAccordions();
  renderExerciseList();
}

loadData();
