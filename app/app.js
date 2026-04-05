/**
 * free-exercise-graph — static product UI
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


const MOVEMENT_GLYPHS = {
  squat: "↓",
  hinge: "↘",
  push: "→",
  pull: "←",
  core: "◼",
  carry: "⇄",
  locomotion: "↔",
  rotation: "⟳",
  mobility: "∿",
  general: "•",
};

const REGION_DISPLAY = {
  legs_front: "Quads",
  hamstrings: "Hamstrings",
  glutes: "Glutes",
  calves: "Calves",
  core: "Core",
  back: "Back",
  lower_back: "Lower Back",
  shoulders: "Shoulders",
  chest: "Chest",
  arms: "Arms",
  hips: "Hips",
};

const QUERY_ALIASES = {
  bicep: ["biceps brachii", "brachialis"],
  biceps: ["biceps brachii", "brachialis"],
  tricep: ["triceps"],
  triceps: ["triceps"],
  delt: ["deltoid", "shoulder"],
  delts: ["deltoid", "shoulder"],
  shoulder: ["shoulder", "deltoid"],
  shoulders: ["shoulder", "deltoid"],
  quad: ["quadriceps", "vastus", "rectus femoris"],
  quads: ["quadriceps", "vastus", "rectus femoris"],
  glute: ["glute"],
  glutes: ["glute"],
  hamstring: ["hamstring", "biceps femoris", "semitendinosus", "semimembranosus"],
  hamstrings: ["hamstring", "biceps femoris", "semitendinosus", "semimembranosus"],
  abs: ["rectus abdominis", "oblique", "transverse abdominis", "core"],
  "rear delt": ["posterior deltoid"],
  "rear delts": ["posterior deltoid"],
};

const TOKEN_NORMALIZATION = {
  biceps: "bicep",
  triceps: "tricep",
  glutes: "glute",
  quads: "quad",
  delts: "delt",
  shoulders: "shoulder",
  hamstrings: "hamstring",
  calves: "calf",
  obliques: "oblique",
};

const BROWSE_FILTER_KEYS = ["patterns", "modalities", "equipment", "joints", "laterality", "planes", "styles"];
const DEFAULT_THEME = "gold";
const THEME_STORAGE_KEY = "feg-theme";
const THEMES = {
  gold: { label: "Gold", swatchStart: "#ffd94f", swatchEnd: "#c83200" },
  mono: { label: "Mono", swatchStart: "#efefef", swatchEnd: "#202020" },
  dark: { label: "Dark", swatchStart: "#2a2e35", swatchEnd: "#f4efe7" },
  campbell: { label: "Campbell", swatchStart: "#f6e2bd", swatchEnd: "#c9242b" },
};

const FILTER_VALUE_GETTERS = {
  modalities: exercise => exercise.modality ? [exercise.modality] : [],
  equipment: exercise => exercise.equipment || [],
  joints: exercise => [...(exercise.primaryJA || []), ...(exercise.supportingJA || [])],
  laterality: exercise => exercise.laterality ? [exercise.laterality] : [],
  planes: exercise => exercise.planes || [],
  styles: exercise => exercise.style || [],
};

function createEmptyFilters() {
  return {
    muscles: [],
    patterns: [],
    modalities: [],
    equipment: [],
    joints: [],
    laterality: [],
    planes: [],
    styles: [],
  };
}

const state = {
  exercises: [],
  exerciseMap: new Map(),
  searchIndex: new Map(),
  vocab: {},
  activeTab: "exercises",
  mode: "explore",
  search: "",
  filters: createEmptyFilters(),
  patternDescendants: {},
  muscleDescendants: {},
  bodyView: "front",
  sheetExercise: null,
  sheetMode: "user",
  sheetBuilderStep: 0,
  muscleOpenSections: {},
  pendingMuscleScrollTo: null,
  observatoryData: null,
  observatoryLoadPromise: null,
  substituteUi: {},
  theme: DEFAULT_THEME,
};

let searchDebounceTimer = null;

function el(id) { return document.getElementById(id); }

function normalizeTheme(theme) {
  return Object.prototype.hasOwnProperty.call(THEMES, theme) ? theme : DEFAULT_THEME;
}

function getStoredTheme() {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function setStoredTheme(theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Ignore storage errors in private browsing or restricted environments.
  }
}

function renderThemeMenu() {
  const menu = el("theme-menu");
  if (!menu) return;
  menu.innerHTML = Object.entries(THEMES).map(([id, theme]) => `
    <button
      class="theme-option${state.theme === id ? " active" : ""}"
      type="button"
      data-theme="${id}">
      <span
        class="theme-option-swatch"
        style="--swatch-start:${theme.swatchStart}; --swatch-end:${theme.swatchEnd};"
        aria-hidden="true"></span>
      <span>${theme.label}</span>
    </button>
  `).join("");
}

function setThemeMenuOpen(open) {
  const dock = el("theme-dock");
  const toggle = el("theme-toggle");
  const menu = el("theme-menu");
  if (!dock || !toggle || !menu) return;
  dock.classList.toggle("open", open);
  menu.hidden = !open;
  toggle.setAttribute("aria-expanded", open ? "true" : "false");
}

function applyTheme(theme, { persist = true, sync = true } = {}) {
  const nextTheme = normalizeTheme(theme);
  state.theme = nextTheme;
  document.body.dataset.theme = nextTheme;

  const toggle = el("theme-toggle");
  if (toggle) {
    const label = THEMES[nextTheme]?.label || nextTheme;
    toggle.setAttribute("aria-label", `Switch color theme. Current theme: ${label}`);
    toggle.title = `Theme: ${label}`;
  }

  document.querySelectorAll(".theme-option[data-theme]").forEach(button => {
    button.classList.toggle("active", button.dataset.theme === nextTheme);
  });

  if (persist) setStoredTheme(nextTheme);
  if (sync) syncUrlState();
}

async function loadJson(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${path} failed to load (${res.status} ${res.statusText})`);
  }
  return res.json();
}

async function loadText(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${path} failed to load (${res.status} ${res.statusText})`);
  }
  return res.text();
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

async function loadIllustrations() {
  const [frontSvg, backSvg] = await Promise.all([
    loadText("illustrations/anatomy-front.svg"),
    loadText("illustrations/anatomy-back.svg"),
  ]);
  el("anatomy-front-slot").innerHTML = frontSvg;
  el("anatomy-back-slot").innerHTML = backSvg;
}

function labelFor(id) {
  for (const p of state.vocab.patterns || []) if (p.id === id) return p.label;
  for (const j of state.vocab.joints || []) {
    if (j.id === id) return j.label;
    for (const a of j.actions || []) if (a.id === id) return a.label;
  }
  for (const m of state.vocab.modalities || []) if (m.id === id) return m.label;
  for (const e of state.vocab.equipment || []) if (e.id === id) return e.label;
  for (const lat of state.vocab.laterality || []) if (lat.id === id) return lat.label;
  for (const plane of state.vocab.planes || []) if (plane.id === id) return plane.label;
  for (const style of state.vocab.styles || []) if (style.id === id) return style.label;
  return id.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2");
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function titleCase(text) {
  return text.replace(/_/g, " ").replace(/\b\w/g, char => char.toUpperCase());
}

function pluralizeLabel(singular, plural, count) {
  return count === 1 ? singular : plural;
}

function formatCount(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function normalizeSearchText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function canonicalizeSearchText(text) {
  return normalizeSearchText(text)
    .split(" ")
    .filter(Boolean)
    .map(token => TOKEN_NORMALIZATION[token] || token)
    .join(" ");
}

function muscleDegreeWeight(degree) {
  return {
    PrimeMover: 40,
    Synergist: 24,
    Stabilizer: 10,
    PassiveTarget: 4,
  }[degree] || 0;
}

function formatBodyFocus(value) {
  return titleCase(value || "general").replace("Posterior Chain", "Posterior Chain").replace("Anterior Chain", "Anterior Chain").replace("Full Body", "Full Body");
}

function movementGlyph(exercise) {
  const family = exercise.compareAttributes?.movementFamily || exercise.movementFamily || "general";
  return {
    symbol: MOVEMENT_GLYPHS[family] || MOVEMENT_GLYPHS.general,
    label: titleCase(family),
  };
}

function copyCurrentUrl(button, idleText) {
  return async () => {
    syncUrlState();
    try {
      await navigator.clipboard.writeText(window.location.href);
      button.textContent = "Copied";
    } catch {
      button.textContent = "Copy failed";
    }
    window.setTimeout(() => {
      button.textContent = idleText;
    }, 1200);
  };
}

function graphGroundingLine(exercise) {
  const parts = [];
  if (exercise.primaryJA?.length) parts.push(`Primary joint action: ${exercise.primaryJA.map(labelFor).join(", ")}`);
  const primeMovers = exercise.muscles
    .filter(([, degree]) => degree === "PrimeMover")
    .slice(0, 3)
    .map(([muscle]) => muscleLabel(muscle));
  if (primeMovers.length) parts.push(`Prime movers: ${primeMovers.join(", ")}`);
  else if (exercise.muscles?.length) parts.push(`Muscle emphasis: ${muscleLabel(exercise.muscles[0][0])}`);
  parts.push(`Equipment: ${(exercise.equipment?.length ? exercise.equipment.map(labelFor).join(", ") : "Bodyweight")}`);
  return parts.join(" · ");
}

function searchableText(exercise) {
  const parts = [
    exercise.name,
    ...(exercise.patterns || []).map(labelFor),
    ...(exercise.primaryJA || []).map(labelFor),
    ...(exercise.supportingJA || []).map(labelFor),
    ...(exercise.equipment || []).map(labelFor),
    ...(exercise.planes || []).map(labelFor),
    ...(exercise.style || []).map(labelFor),
    ...(exercise.muscles || []).map(([muscle]) => muscleLabel(muscle)),
  ];
  if (exercise.modality) parts.push(labelFor(exercise.modality));
  if (exercise.laterality) parts.push(labelFor(exercise.laterality));
  return parts.join(" ").toLowerCase();
}

function buildFallbackSearchIndex(exercise) {
  const patterns = (exercise.patterns || []).map(labelFor).map(canonicalizeSearchText);
  const primaryJAs = (exercise.primaryJA || []).map(labelFor).map(canonicalizeSearchText);
  const supportingJAs = (exercise.supportingJA || []).map(labelFor).map(canonicalizeSearchText);
  const equipment = (exercise.equipment || []).map(labelFor).map(canonicalizeSearchText);
  const planes = (exercise.planes || []).map(labelFor).map(canonicalizeSearchText);
  const styles = (exercise.style || []).map(labelFor).map(canonicalizeSearchText);
  const muscles = (exercise.muscles || []).map(([muscle]) => canonicalizeSearchText(muscleLabel(muscle)));
  const muscleEntries = (exercise.muscles || []).map(([muscle, degree]) => ({
    label: canonicalizeSearchText(muscleLabel(muscle)),
    degree,
  }));
  const regions = (exercise.visualRegions || []).map(region => canonicalizeSearchText(REGION_DISPLAY[region] || titleCase(region)));
  const aliases = searchAliases(exercise).map(canonicalizeSearchText);
  const modality = canonicalizeSearchText(exercise.modality ? labelFor(exercise.modality) : "");
  const laterality = canonicalizeSearchText(exercise.laterality ? labelFor(exercise.laterality) : "");
  const name = canonicalizeSearchText(exercise.name);
  const bodyFocus = canonicalizeSearchText(formatBodyFocus(exercise.bodyFocus));
  const movementFamily = canonicalizeSearchText(titleCase(exercise.movementFamily || "general"));
  const aliasTargets = [...new Set(
    aliases.flatMap(alias => (QUERY_ALIASES[alias] || []).map(canonicalizeSearchText))
  )];
  const allTerms = [...new Set([
    name,
    modality,
    laterality,
    bodyFocus,
    movementFamily,
    ...patterns,
    ...primaryJAs,
    ...supportingJAs,
    ...equipment,
    ...planes,
    ...styles,
    ...muscles,
    ...regions,
    ...aliases,
  ].filter(Boolean))];

  return {
    name,
    modality,
    laterality,
    bodyFocus,
    movementFamily,
    patterns,
    primaryJA: primaryJAs,
    supportingJA: supportingJAs,
    equipment,
    planes,
    styles,
    muscles,
    muscleEntries,
    regions,
    aliases,
    aliasTargets,
    all: allTerms.join(" | "),
  };
}

function getSearchIndex(exercise) {
  return state.searchIndex.get(exercise.id) || buildFallbackSearchIndex(exercise);
}

function searchAliases(exercise) {
  const aliases = new Set();
  const muscles = exercise.muscles || [];
  const labels = muscles.map(([muscle]) => canonicalizeSearchText(muscleLabel(muscle)));

  if (labels.some(label => label.includes("biceps brachii") || label.includes("brachialis"))) {
    aliases.add("bicep");
    aliases.add("biceps");
  }
  if (labels.some(label => label.includes("triceps"))) {
    aliases.add("tricep");
    aliases.add("triceps");
  }
  if (labels.some(label => label.includes("deltoid"))) {
    aliases.add("delt");
    aliases.add("delts");
    aliases.add("rear delt");
    aliases.add("rear delts");
    aliases.add("shoulder");
    aliases.add("shoulders");
  }
  if (labels.some(label => label.includes("vastus") || label.includes("rectus femoris"))) {
    aliases.add("quad");
    aliases.add("quads");
  }
  if (labels.some(label => label.includes("glute"))) {
    aliases.add("glute");
    aliases.add("glutes");
  }
  if (labels.some(label => label.includes("biceps femoris") || label.includes("semitendinosus") || label.includes("semimembranosus"))) {
    aliases.add("hamstring");
    aliases.add("hamstrings");
  }
  if (labels.some(label => label.includes("rectus abdominis") || label.includes("oblique") || label.includes("transverse abdominis"))) {
    aliases.add("abs");
  }
  return [...aliases];
}

function allMuscleNodes(nodes = state.vocab.muscles?.regions || []) {
  return nodes.flatMap(node => [node, ...allMuscleNodes(node.children || [])]);
}

function queryMatchedMuscleIds(query) {
  const q = canonicalizeSearchText(query);
  if (!q) return [];
  const candidates = new Set([q, ...(QUERY_ALIASES[q] || []).map(canonicalizeSearchText)]);
  return allMuscleNodes()
    .filter(node => {
      const label = canonicalizeSearchText(node.label);
      return [...candidates].some(candidate => label === candidate || label.includes(candidate) || candidate.includes(label));
    })
    .map(node => node.id);
}

function muscleMatchScore(exercise, targetMuscleIds = []) {
  if (!targetMuscleIds.length) return 0;
  let best = 0;
  for (const targetId of targetMuscleIds) {
    const allowed = state.muscleDescendants[targetId] || [targetId];
    for (const [muscle, degree] of exercise.muscles || []) {
      if (allowed.includes(muscle)) {
        best = Math.max(best, muscleDegreeWeight(degree));
      }
    }
  }
  return best;
}

function searchScore(exercise, query) {
  const q = canonicalizeSearchText(query);
  if (!q) return 0;

  const index = getSearchIndex(exercise);
  const {
    name,
    modality,
    laterality,
    patterns,
    primaryJA,
    supportingJA,
    equipment,
    muscles,
    muscleEntries,
    regions,
    aliases,
    aliasTargets,
    all,
  } = index;
  const queryAliasTargets = (QUERY_ALIASES[q] || []).map(canonicalizeSearchText);
  const matchedMuscleIds = queryMatchedMuscleIds(q);

  let score = 0;
  if (name === q) score = Math.max(score, 120);
  if (name.includes(q)) score = Math.max(score, 100);
  if (aliases.includes(q)) score = Math.max(score, 95);
  if (all.includes(q)) score = Math.max(score, 68);
  if ([name, modality, laterality, ...patterns, ...primaryJA, ...supportingJA, ...equipment, ...muscles, ...regions, ...aliases].some(field => field === q)) {
    score = Math.max(score, 90);
  }
  if (patterns.some(field => field.includes(q)) || primaryJA.some(field => field.includes(q)) || supportingJA.some(field => field.includes(q))) {
    score = Math.max(score, 80);
  }
  if (equipment.some(field => field.includes(q)) || modality.includes(q) || laterality.includes(q) || regions.some(field => field.includes(q))) {
    score = Math.max(score, 72);
  }
  if (muscles.some(field => field.includes(q))) score = Math.max(score, 60);

  if (matchedMuscleIds.length) {
    score += muscleMatchScore(exercise, matchedMuscleIds);
  } else if (queryAliasTargets.length && muscleEntries.some(entry => queryAliasTargets.some(target => entry.label.includes(target)))) {
    const bestDegree = muscleEntries
      .filter(entry => queryAliasTargets.some(target => entry.label.includes(target)))
      .reduce((best, entry) => Math.max(best, muscleDegreeWeight(entry.degree)), 0);
    score += bestDegree;
  }

  if (queryAliasTargets.length) {
    const aliasHit = aliasTargets.some(target => queryAliasTargets.includes(target))
      || [...muscles, ...regions, ...aliases, ...patterns].some(field => queryAliasTargets.some(target => field.includes(target)));
    if (aliasHit) score = Math.max(score, 92);
    else if (!name.includes(q) && !aliases.includes(q)) return 0;
  }

  return score;
}

function closeAllFilterPanels() {
  document.querySelectorAll(".filter-panel").forEach(panel => panel.classList.remove("open"));
  document.querySelectorAll(".filter-chip[data-panel]").forEach(chip => chip.classList.remove("active"));
}

function closeFilterPanelForType(type) {
  const panelForType = {
    patterns: "patterns",
    muscles: "muscles",
    modalities: "modalities",
    equipment: "equipment",
  };
  const panel = panelForType[type];
  if (!panel) return;
  el(`panel-${panel}`)?.classList.remove("open");
  document.querySelector(`.filter-chip[data-panel="${panel}"]`)?.classList.remove("active");
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

function sortByLabel(items = []) {
  return [...items].sort((a, b) => a.label.localeCompare(b.label));
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
  state.filters = createEmptyFilters();
  rerenderAll();
}

function clearBrowseFilters() {
  for (const key of BROWSE_FILTER_KEYS) {
    state.filters[key] = [];
  }
  rerenderAll();
}

function filterMatchesHierarchy(selected, descendantsMap, values) {
  if (!selected.length) return true;
  return selected.some(id => {
    const allowed = descendantsMap[id] || [id];
    return values.some(value => allowed.includes(value));
  });
}

function filteredExercises(baseExercises = state.exercises) {
  const q = state.search.trim().toLowerCase();
  const { muscles, patterns } = state.filters;
  const matches = [];

  for (const ex of baseExercises) {
    if (!filterMatchesHierarchy(patterns, state.patternDescendants, ex.patterns)) continue;
    if (!filterMatchesHierarchy(muscles, state.muscleDescendants, ex.muscles.map(m => m[0]))) continue;
    let blocked = false;
    for (const key of BROWSE_FILTER_KEYS) {
      if (key === "patterns") continue;
      const selected = state.filters[key];
      if (!selected.length) continue;
      const values = FILTER_VALUE_GETTERS[key](ex);
      if (!selected.some(id => values.includes(id))) {
        blocked = true;
        break;
      }
    }
    if (blocked) continue;

    const musclePriority = muscleMatchScore(ex, muscles);
    const score = q ? searchScore(ex, q) : 1;
    if (q && score <= 0) continue;
    matches.push({ ex, score, musclePriority });
  }

  if (!q) {
    return matches
      .sort((a, b) => b.musclePriority - a.musclePriority || a.ex.name.localeCompare(b.ex.name))
      .map(match => match.ex);
  }

  return matches
    .sort((a, b) => b.score - a.score || b.musclePriority - a.musclePriority || a.ex.name.localeCompare(b.ex.name))
    .map(match => match.ex);
}

function hasActiveFilters() {
  return Object.values(state.filters).some(values => values.length > 0);
}

function getExercise(id) {
  return state.exerciseMap.get(id) || null;
}

function getSubstituteUi(ex) {
  return state.substituteUi[ex.id] || {
    closestAlternatives: [],
    equipmentAlternatives: [],
    familyHighlights: [],
  };
}

function getSubstituteItems(items = [], limit = 8) {
  return items
    .map(item => ({ ...item, ex: getExercise(item.id) }))
    .filter(item => item.ex)
    .slice(0, limit);
}

function getSubstituteGroups(groups = []) {
  return groups
    .map(group => ({
      label: group.label,
      items: getSubstituteItems(group.items || [], 8),
    }))
    .filter(group => group.items.length);
}

function renderSubstituteList(items, emptyMessage) {
  if (!items.length) {
    return `<div style="font-size:13px;color:var(--text-2)">${emptyMessage}</div>`;
  }
  return items.map(item => {
    const metaParts = [];
    if (item.reason) metaParts.push(item.reason);
    if (item.fallback) metaParts.push("Filled from the closest available graph match.");
    const meta = metaParts.join(" ");
    return `
      <div class="sub-card">
        <div>
          <div>${item.ex.name}</div>
          ${meta ? `<div class="sub-why">${meta}</div>` : ""}
        </div>
        <button class="sub-view-btn" type="button" data-id="${item.ex.id}">View</button>
      </div>
    `;
  }).join("");
}

function renderFamilyHighlights(groups) {
  if (!groups.length) {
    return `<div style="font-size:13px;color:var(--text-2)">No broader family options available yet.</div>`;
  }
  return groups.map(group => `
    <div class="sub-family-group">
      <div class="sub-family-group-label">${group.label}</div>
      <div class="sub-list">${renderSubstituteList(group.items, "")}</div>
    </div>
  `).join("");
}


function syncUrlState() {
  const params = new URLSearchParams();
  if (state.theme !== DEFAULT_THEME) params.set("theme", state.theme);
  if (state.activeTab !== "exercises") params.set("tab", state.activeTab);
  if (state.search) params.set("q", state.search);
  if (state.sheetExercise) params.set("detail", state.sheetExercise);
  if (state.bodyView !== "front") params.set("body", state.bodyView);
  if (state.sheetMode === "builder") params.set("builderView", "1");

  for (const [type, ids] of Object.entries(state.filters)) {
    if (ids.length) params.set(type, ids.join(","));
  }

  const query = params.toString();
  const next = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState({}, "", next);
}

function restoreUrlState() {
  const params = new URLSearchParams(window.location.search);
  state.theme = normalizeTheme(params.get("theme") || getStoredTheme() || DEFAULT_THEME);
  state.activeTab = params.get("tab") || "exercises";
  state.search = params.get("q") || "";
  state.sheetExercise = params.get("detail") || null;
  state.bodyView = params.get("body") || "front";
  state.sheetMode = params.get("builderView") === "1" ? "builder" : "user";

  for (const type of Object.keys(state.filters)) {
    state.filters[type] = (params.get(type) || "").split(",").filter(Boolean);
  }
}


function renderActiveFilters() {
  const pills = [];
  for (const [type, ids] of Object.entries(state.filters)) {
    for (const id of ids) {
      pills.push(`
        <span class="active-filter-pill">
          ${type === "muscles" ? muscleLabel(id) : labelFor(id)}
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

function renderRegionMini(regions) {
  return regions.map(region => `<span class="mini-region mini-region-${region}">${REGION_DISPLAY[region] || titleCase(region)}</span>`).join("");
}

function renderExerciseCard(exercise) {
  const primaryJACount = exercise.primaryJA?.length || 0;
  const equipmentCount = exercise.equipment?.length || 0;
  const primaryJALine = primaryJACount
    ? `${pluralizeLabel("Primary joint action", "Primary joint actions", primaryJACount)}: ${exercise.primaryJA.map(labelFor).join(", ")}`
    : "";
  const equipmentLine = `${pluralizeLabel("Equipment", "Equipment", equipmentCount)}: ${exercise.equipment[0] ? exercise.equipment.map(labelFor).join(", ") : "Bodyweight"}`;
  const factLines = [primaryJALine, equipmentLine].filter(Boolean);

  return `
    <article class="exercise-card v2-card" data-id="${exercise.id}">
      <div class="card-header">
        <span class="card-name">${exercise.name}</span>
        <div class="card-badges">
          ${exercise.modality ? `<span class="badge badge-modality">${labelFor(exercise.modality)}</span>` : ""}
          ${exercise.laterality ? `<span class="badge badge-isolation">${labelFor(exercise.laterality)}</span>` : ""}
        </div>
      </div>
      <div class="card-visual">
        ${renderRegionMini(exercise.visualRegions)}
      </div>
      <ul class="card-facts">
        ${factLines.map(line => `<li class="card-fact-line">${line}</li>`).join("")}
      </ul>
      <div class="card-actions">
        <button class="card-btn card-btn-primary" type="button" data-details="${exercise.id}">Details</button>
      </div>
    </article>
  `;
}

function bindExerciseCards(root = document) {
  root.querySelectorAll("[data-details]").forEach(button => {
    button.addEventListener("click", event => {
      event.stopPropagation();
      openSheet(button.dataset.details);
    });
  });
  root.querySelectorAll(".exercise-card[data-id]").forEach(card => {
    card.addEventListener("click", () => openSheet(card.dataset.id));
  });
}

function renderExploreView() {
  const results = filteredExercises();
  el("result-count").textContent = `${formatCount(results.length)} exercise${results.length !== 1 ? "s" : ""}`;

  const list = el("exercise-list");
  if (!results.length) {
    list.innerHTML = `
      <div class="empty">
        <strong>No exercises match this mix of constraints.</strong><br>
        Try broadening the search or clearing a filter.
      </div>`;
    return;
  }

  const toRender = results.slice(0, 120);
  list.innerHTML = toRender.map(ex => renderExerciseCard(ex)).join("");
  if (results.length > 120) {
    list.innerHTML += `<div class="empty" style="padding:16px">Showing 120 of ${formatCount(results.length)}. Refine your search to see more.</div>`;
  }
  bindExerciseCards(list);
}



// ── Observatory (lazy load) ────────────────────────────────────────────────────

async function ensureObservatory() {
  if (state.observatoryData) return state.observatoryData;
  if (!state.observatoryLoadPromise) {
    state.observatoryLoadPromise = loadJson("observatory.json")
      .then(data => { state.observatoryData = data; return data; })
      .catch(() => { state.observatoryData = []; return []; });
  }
  return state.observatoryLoadPromise;
}

function getObservatoryEntry(exerciseId) {
  if (!state.observatoryData) return null;
  return state.observatoryData.find(e => e.entity_id === exerciseId) || null;
}

// ── Sheet rendering ────────────────────────────────────────────────────────────

function renderSheetUser(ex) {
  const badges = [];
  if (ex.modality) badges.push(`<span class="badge badge-modality">${labelFor(ex.modality)}</span>`);
  if (ex.combination) badges.push(`<span class="badge badge-combo">Combination</span>`);
  if (ex.laterality) badges.push(`<span class="badge badge-isolation">${labelFor(ex.laterality)}</span>`);

  const musclesByDegree = {};
  for (const [muscle, degree] of ex.muscles) {
    (musclesByDegree[degree] = musclesByDegree[degree] || []).push(muscle);
  }
  const muscleGroupsHtml = DEGREE_ORDER
    .filter(degree => musclesByDegree[degree]?.length)
    .map(degree => {
      const cls = DEGREE_CLASS[degree];
      return `
        <div class="muscle-degree-group">
          <div class="muscle-degree-heading">
            <span class="legend-dot deg-${cls}"></span>
            ${DEGREE_LABEL[degree]}
          </div>
          <div class="tag-list">
            ${musclesByDegree[degree].map(muscle => `<span class="tag muscle-tag">${muscleLabel(muscle)}</span>`).join("")}
          </div>
        </div>
      `;
    }).join("");

  const substituteUi = getSubstituteUi(ex);
  const closestAlternatives = getSubstituteItems(substituteUi.closestAlternatives || [], 4);
  const equipmentAlternatives = getSubstituteItems(substituteUi.equipmentAlternatives || [], 4);
  const familyHighlights = getSubstituteGroups(substituteUi.familyHighlights || []);

  return `
    ${badges.length ? `<div class="sheet-badges">${badges.join("")}</div>` : ""}

    <div class="section-label">Body Emphasis</div>
    <div class="mini-region-row">${renderRegionMini(ex.visualRegions)}</div>

    <div class="section-label">Movement Patterns</div>
    <div class="tag-list">${ex.patterns.map(pattern => `<span class="tag tag-primary">${labelFor(pattern)}</span>`).join("") || '<span class="tag">None</span>'}</div>

    <div class="section-label">Muscles</div>
    <div class="muscle-degree-groups">${muscleGroupsHtml || '<span style="font-size:13px;color:var(--text-2)">No data</span>'}</div>

    ${ex.primaryJA.length ? `<div class="section-label">Primary Joint Actions</div><div class="tag-list">${ex.primaryJA.map(ja => `<span class="tag tag-primary">${labelFor(ja)}</span>`).join("")}</div>` : ""}
    ${ex.supportingJA.length ? `<div class="section-label">Supporting Joint Actions</div><div class="tag-list">${ex.supportingJA.map(ja => `<span class="tag">${labelFor(ja)}</span>`).join("")}</div>` : ""}

    <div class="section-label">Equipment</div>
    <div class="tag-list">${ex.equipment.map(eq => `<span class="tag">${labelFor(eq)}</span>`).join("") || '<span class="tag">Bodyweight</span>'}</div>

    <div class="section-label">Substitutes</div>
    <div class="sub-section-label">Closest Alternatives</div>
    <div class="sub-list">${renderSubstituteList(closestAlternatives, "No strong direct replacements available yet.")}</div>

    ${equipmentAlternatives.length ? `
      <div class="sub-section-label">Different Equipment</div>
      <div class="sub-list">${renderSubstituteList(equipmentAlternatives, "")}</div>
    ` : ""}

    <details class="sub-family-details">
      <summary>
        <span class="sub-family-summary-copy">
          <span>Explore This Family</span>
          <span class="sub-family-summary-hint">Tap to expand</span>
        </span>
        <span class="sub-family-summary-icon" aria-hidden="true">▾</span>
      </summary>
      <div class="sub-family-content">${renderFamilyHighlights(familyHighlights)}</div>
    </details>
  `;
}

const _STAGE_NAMES = ["Sources", "Identity", "Reconcile", "Enrich", "Graph"];

function renderBuilderStage(entry, stepIndex) {
  const stages = entry.stages;

  if (stepIndex === 0) {
    // Sources
    const records = stages.sources;
    const rows = records.map(rec => {
      const claimRows = rec.claims.map(c =>
        `<div class="obs-claim-row"><span class="obs-claim-pred">${escapeHtml(c.predicate)}</span><span class="obs-claim-val">${escapeHtml(c.value)}</span></div>`
      ).join("");
      return `
        <div class="obs-source-record">
          <div class="obs-source-header">
            <span class="obs-source-name">${escapeHtml(rec.display_name)}</span>
            <span class="obs-source-tag">${escapeHtml(rec.source)}</span>
          </div>
          ${claimRows || '<div class="obs-empty">No structured claims</div>'}
        </div>
      `;
    }).join("");
    return `
      <div class="obs-stage-intro">${records.length} source record${records.length !== 1 ? "s" : ""} contributed to this entity.</div>
      ${rows}
    `;
  }

  if (stepIndex === 1) {
    // Identity
    const id = stages.identity;
    const crossLabel = id.cross_source
      ? `<span class="obs-badge obs-badge-cross">Cross-source merge</span>`
      : `<span class="obs-badge obs-badge-single">Single source</span>`;
    const sourceTags = id.sources.map(s => `<span class="obs-source-tag">${escapeHtml(s)}</span>`).join(" ");
    const matchRows = id.possible_matches.length
      ? id.possible_matches.map(m => `
          <div class="obs-claim-row">
            <span class="obs-claim-pred">${escapeHtml(m.display_name)}</span>
            <span class="obs-claim-val">score ${escapeHtml(String(m.score))} · ${escapeHtml(m.status)}</span>
          </div>`).join("")
      : `<div class="obs-empty">No ambiguous candidates</div>`;
    return `
      <div class="obs-stage-intro">${id.record_count} record${id.record_count !== 1 ? "s" : ""} resolved into one canonical entity. ${crossLabel}</div>
      <div class="obs-row-group"><div class="obs-group-label">Sources</div><div>${sourceTags}</div></div>
      <div class="obs-row-group"><div class="obs-group-label">Possible matches considered</div>${matchRows}</div>
    `;
  }

  if (stepIndex === 2) {
    // Reconcile
    const rec = stages.reconcile;
    const methodRows = Object.entries(rec.by_method).map(([method, claims]) => {
      const claimRows = claims.map(c =>
        `<div class="obs-claim-row"><span class="obs-claim-pred">${escapeHtml(c.predicate)}</span><span class="obs-claim-val">${escapeHtml(c.value)}</span></div>`
      ).join("");
      const methodClass = method === "Human override" ? "obs-badge-override"
        : method === "Coverage gap" ? "obs-badge-gap"
        : method === "Consensus" ? "obs-badge-consensus" : "obs-badge-union";
      return `
        <div class="obs-row-group">
          <div class="obs-group-label"><span class="obs-badge ${methodClass}">${escapeHtml(method)}</span> · ${claims.length} claim${claims.length !== 1 ? "s" : ""}</div>
          ${claimRows}
        </div>
      `;
    }).join("");

    const conflictRows = rec.conflicts.length
      ? rec.conflicts.map(c => `
          <div class="obs-conflict">
            <span class="obs-conflict-pred">${escapeHtml(c.predicate)}</span>
            <span class="obs-conflict-desc">${escapeHtml(c.description)}</span>
            <span class="obs-badge obs-badge-deferred">${escapeHtml(c.status)}</span>
          </div>`).join("")
      : `<div class="obs-empty">No conflicts</div>`;

    return `
      <div class="obs-stage-intro">Deterministic resolution algebra — no LLM. ${Object.values(rec.method_counts).reduce((a, b) => a + b, 0)} total claims resolved.</div>
      ${methodRows}
      <div class="obs-row-group"><div class="obs-group-label">Conflicts</div>${conflictRows}</div>
    `;
  }

  if (stepIndex === 3) {
    // Enrich
    const enr = stages.enrich;
    const notableRows = enr.notable.map(c =>
      `<div class="obs-claim-row"><span class="obs-claim-pred">${escapeHtml(c.predicate)}</span><span class="obs-claim-val">${escapeHtml(c.value)}</span></div>`
    ).join("");
    const warnRows = enr.warnings.length
      ? enr.warnings.map(w =>
          `<div class="obs-claim-row obs-warn-row"><span class="obs-claim-pred">${escapeHtml(w.predicate)}</span><span class="obs-claim-val">${escapeHtml(w.stripped_value)} (stripped)</span></div>`
        ).join("")
      : `<div class="obs-empty">No warnings</div>`;
    return `
      <div class="obs-stage-intro">Single LLM pass. ${enr.inferred_count} claims inferred. Inferred claims never overwrite source-asserted facts.</div>
      <div class="obs-row-group">
        <div class="obs-group-label">Model · date</div>
        <div class="obs-claim-row"><span class="obs-claim-pred">Model</span><span class="obs-claim-val">${escapeHtml(enr.model || "—")}</span></div>
        <div class="obs-claim-row"><span class="obs-claim-pred">Enriched</span><span class="obs-claim-val">${escapeHtml(enr.enriched_at || "—")}</span></div>
      </div>
      <div class="obs-row-group"><div class="obs-group-label">Notable additions (not in resolved claims)</div>${notableRows || '<div class="obs-empty">All inferences duplicated resolved claims</div>'}</div>
      <div class="obs-row-group"><div class="obs-group-label">Stripped (unknown vocab at enrichment time)</div>${warnRows}</div>
    `;
  }

  if (stepIndex === 4) {
    // Graph — show final resolved state from user view summary
    return `
      <div class="obs-stage-intro">RDF assembled from resolved + inferred claims. Asserted always takes precedence.</div>
      <div class="obs-empty obs-graph-note">Switch back to User View to see the final assembled record.</div>
    `;
  }

  return "";
}

function renderSheetBuilder(ex, entry) {
  const step = state.sheetBuilderStep;
  const stageName = _STAGE_NAMES[step];
  const stageContent = renderBuilderStage(entry, step);

  const stepIndicators = _STAGE_NAMES.map((name, i) => `
    <button class="obs-step-dot ${i === step ? "active" : ""}" data-step="${i}" title="${escapeHtml(name)}"></button>
  `).join("");

  return `
    <div class="obs-narrative">${escapeHtml(entry.narrative)}</div>

    <div class="obs-stepper">
      <div class="obs-stepper-header">
        <button class="obs-nav-btn" id="obs-prev" ${step === 0 ? "disabled" : ""}>←</button>
        <div class="obs-stepper-center">
          <div class="obs-stage-label">Stage ${step + 1} of ${_STAGE_NAMES.length} · ${escapeHtml(stageName)}</div>
          <div class="obs-step-dots">${stepIndicators}</div>
        </div>
        <button class="obs-nav-btn" id="obs-next" ${step === _STAGE_NAMES.length - 1 ? "disabled" : ""}>→</button>
      </div>
      <div class="obs-stage-content" id="obs-stage-content">
        ${stageContent}
      </div>
    </div>
  `;
}

function bindBuilderNav() {
  const prev = el("obs-prev");
  const next = el("obs-next");
  if (prev) prev.addEventListener("click", e => { e.stopPropagation(); navigateBuilderStep(-1); });
  if (next) next.addEventListener("click", e => { e.stopPropagation(); navigateBuilderStep(1); });
  el("sheet-content").querySelectorAll(".obs-step-dot[data-step]").forEach(dot => {
    dot.addEventListener("click", e => {
      e.stopPropagation();
      state.sheetBuilderStep = parseInt(dot.dataset.step, 10);
      rerenderSheetBuilderOnly();
    });
  });
}

function navigateBuilderStep(delta) {
  const next = state.sheetBuilderStep + delta;
  if (next < 0 || next >= _STAGE_NAMES.length) return;
  state.sheetBuilderStep = next;
  rerenderSheetBuilderOnly();
}

function rerenderSheetBuilderOnly() {
  const entry = getObservatoryEntry(state.sheetExercise);
  if (!entry) return;
  const ex = getExercise(state.sheetExercise);
  if (!ex) return;
  const content = el("sheet-content");
  // Only replace the stepper area (after the toggle and title)
  const stepper = content.querySelector(".obs-stepper");
  const narrative = content.querySelector(".obs-narrative");
  const step = state.sheetBuilderStep;
  const stageName = _STAGE_NAMES[step];
  const stageContent = renderBuilderStage(entry, step);
  const stepIndicators = _STAGE_NAMES.map((name, i) => `
    <button class="obs-step-dot ${i === step ? "active" : ""}" data-step="${i}" title="${escapeHtml(name)}"></button>
  `).join("");

  if (stepper) {
    stepper.innerHTML = `
      <div class="obs-stepper-header">
        <button class="obs-nav-btn" id="obs-prev" ${step === 0 ? "disabled" : ""}>←</button>
        <div class="obs-stepper-center">
          <div class="obs-stage-label">Stage ${step + 1} of ${_STAGE_NAMES.length} · ${escapeHtml(stageName)}</div>
          <div class="obs-step-dots">${stepIndicators}</div>
        </div>
        <button class="obs-nav-btn" id="obs-next" ${step === _STAGE_NAMES.length - 1 ? "disabled" : ""}>→</button>
      </div>
      <div class="obs-stage-content" id="obs-stage-content">
        ${stageContent}
      </div>
    `;
  }
  bindBuilderNav();
}

function renderSheetToggle(hasObservatory) {
  if (!hasObservatory) return "";
  const isBuilder = state.sheetMode === "builder";
  return `
    <div class="sheet-mode-toggle">
      <button class="sheet-mode-btn ${!isBuilder ? "active" : ""}" id="sheet-mode-user">User View</button>
      <button class="sheet-mode-btn ${isBuilder ? "active" : ""}" id="sheet-mode-builder">Builder View</button>
    </div>
  `;
}

function bindSheetToggle(ex) {
  const userBtn = el("sheet-mode-user");
  const builderBtn = el("sheet-mode-builder");
  if (!userBtn || !builderBtn) return;

  userBtn.addEventListener("click", e => {
    e.stopPropagation();
    if (state.sheetMode === "user") return;
    state.sheetMode = "user";
    syncUrlState();
    openSheet(state.sheetExercise);
  });

  builderBtn.addEventListener("click", async e => {
    e.stopPropagation();
    if (state.sheetMode === "builder") return;
    builderBtn.textContent = "Loading…";
    builderBtn.disabled = true;
    await ensureObservatory();
    state.sheetMode = "builder";
    state.sheetBuilderStep = 0;
    syncUrlState();
    openSheet(state.sheetExercise);
  });
}

function openSheet(exerciseId) {
  const ex = getExercise(exerciseId);
  if (!ex) return;
  state.sheetExercise = exerciseId;
  syncUrlState();

  const entry = getObservatoryEntry(exerciseId);
  const hasObservatory = !!entry;
  const isBuilder = state.sheetMode === "builder" && hasObservatory;

  const bodyHtml = isBuilder
    ? renderSheetBuilder(ex, entry)
    : renderSheetUser(ex);

  el("sheet-content").innerHTML = `
    <div class="sheet-title">${ex.name}</div>
    <div class="sheet-subtitle">${graphGroundingLine(ex) || "Structured exercise record."}</div>
    ${renderSheetToggle(hasObservatory)}
    ${bodyHtml}
  `;

  el("sheet-overlay").classList.add("open");
  el("detail-sheet").classList.toggle("builder-open", isBuilder);
  document.body.style.overflow = "hidden";

  bindSheetToggle(ex);

  if (isBuilder) {
    bindBuilderNav();
  } else {
    el("sheet-content").querySelectorAll(".sub-view-btn").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        el("detail-sheet").scrollTop = 0;
        openSheet(button.dataset.id);
      });
    });
  }

  // Pre-warm observatory fetch; once loaded inject toggle if not already visible
  if (!state.observatoryData) {
    ensureObservatory().then(() => {
      const stillOpen = state.sheetExercise === exerciseId && el("sheet-overlay").classList.contains("open");
      if (stillOpen && !hasObservatory && getObservatoryEntry(exerciseId)) {
        const toggleSlot = el("sheet-content").querySelector(".sheet-mode-toggle");
        if (!toggleSlot) {
          const subtitle = el("sheet-content").querySelector(".sheet-subtitle");
          if (subtitle) {
            const div = document.createElement("div");
            div.innerHTML = renderSheetToggle(true);
            subtitle.insertAdjacentElement("afterend", div.firstElementChild);
            bindSheetToggle(ex);
          }
        }
      }
    });
  }
}

window.app = window.app || {};
app.closeSheet = function(e) {
  if (e.target === el("sheet-overlay")) {
    el("sheet-overlay").classList.remove("open");
    el("detail-sheet").classList.remove("builder-open");
    document.body.style.overflow = "";
    state.sheetExercise = null;
    state.sheetMode = "user";
    syncUrlState();
  }
};

app.setBodyView = function(view) {
  state.bodyView = view;
  el("anatomy-front").style.display = view === "front" ? "" : "none";
  el("anatomy-back").style.display = view === "back" ? "" : "none";
  el("btn-front").classList.toggle("active", view === "front");
  el("btn-back").classList.toggle("active", view === "back");
  syncUrlState();
};

app.setTheme = function(theme) {
  applyTheme(theme);
};

function renderPatternTags() {
  el("pattern-tags").innerHTML = (state.vocab.patterns || []).map(pattern => {
    const active = state.filters.patterns.includes(pattern.id);
    return `
      <span class="filter-tag ${active ? "active" : ""}" data-type="patterns" data-id="${pattern.id}" style="padding-left:${10 + pattern.depth * 14}px">
        ${pattern.label} <span style="opacity:.6;font-size:11px">${formatCount(pattern.count)}</span>
      </span>
    `;
  }).join("");
}

function renderMuscleFilterTree(nodes, depth = 0) {
  return sortByLabel(nodes).map(node => {
    const active = state.filters.muscles.includes(node.id);
    return `
      <div>
        <button class="hierarchy-node ${active ? "active" : ""}" data-type="muscles" data-id="${node.id}" style="margin-left:${depth * 16}px">
          <span class="hierarchy-node-main">
            <span>${node.label}</span>
            <span class="hierarchy-node-kind">${node.type}</span>
          </span>
          <span class="vocab-item-count">${formatCount(node.count)}</span>
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
        ${modality.label} <span style="opacity:.6;font-size:11px">${formatCount(modality.count)}</span>
      </span>
    `;
  }).join("");

  el("equipment-tags").innerHTML = (state.vocab.equipment || []).map(equipment => {
    const active = state.filters.equipment.includes(equipment.id);
    return `
      <span class="filter-tag ${active ? "active" : ""}" data-type="equipment" data-id="${equipment.id}">
        ${equipment.label} <span style="opacity:.6;font-size:11px">${formatCount(equipment.count)}</span>
      </span>
    `;
  }).join("");

  document.querySelectorAll(".filter-tag[data-type], .hierarchy-node[data-type]").forEach(node => {
    node.addEventListener("click", () => {
      toggleFilter(node.dataset.type, node.dataset.id);
      closeFilterPanelForType(node.dataset.type);
    });
  });
}

function findTopMuscleRegionId(muscleId) {
  for (const region of state.vocab.muscles?.regions || []) {
    const descendants = state.muscleDescendants[region.id] || [region.id];
    if (descendants.includes(muscleId)) return region.id;
  }
  return null;
}

function setMuscleSectionOpen(regionId, open) {
  state.muscleOpenSections[regionId] = open;
}

function renderMuscleSection(nodes, depth = 0) {
  return sortByLabel(nodes).map(node => {
    const active = state.filters.muscles.includes(node.id);
    return `
      <div class="muscle-group-row ${active ? "active" : ""}" data-muscle="${node.id}" style="margin-left:${depth * 16}px">
        <span>${node.label}</span>
        <span class="muscle-count">${formatCount(node.count)} exercises</span>
      </div>
      ${node.children?.length ? renderMuscleSection(node.children, depth + 1) : ""}
    `;
  }).join("");
}

function renderMuscleList() {
  const regions = sortByLabel(state.vocab.muscles?.regions || []);
  el("muscle-list").innerHTML = regions.map(region => {
    const open = !!state.muscleOpenSections[region.id];
    return `
      <div class="vocab-section">
        <div class="vocab-section-header ${open ? "open" : ""}" data-muscle-section="${region.id}" id="muscle-section-header-${region.id}">
          <span class="muscle-header-label">${region.label}</span>
          <span class="vocab-item-count muscle-header-count">${formatCount(region.count)}</span>
          <span class="vocab-chevron">▼</span>
        </div>
        <div class="vocab-items ${open ? "open" : ""}" id="muscle-section-${region.id}">
          ${renderMuscleSection(region.children || [])}
        </div>
      </div>
    `;
  }).join("");

  el("muscle-list").querySelectorAll(".muscle-group-row").forEach(row => {
    row.addEventListener("click", () => toggleFilter("muscles", row.dataset.muscle));
  });

  el("muscle-list").querySelectorAll("[data-muscle-section]").forEach(header => {
    header.addEventListener("click", event => {
      if (event.target.closest(".muscle-group-row")) return;
      const section = el(`muscle-section-${header.dataset.muscleSection}`);
      const open = !section.classList.contains("open");
      section.classList.toggle("open", open);
      header.classList.toggle("open", open);
      setMuscleSectionOpen(header.dataset.muscleSection, open);
    });
  });

  if (state.pendingMuscleScrollTo) {
    const target = el(`muscle-section-header-${state.pendingMuscleScrollTo}`);
    state.pendingMuscleScrollTo = null;
    if (target) {
      window.requestAnimationFrame(() => {
        target.scrollIntoView({ block: "start", behavior: "instant" });
      });
    }
  }
}

function renderMuscleActiveFilters() {
  const container = el("muscle-active-filters");
  if (!container) return;
  const muscles = state.filters.muscles;
  if (!muscles.length) {
    container.innerHTML = "";
    container.style.display = "none";
    return;
  }
  container.style.display = "flex";
  container.innerHTML = muscles.map(id => `
    <span class="active-filter-pill">
      ${muscleLabel(id)}
      <button type="button" data-remove-muscle="${id}" aria-label="Remove ${muscleLabel(id)}">✕</button>
    </span>
  `).join("");
  container.querySelectorAll("[data-remove-muscle]").forEach(button => {
    button.addEventListener("click", () => {
      state.filters.muscles = state.filters.muscles.filter(m => m !== button.dataset.removeMuscle);
      rerenderAll();
    });
  });
}

function renderMuscleResults() {
  renderMuscleActiveFilters();
  const results = filteredExercises();
  const countLabel = state.filters.muscles.length
    ? `${formatCount(results.length)} exercise${results.length !== 1 ? "s" : ""} match the current muscle filters`
    : `${formatCount(results.length)} exercise${results.length !== 1 ? "s" : ""} available`;

  el("muscle-result-count").textContent = countLabel;

  const list = el("muscle-exercise-list");
  if (!results.length) {
    list.innerHTML = `
      <div class="empty">
        <strong>No exercises match this muscle selection.</strong><br>
        Try another region or clear the muscle filters.
      </div>`;
    return;
  }

  const toRender = results.slice(0, 36);
  list.innerHTML = toRender.map(ex => renderExerciseCard(ex)).join("");
  if (results.length > 36) {
    list.innerHTML += `<div class="empty" style="padding:16px">Showing 36 of ${formatCount(results.length)}. Add more filters to narrow the list.</div>`;
  }
  bindExerciseCards(list);
}

function renderBrowseResults() {
  const results = filteredExercises();
  const hasBrowseFilters = BROWSE_FILTER_KEYS.some(key => state.filters[key].length > 0);

  const countLabel = hasBrowseFilters
    ? `${formatCount(results.length)} exercise${results.length !== 1 ? "s" : ""} match the current concept filters`
    : `${formatCount(results.length)} exercise${results.length !== 1 ? "s" : ""} available`;

  el("browse-result-count").textContent = countLabel;

  const list = el("browse-exercise-list");
  if (!hasBrowseFilters) {
    const toRender = results.slice(0, 36);
    list.innerHTML = toRender.map(ex => renderExerciseCard(ex)).join("");
    if (results.length > 36) {
      list.innerHTML += `<div class="empty" style="padding:16px">Showing 36 of ${formatCount(results.length)}. Add more filters to narrow the list.</div>`;
    }
    bindExerciseCards(list);
    return;
  }

  if (!results.length) {
    list.innerHTML = `
      <div class="empty">
        <strong>No exercises match this concept selection.</strong><br>
        Try another concept or remove one of the active Browse filters.
      </div>`;
    return;
  }

  const toRender = results.slice(0, 36);
  list.innerHTML = toRender.map(ex => renderExerciseCard(ex)).join("");
  if (results.length > 36) {
    list.innerHTML += `<div class="empty" style="padding:16px">Showing 36 of ${formatCount(results.length)}. Add more filters to narrow the list.</div>`;
  }
  bindExerciseCards(list);
}

function renderVocab() {
  el("vocab-modalities").innerHTML = (state.vocab.modalities || []).map(modality => {
    const active = state.filters.modalities.includes(modality.id);
    return `
      <div class="vocab-item ${active ? "active" : ""}" data-type="modalities" data-id="${modality.id}">
        <span class="vocab-item-main">
          <strong>${modality.label}</strong>
          ${modality.description ? `<small>${modality.description}</small>` : ""}
        </span>
        <span class="vocab-item-count">${formatCount(modality.count)}</span>
      </div>
    `;
  }).join("");

  el("vocab-patterns").innerHTML = (state.vocab.patterns || []).map(pattern => {
    const active = state.filters.patterns.includes(pattern.id);
    return `
      <div class="vocab-item ${active ? "active" : ""} indent-${Math.min(pattern.depth, 3)}" data-type="patterns" data-id="${pattern.id}">
        <span class="vocab-item-main">
          <strong>${pattern.label}</strong>
          ${pattern.description ? `<small>${pattern.description}</small>` : ""}
        </span>
        <span class="vocab-item-count">${formatCount(pattern.count)}</span>
      </div>
    `;
  }).join("");

  el("vocab-joints").innerHTML = (state.vocab.joints || []).flatMap(joint =>
    (joint.actions || []).map(action => {
      const active = state.filters.joints.includes(action.id);
      return `
        <div class="vocab-item ${active ? "active" : ""} indent-1" data-type="joints" data-id="${action.id}">
          <span>${action.label} <span style="color:var(--text-2);font-size:12px">${joint.label}</span></span>
          <span class="vocab-item-count">${formatCount(action.count)}</span>
        </div>
      `;
    })
  ).join("");

  el("vocab-equipment").innerHTML = (state.vocab.equipment || []).map(equipment => {
    const active = state.filters.equipment.includes(equipment.id);
    return `
      <div class="vocab-item ${active ? "active" : ""}" data-type="equipment" data-id="${equipment.id}">
        <span>${equipment.label}</span>
        <span class="vocab-item-count">${formatCount(equipment.count)}</span>
      </div>
    `;
  }).join("");

  el("vocab-laterality").innerHTML = (state.vocab.laterality || []).map(item => {
    const active = state.filters.laterality.includes(item.id);
    return `
      <div class="vocab-item ${active ? "active" : ""}" data-type="laterality" data-id="${item.id}">
        <span>${item.label}</span>
        <span class="vocab-item-count">${formatCount(item.count)}</span>
      </div>
    `;
  }).join("");

  el("vocab-planes").innerHTML = (state.vocab.planes || []).map(item => {
    const active = state.filters.planes.includes(item.id);
    return `
      <div class="vocab-item ${active ? "active" : ""}" data-type="planes" data-id="${item.id}">
        <span>${item.label}</span>
        <span class="vocab-item-count">${formatCount(item.count)}</span>
      </div>
    `;
  }).join("");

  el("vocab-styles").innerHTML = (state.vocab.styles || []).map(item => {
    const active = state.filters.styles.includes(item.id);
    return `
      <div class="vocab-item ${active ? "active" : ""}" data-type="styles" data-id="${item.id}">
        <span>${item.label}</span>
        <span class="vocab-item-count">${formatCount(item.count)}</span>
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
  window.scrollTo({ top: 0, behavior: "instant" });
  if (tab === "muscles") renderMuscleList();
  if (tab === "vocab") renderVocab();
  syncUrlState();
}


function initFilterChips() {
  document.querySelectorAll(".filter-chip[data-panel]").forEach(chip => {
    chip.addEventListener("click", () => {
      const panel = el(`panel-${chip.dataset.panel}`);
      const isOpen = !panel.classList.contains("open");
      closeAllFilterPanels();
      panel.classList.toggle("open", isOpen);
      chip.classList.toggle("active", isOpen);
      if (isOpen) renderFilterPanels();
    });
  });

  el("clear-filters").addEventListener("click", () => clearFilters());
}

function updateClearBtn() {
  el("clear-filters").style.display = hasActiveFilters() ? "" : "none";
}

function updateMuscleClearBtn() {
  const button = el("clear-muscle-filters");
  if (!button) return;
  const hasMuscleFilters = state.filters.muscles.length > 0;
  button.disabled = !hasMuscleFilters;
  button.classList.toggle("disabled", !hasMuscleFilters);
}

function updateBrowseClearBtn() {
  const button = el("clear-browse-filters");
  if (!button) return;
  const hasBrowseFilters = BROWSE_FILTER_KEYS.some(key => state.filters[key].length > 0);
  button.disabled = !hasBrowseFilters;
  button.classList.toggle("disabled", !hasBrowseFilters);
}

function highlightAnatomy() {
  const hasMuscleSelection = state.filters.muscles.length > 0;
  document.querySelectorAll(".muscle-region").forEach(region => {
    const regionMuscles = region.dataset.muscles.split(",");
    const matched = regionMuscles.some(muscle => filterMatchesHierarchy(state.filters.muscles, state.muscleDescendants, [muscle]));
    region.classList.toggle("highlighted", matched);
    region.classList.toggle("muted", hasMuscleSelection && !matched);
  });
}

function initAnatomyMap() {
  document.querySelectorAll(".muscle-region").forEach(region => {
    region.addEventListener("click", () => {
      const muscles = region.dataset.muscles.split(",");
      const allActive = muscles.every(muscle => state.filters.muscles.includes(muscle));
      const targetRegions = [...new Set(muscles.map(findTopMuscleRegionId).filter(Boolean))];
      targetRegions.forEach(regionId => setMuscleSectionOpen(regionId, true));
      state.pendingMuscleScrollTo = targetRegions[0] || null;
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
    if (searchDebounceTimer) window.clearTimeout(searchDebounceTimer);
    searchDebounceTimer = window.setTimeout(() => {
      rerenderForSearch();
    }, 120);
  });
}

function initNav() {
  document.querySelectorAll(".nav-btn[data-tab]").forEach(button => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
}

function initThemeDock() {
  const dock = el("theme-dock");
  const toggle = el("theme-toggle");
  const menu = el("theme-menu");
  if (!dock || !toggle || !menu) return;

  if (Object.keys(THEMES).length <= 1) {
    dock.hidden = true;
    applyTheme(state.theme, { persist: false, sync: false });
    return;
  }

  renderThemeMenu();
  applyTheme(state.theme, { persist: false, sync: false });
  setThemeMenuOpen(false);

  toggle.addEventListener("click", event => {
    event.stopPropagation();
    setThemeMenuOpen(menu.hidden);
  });

  menu.addEventListener("click", event => {
    const button = event.target.closest(".theme-option[data-theme]");
    if (!button) return;
    applyTheme(button.dataset.theme);
    setThemeMenuOpen(false);
  });

  document.addEventListener("click", event => {
    if (!dock.contains(event.target)) setThemeMenuOpen(false);
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") setThemeMenuOpen(false);
  });
}


function initCopyLink() {
  const button = el("copy-link-btn");
  if (!button) return;
  button.addEventListener("click", copyCurrentUrl(button, "Copy current view"));
}

// Lightweight re-render for search: only touches exercise lists, not
// filter panels / muscle hierarchy / vocab / anatomy — those don't change
// with search text and are the expensive part of a full rerenderAll.
function rerenderForSearch() {
  renderExploreView();
  renderMuscleResults();
  renderBrowseResults();
  syncUrlState();
}

function rerenderAll() {
  updateClearBtn();
  updateMuscleClearBtn();
  updateBrowseClearBtn();
  renderFilterPanels();
  renderActiveFilters();
  renderExploreView();
  renderMuscleList();
  renderMuscleResults();
  renderVocab();
  renderBrowseResults();
  highlightAnatomy();
  app.setBodyView(state.bodyView);
  if (state.sheetExercise && getExercise(state.sheetExercise)) {
    openSheet(state.sheetExercise);
  }
  syncUrlState();
}

function initBuilderKeyboard() {
  document.addEventListener("keydown", e => {
    if (state.sheetMode !== "builder" || !state.sheetExercise) return;
    if (e.key === "ArrowLeft") navigateBuilderStep(-1);
    if (e.key === "ArrowRight") navigateBuilderStep(1);
  });
}

function init() {
  initThemeDock();
  initNav();
  initSearch();
  initFilterChips();
  initAnatomyMap();
  initVocabAccordions();
  initCopyLink();
  initBuilderKeyboard();
  el("clear-muscle-filters")?.addEventListener("click", () => {
    if (!state.filters.muscles.length) return;
    state.filters.muscles = [];
    rerenderAll();
  });
  el("clear-browse-filters")?.addEventListener("click", () => {
    const hasBrowseFilters = BROWSE_FILTER_KEYS.some(key => state.filters[key].length > 0);
    if (!hasBrowseFilters) return;
    clearBrowseFilters();
  });
  el("search-input").value = state.search;
  switchTab(state.activeTab);
  rerenderAll();
}

async function loadData() {
  try {
    const [stateExercises, stateVocab, substituteUi] = await Promise.all([
      loadJson("data.json"),
      loadJson("vocab.json"),
      loadJson("exercise_substitute_ui.json").catch(() => ({})),
    ]);
    if (!Array.isArray(stateExercises)) {
      throw new Error("data.json did not return an exercise array");
    }
    if (!stateVocab || typeof stateVocab !== "object") {
      throw new Error("vocab.json did not return an object");
    }
    state.exercises = stateExercises;
    state.exerciseMap = new Map(stateExercises.map(ex => [ex.id, ex]));
    state.searchIndex = new Map(stateExercises.map(ex => [ex.id, ex.searchIndex || buildFallbackSearchIndex(ex)]));
    state.vocab = stateVocab;
    state.substituteUi = substituteUi && typeof substituteUi === "object" ? substituteUi : {};
    buildHierarchyMaps();
    restoreUrlState();
    await loadIllustrations();
    init();
  } catch (err) {
    console.error(err);
    renderFatalError(err);
  }
}

loadData();
