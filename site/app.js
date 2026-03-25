/**
 * free-exercise-graph — SPA
 * Vanilla JS, no build step, no dependencies.
 */

const DEGREE_ORDER = ["PrimeMover", "Synergist", "Stabilizer", "PassiveTarget"];
const DEGREE_CLASS = {
  PrimeMover: "prime",
  Synergist: "synergist",
  Stabilizer: "stabilizer",
  PassiveTarget: "passive",
};
const DEGREE_LABEL = {
  PrimeMover: "Prime Mover",
  Synergist: "Synergist",
  Stabilizer: "Stabilizer",
  PassiveTarget: "Passive Target",
};

const state = {
  exercises: [],
  vocab: {},
  activeTab: "exercises",
  search: "",
  filters: {
    muscles: [],
    patterns: [],
    modalities: [],
    equipment: [],
    joints: [],
  },
  patternDescendants: {},
  muscleDescendants: {},
  bodyView: "front",
  sheetExercise: null,
};

async function loadData() {
  try {
    const [stateExercises, stateVocab] = await Promise.all([
      loadJson("data.json"),
      loadJson("vocab.json"),
    ]);
    if (!Array.isArray(stateExercises)) {
      throw new Error("data.json did not return an exercise array");
    }
    if (!stateVocab || typeof stateVocab !== "object") {
      throw new Error("vocab.json did not return an object");
    }
    state.exercises = stateExercises;
    state.vocab = stateVocab;
    buildHierarchyMaps();
    init();
  } catch (err) {
    console.error(err);
    renderFatalError(err);
  }
}

function el(id) { return document.getElementById(id); }

async function loadJson(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${path} failed to load (${res.status} ${res.statusText})`);
  }
  return res.json();
}

function renderFatalError(err) {
  const message = err instanceof Error ? err.message : String(err);
  el("result-count").textContent = "Site data failed to load";
  el("exercise-list").innerHTML = `
    <div class="empty">
      <strong>Static site data failed to load.</strong><br>
      ${message}<br><br>
      Make sure the deployed artifact includes <code>data.json</code> and <code>vocab.json</code>
      in the same directory as <code>index.html</code>.
    </div>`;
}

function labelFor(id) {
  for (const p of state.vocab.patterns || []) if (p.id === id) return p.label;
  for (const j of state.vocab.joints || []) {
    if (j.id === id) return j.label;
    for (const a of j.actions || []) if (a.id === id) return a.label;
  }
  for (const m of state.vocab.modalities || []) if (m.id === id) return m.label;
  for (const e of state.vocab.equipment || []) if (e.id === id) return e.label;
  return id.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2");
}

function findMuscleNode(id, nodes = state.vocab.muscles?.regions || []) {
  for (const node of nodes) {
    if (node.id === id) return node;
    const found = findMuscleNode(id, node.children || []);
    if (found) return found;
  }
  return null;
}

function muscleLabel(id) {
  return findMuscleNode(id)?.label || labelFor(id);
}

function buildHierarchyMaps() {
  const patternChildren = {};
  for (const pattern of state.vocab.patterns || []) {
    const parent = pattern.parent || null;
    patternChildren[parent] = patternChildren[parent] || [];
    patternChildren[parent].push(pattern.id);
  }

  const patternDescendants = {};
  function collectPatternDescendants(id) {
    const descendants = [id];
    for (const child of patternChildren[id] || []) {
      descendants.push(...collectPatternDescendants(child));
    }
    patternDescendants[id] = descendants;
    return descendants;
  }
  for (const pattern of state.vocab.patterns || []) collectPatternDescendants(pattern.id);
  state.patternDescendants = patternDescendants;

  const muscleDescendants = {};
  function collectMuscleDescendants(node) {
    const descendants = [node.id];
    for (const child of node.children || []) {
      descendants.push(...collectMuscleDescendants(child));
    }
    muscleDescendants[node.id] = descendants;
    return descendants;
  }
  for (const region of state.vocab.muscles?.regions || []) collectMuscleDescendants(region);
  state.muscleDescendants = muscleDescendants;
}

function selectedIds(type) {
  return state.filters[type];
}

function toggleFilter(type, id) {
  const arr = selectedIds(type);
  const idx = arr.indexOf(id);
  if (idx === -1) arr.push(id);
  else arr.splice(idx, 1);
  rerenderAll();
}

function clearFilters() {
  state.filters = {
    muscles: [],
    patterns: [],
    modalities: [],
    equipment: [],
    joints: [],
  };
  rerenderAll();
}

function filterMatchesHierarchy(selected, descendantsMap, values) {
  if (!selected.length) return true;
  return selected.some(id => {
    const allowed = descendantsMap[id] || [id];
    return values.some(value => allowed.includes(value));
  });
}

function filteredExercises() {
  const q = state.search.toLowerCase().trim();
  const { muscles, patterns, modalities, equipment, joints } = state.filters;

  return state.exercises.filter(ex => {
    if (q && !ex.name.toLowerCase().includes(q)) return false;
    if (!filterMatchesHierarchy(patterns, state.patternDescendants, ex.patterns)) return false;
    if (!filterMatchesHierarchy(muscles, state.muscleDescendants, ex.muscles.map(m => m[0]))) return false;
    if (modalities.length && !modalities.includes(ex.modality)) return false;
    if (equipment.length && !equipment.some(eq => ex.equipment.includes(eq))) return false;
    if (joints.length && !joints.some(j => ex.primaryJA.includes(j) || ex.supportingJA.includes(j))) return false;
    return true;
  });
}

function hasActiveFilters() {
  return Object.values(state.filters).some(values => values.length > 0);
}

function getSubstitutes(ex, limit = 8) {
  return state.exercises
    .filter(candidate => candidate.id !== ex.id)
    .map(candidate => {
      const sharedPattern = ex.patterns.filter(p => candidate.patterns.includes(p)).length;
      const sharedJA = ex.primaryJA.filter(ja => candidate.primaryJA.includes(ja)).length;
      const diffEquip = ex.equipment.length > 0 && ex.equipment.some(eq => !candidate.equipment.includes(eq));
      const score = sharedPattern * 3 + sharedJA * 2 + (diffEquip ? 1 : 0);
      const reasons = [];
      if (sharedPattern) {
        reasons.push(ex.patterns.filter(p => candidate.patterns.includes(p)).map(labelFor).join(", "));
      } else if (sharedJA) {
        reasons.push(ex.primaryJA.filter(ja => candidate.primaryJA.includes(ja)).map(labelFor).join(", "));
      }
      return { ex: candidate, score, reason: reasons[0] || "" };
    })
    .filter(result => result.score >= 3)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

function renderHero() {
  const stats = [
    { label: "Exercises", value: state.exercises.length.toLocaleString() },
    { label: "Patterns", value: (state.vocab.patterns || []).filter(item => item.depth === 0).length },
    { label: "Muscle regions", value: (state.vocab.muscles?.regions || []).length },
    { label: "Joint groups", value: (state.vocab.joints || []).length },
  ];
  el("hero-stats").innerHTML = stats.map(stat => `
    <span class="hero-stat"><strong>${stat.value}</strong> ${stat.label}</span>
  `).join("");
}

function renderActiveFilters() {
  const pills = [];
  for (const [type, ids] of Object.entries(state.filters)) {
    for (const id of ids) {
      pills.push(`
        <span class="active-filter-pill">
          ${labelFor(id)}
          <button type="button" data-remove-type="${type}" data-remove-id="${id}" aria-label="Remove ${labelFor(id)}">✕</button>
        </span>
      `);
    }
  }
  const container = el("active-filters");
  container.innerHTML = pills.join("");
  container.style.display = pills.length ? "flex" : "none";
  container.querySelectorAll("[data-remove-type]").forEach(button => {
    button.addEventListener("click", () => toggleFilter(button.dataset.removeType, button.dataset.removeId));
  });
}

function renderExerciseList() {
  const results = filteredExercises();
  el("result-count").textContent = `${results.length.toLocaleString()} exercise${results.length !== 1 ? "s" : ""}`;
  renderActiveFilters();

  const list = el("exercise-list");
  if (!results.length) {
    list.innerHTML = '<div class="empty">No exercises match your current filters.</div>';
    return;
  }

  const toRender = results.slice(0, 200);
  list.innerHTML = toRender.map(ex => {
    const badges = [];
    if (ex.modality) badges.push(`<span class="badge badge-modality">${labelFor(ex.modality)}</span>`);
    if (ex.combination) badges.push(`<span class="badge badge-combo">Combination</span>`);
    if (ex.laterality) badges.push(`<span class="badge badge-isolation">${labelFor(ex.laterality)}</span>`);

    const topMuscles = ex.muscles
      .filter(([_, degree]) => degree === "PrimeMover" || degree === "Synergist")
      .slice(0, 3)
      .map(([muscle, degree]) => `<span class="muscle-pill pill-${DEGREE_CLASS[degree]}">${muscleLabel(muscle)}</span>`)
      .join("");

    const pattern = ex.patterns.slice(0, 2).map(labelFor).join(" · ");

    return `
      <div class="exercise-card" data-id="${ex.id}">
        <div class="card-header">
          <span class="card-name">${ex.name}</span>
          ${badges.join("")}
        </div>
        <div class="card-meta">
          ${topMuscles}
          ${pattern ? `<span style="font-size:12px;color:var(--text-2)">${pattern}</span>` : ""}
        </div>
      </div>
    `;
  }).join("");

  if (results.length > 200) {
    list.innerHTML += `<div class="empty" style="padding:16px">Showing 200 of ${results.length}. Refine your search to see more.</div>`;
  }

  list.querySelectorAll(".exercise-card").forEach(card => {
    card.addEventListener("click", () => openSheet(card.dataset.id));
  });
}

function openSheet(exerciseId) {
  const ex = state.exercises.find(item => item.id === exerciseId);
  if (!ex) return;
  state.sheetExercise = exerciseId;

  const badges = [];
  if (ex.modality) badges.push(`<span class="badge badge-modality">${labelFor(ex.modality)}</span>`);
  if (ex.combination) badges.push(`<span class="badge badge-combo">Combination</span>`);
  if (ex.laterality) badges.push(`<span class="badge badge-isolation">${labelFor(ex.laterality)}</span>`);

  const musclesByDegree = {};
  for (const [muscle, degree] of ex.muscles) {
    (musclesByDegree[degree] = musclesByDegree[degree] || []).push(muscle);
  }
  const muscleBarsHtml = DEGREE_ORDER
    .filter(degree => musclesByDegree[degree]?.length)
    .map(degree => {
      const cls = DEGREE_CLASS[degree];
      return musclesByDegree[degree].map(muscle => `
        <div class="muscle-bar">
          <span class="muscle-bar-name">${muscleLabel(muscle)}</span>
          <div class="muscle-bar-track"><div class="muscle-bar-fill bar-${cls}"></div></div>
          <span class="degree-tag deg-${cls}">${DEGREE_LABEL[degree]}</span>
        </div>`).join("");
    }).join("");

  const patternsHtml = ex.patterns.length
    ? ex.patterns.map(pattern => `<span class="tag tag-primary">${labelFor(pattern)}</span>`).join("")
    : `<span class="tag" style="color:var(--text-2)">None</span>`;

  const primaryJAHtml = ex.primaryJA.map(ja => `<span class="tag tag-primary">${labelFor(ja)}</span>`).join("");
  const supportingJAHtml = ex.supportingJA.map(ja => `<span class="tag">${labelFor(ja)}</span>`).join("");
  const equipHtml = ex.equipment.length
    ? ex.equipment.map(eq => `<span class="tag">${labelFor(eq)}</span>`).join("")
    : `<span class="tag">Bodyweight</span>`;
  const styleHtml = ex.style.length
    ? ex.style.map(style => `<span class="tag">${labelFor(style)}</span>`).join("")
    : "";

  const subs = getSubstitutes(ex);
  const subsHtml = subs.length
    ? subs.map(({ ex: sub, reason }) => `
        <div class="sub-card" data-id="${sub.id}">
          <div>${sub.name}</div>
          ${reason ? `<div class="sub-why">${reason}</div>` : ""}
        </div>
      `).join("")
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

  el("sheet-content").querySelectorAll(".sub-card").forEach(card => {
    card.addEventListener("click", event => {
      event.stopPropagation();
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

function renderPatternTags() {
  const patternTags = el("pattern-tags");
  patternTags.innerHTML = (state.vocab.patterns || []).map(pattern => {
    const active = state.filters.patterns.includes(pattern.id);
    return `
      <span class="filter-tag ${active ? "active" : ""}" data-type="patterns" data-id="${pattern.id}" style="padding-left:${10 + pattern.depth * 14}px">
        ${pattern.label} <span style="opacity:.6;font-size:11px">${pattern.count}</span>
      </span>
    `;
  }).join("");
}

function renderMuscleFilterTree(nodes, depth = 0) {
  return nodes.map(node => {
    const active = state.filters.muscles.includes(node.id);
    return `
      <div>
        <button class="hierarchy-node ${active ? "active" : ""}" data-type="muscles" data-id="${node.id}" style="margin-left:${depth * 16}px">
          <span class="hierarchy-node-main">
            <span>${node.label}</span>
            <span class="hierarchy-node-kind">${node.type}</span>
          </span>
          <span class="vocab-item-count">${node.count}</span>
        </button>
        ${node.children?.length ? `<div class="hierarchy-children">${renderMuscleFilterTree(node.children, depth + 1)}</div>` : ""}
      </div>
    `;
  }).join("");
}

function renderFilterPanels() {
  renderPatternTags();

  el("muscle-filter-tags").innerHTML = renderMuscleFilterTree(state.vocab.muscles?.regions || []);

  el("modality-tags").innerHTML = (state.vocab.modalities || []).map(modality => {
    const active = state.filters.modalities.includes(modality.id);
    return `
      <span class="filter-tag ${active ? "active" : ""}" data-type="modalities" data-id="${modality.id}">
        ${modality.label} <span style="opacity:.6;font-size:11px">${modality.count}</span>
      </span>
    `;
  }).join("");

  el("equipment-tags").innerHTML = (state.vocab.equipment || []).map(equipment => {
    const active = state.filters.equipment.includes(equipment.id);
    return `
      <span class="filter-tag ${active ? "active" : ""}" data-type="equipment" data-id="${equipment.id}">
        ${equipment.label} <span style="opacity:.6;font-size:11px">${equipment.count}</span>
      </span>
    `;
  }).join("");

  document.querySelectorAll(".filter-tag[data-type], .hierarchy-node[data-type]").forEach(node => {
    node.addEventListener("click", () => toggleFilter(node.dataset.type, node.dataset.id));
  });
}

function renderMuscleSection(nodes, depth = 0) {
  return nodes.map(node => {
    const active = state.filters.muscles.includes(node.id);
    return `
      <div class="muscle-group-row ${active ? "active" : ""}" data-muscle="${node.id}" style="margin-left:${depth * 16}px">
        <span>${node.label}</span>
        <span class="muscle-count">${node.count} exercises</span>
      </div>
      ${node.children?.length ? renderMuscleSection(node.children, depth + 1) : ""}
    `;
  }).join("");
}

function renderMuscleList() {
  const regions = state.vocab.muscles?.regions || [];
  el("muscle-list").innerHTML = regions.map(region => `
    <div class="vocab-section">
      <div class="vocab-section-header open" data-muscle-section="${region.id}">
        ${region.label} <span class="vocab-chevron">▼</span>
      </div>
      <div class="vocab-items open" id="muscle-section-${region.id}">
        ${renderMuscleSection(region.children || [])}
      </div>
    </div>
  `).join("");

  el("muscle-list").querySelectorAll(".muscle-group-row").forEach(row => {
    row.addEventListener("click", () => toggleFilter("muscles", row.dataset.muscle));
  });

  document.querySelectorAll("[data-muscle-section]").forEach(header => {
    header.addEventListener("click", event => {
      if (event.target.closest(".muscle-group-row")) return;
      const section = el(`muscle-section-${header.dataset.muscleSection}`);
      const open = section.classList.toggle("open");
      header.classList.toggle("open", open);
    });
  });
}

function renderVocab() {
  el("vocab-modalities").innerHTML = (state.vocab.modalities || []).map(modality => {
    const active = state.filters.modalities.includes(modality.id);
    return `
      <div class="vocab-item ${active ? "active" : ""}" data-type="modalities" data-id="${modality.id}">
        <span>${modality.label}</span>
        <span class="vocab-item-count">${modality.count}</span>
      </div>
    `;
  }).join("");

  el("vocab-patterns").innerHTML = (state.vocab.patterns || []).map(pattern => {
    const active = state.filters.patterns.includes(pattern.id);
    return `
      <div class="vocab-item ${active ? "active" : ""} indent-${Math.min(pattern.depth, 3)}" data-type="patterns" data-id="${pattern.id}">
        <span>${pattern.label}</span>
        <span class="vocab-item-count">${pattern.count}</span>
      </div>
    `;
  }).join("");

  el("vocab-joints").innerHTML = (state.vocab.joints || []).flatMap(joint =>
    (joint.actions || []).map(action => {
      const active = state.filters.joints.includes(action.id);
      return `
        <div class="vocab-item ${active ? "active" : ""} indent-1" data-type="joints" data-id="${action.id}">
          <span>${action.label} <span style="color:var(--text-2);font-size:12px">${joint.label}</span></span>
          <span class="vocab-item-count">${action.count}</span>
        </div>
      `;
    })
  ).join("");

  el("vocab-equipment").innerHTML = (state.vocab.equipment || []).map(equipment => {
    const active = state.filters.equipment.includes(equipment.id);
    return `
      <div class="vocab-item ${active ? "active" : ""}" data-type="equipment" data-id="${equipment.id}">
        <span>${equipment.label}</span>
        <span class="vocab-item-count">${equipment.count}</span>
      </div>
    `;
  }).join("");

  document.querySelectorAll(".vocab-item[data-type]").forEach(item => {
    item.addEventListener("click", () => toggleFilter(item.dataset.type, item.dataset.id));
  });
}

function initVocabAccordions() {
  document.querySelectorAll(".vocab-section-header").forEach(header => {
    if (header.dataset.bound === "true") return;
    header.dataset.bound = "true";
    header.addEventListener("click", () => {
      const section = header.dataset.section;
      if (!section) return;
      const items = el(`vocab-${section}`);
      const open = items.classList.toggle("open");
      header.classList.toggle("open", open);
    });
  });
}

function switchTab(tab) {
  state.activeTab = tab;
  document.body.dataset.tab = tab;
  document.querySelectorAll(".view").forEach(view => view.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(button => button.classList.remove("active"));
  el(`view-${tab}`).classList.add("active");
  document.querySelector(`.nav-btn[data-tab="${tab}"]`).classList.add("active");

  if (tab === "muscles") renderMuscleList();
  if (tab === "vocab") renderVocab();
}

function initFilterChips() {
  document.querySelectorAll(".filter-chip[data-panel]").forEach(chip => {
    chip.addEventListener("click", () => {
      const panel = el(`panel-${chip.dataset.panel}`);
      const isOpen = panel.classList.toggle("open");
      chip.classList.toggle("active", isOpen);
      if (isOpen) renderFilterPanels();
    });
  });

  el("clear-filters").addEventListener("click", () => clearFilters());
}

function updateClearBtn() {
  el("clear-filters").style.display = hasActiveFilters() ? "" : "none";
}

function highlightAnatomy() {
  document.querySelectorAll(".muscle-region").forEach(region => {
    const regionMuscles = region.dataset.muscles.split(",");
    region.classList.toggle(
      "highlighted",
      regionMuscles.some(muscle => filterMatchesHierarchy(state.filters.muscles, state.muscleDescendants, [muscle]))
    );
  });
}

function initAnatomyMap() {
  document.querySelectorAll(".muscle-region").forEach(region => {
    region.addEventListener("click", () => {
      const muscles = region.dataset.muscles.split(",");
      const allActive = muscles.every(muscle => state.filters.muscles.includes(muscle));
      if (allActive) {
        state.filters.muscles = state.filters.muscles.filter(muscle => !muscles.includes(muscle));
      } else {
        muscles.forEach(muscle => {
          if (!state.filters.muscles.includes(muscle)) state.filters.muscles.push(muscle);
        });
      }
      rerenderAll();
    });
  });
}

function initSearch() {
  el("search-input").addEventListener("input", event => {
    state.search = event.target.value;
    renderExerciseList();
  });
}

function initNav() {
  document.querySelectorAll(".nav-btn[data-tab]").forEach(button => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
}

function rerenderAll() {
  updateClearBtn();
  renderFilterPanels();
  renderExerciseList();
  renderMuscleList();
  renderVocab();
  highlightAnatomy();
}

function init() {
  renderHero();
  initNav();
  initSearch();
  initFilterChips();
  initAnatomyMap();
  renderFilterPanels();
  renderExerciseList();
  renderMuscleList();
  renderVocab();
  initVocabAccordions();
  highlightAnatomy();
}

loadData();
