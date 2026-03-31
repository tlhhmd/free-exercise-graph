# DESIGN.md — free-exercise-graph app

Design reference for `app/style.css`. Captures the implicit system so future
contributors don't have to reverse-engineer it from the CSS.

---

## Personality

The app is a reference book for explorers, not a workout tracker. The visual
identity is warm editorial paper laid over saturated, tab-specific backgrounds.
Think: a well-designed atlas, not a fitness dashboard.

Three decisions make this work:

1. **Colored backgrounds carry meaning.** Blue = exercises, orange = muscles,
   yellow = vocab. These aren't decoration — they orient the user by tab.
2. **Glass surfaces, not flat cards.** Content sits on translucent paper-like
   surfaces over the colored background. This keeps the tab color visible and
   alive beneath the content.
3. **League Gothic as the structural voice.** Navigation, headings, and labels
   use League Gothic — condensed, uppercase, direct. All three tab headers now
   share the same voice and layout system.

---

## Color System

All color values live as CSS custom properties in `:root` and are overridden
per tab via `body[data-tab="..."]` selectors.

### Tab palettes

| Tab       | Background      | Surface                      | Text       | Accent    |
|-----------|-----------------|------------------------------|------------|-----------|
| Exercises | `#2f9cf6`       | `rgba(255,255,255,0.92)`     | `#0e2f5a`  | `#c2410c` |
| Muscles   | `#ef5a22`       | `rgba(255,245,235,0.94)`     | `#1e2f89`  | `#1e2f89` |
| Vocab     | `#ffd037`       | `rgba(255,252,242,0.94)`     | `#1c3fa4`  | `#c83200` |

### Degree involvement colors

Used for muscle involvement badges and bar fills. Text colors are
WCAG AA compliant against their badge backgrounds.

| Degree      | Text      | Badge background | Contrast |
|-------------|-----------|------------------|----------|
| Prime Mover | `#b91c1c` | `#fee2e2`        | 5.30:1   |
| Synergist   | `#c2410c` | `#ffedd5`        | 4.52:1   |
| Stabilizer  | `#1e40af` | `#dbeafe`        | 7.15:1   |
| Passive     | `#3a5f93` | `var(--surface-2)`| 5.82:1  |

Stabilizer deliberately uses its own blue palette, not `var(--accent)`. It
represents a consistent semantic category (blue = stabilizer) across all tabs.

### No dark mode

Intentionally absent. The tab background colors carry semantic meaning and are
the app's visual identity — they don't survive inversion. A dark variant would
need its own palette (deep backgrounds, tinted glass surfaces). That is a full
redesign, not a theming tweak.

---

## Typography

Three typefaces. Each has one job.

### System sans-serif — body
`"SF Pro Text", "Segoe UI", "Helvetica Neue", Arial, sans-serif`

The invisible workhorse. Used for all body text, labels, filter chips, sheet
content, and UI copy.

### League Gothic — display
`"League Gothic", Impact, sans-serif`

Tab headings, navigation labels, hero eyebrows, section headers, and filter
panel titles. Always uppercase. Letter-spacing 0.02–0.08em depending on size.

### Caveat Brush — decorative kicker
`"Caveat Brush", "Bradley Hand", cursive`

One line of handwritten text above a League Gothic tab heading. That is its
entire job. Font size is 28px (a deliberate exception to the type scale —
this is a decorative element, not a content size). It never appears on:
- Body text
- Badges or tags
- The detail sheet or Builder View
- Any component added after the initial three tab heroes

If you are tempted to use Caveat Brush somewhere new, use color and weight
instead.

---

## Type Scale

All font sizes use named tokens. New components must use a token — never a
raw pixel value.

| Token           | Value                   | Usage                                        |
|-----------------|-------------------------|----------------------------------------------|
| `--text-xs`     | 11px                    | Badges, meta labels, fine print              |
| `--text-sm`     | 14px                    | Secondary copy, filter chips, tab copy       |
| `--text-base`   | 15px                    | Body text, exercise names, sheet content     |
| `--text-lg`     | 19px                    | Card titles, section headers, sheet name     |
| `--text-xl`     | 24px                    | Subsection headings, vocab display           |
| `--text-display`| `clamp(40px, 8vw, 64px)`| League Gothic tab headings                   |

**Exception:** Caveat Brush kicker uses 28px, hardcoded. This is the only
intentional departure from the scale.

---

## Border Radius Scale

All border-radius values use named tokens. New components must pick from the
scale — no values between steps.

| Token      | Value  | Usage                                     |
|------------|--------|-------------------------------------------|
| `--r-xs`   | 4px    | Progress bars, thin insets                |
| `--r-sm`   | 8px    | Inline badges, small tags                 |
| `--r-md`   | 14px   | Filter chips, sub-cards, row items        |
| `--r-lg`   | 18px   | Nav buttons, section cards, exercise rows |
| `--r-xl`   | 22px   | Hero cards, detail sheet top corners      |
| `--r-full` | 999px  | Pill badges                               |

Circular elements (muscle anatomy diagrams) may use `50%` — that is not a
radius scale value, it is a geometry choice.

---

## Layout

- Max content width: 760px, centered.
- Bottom navigation height: `var(--nav-h)` = 82px, fixed.
- Base gap: `var(--gap)` = 12px.
- Sheet overlay: fixed to bottom, `min(calc(100% - 16px), 680px)` wide,
  8px breathing room on narrow screens.
- Builder View locks sheet height to 78dvh (`.builder-open` class) to
  prevent top-edge jitter during stage transitions.

---

## Component Vocabulary

### tab-hero
Shared hero at the top of all three tabs. Contains the Caveat Brush kicker,
League Gothic tab title, and short tab copy on a tab-colored glass surface.

### view-toggle (User / Builder)
Appears on exercise detail sheets for the five curated Observatory exercises.
Switches between the user-facing fact view and the pipeline-replay Builder View.

### detail sheet
Bottom sheet for exercise details. `--r-xl` top corners, slides up on
exercise tap. Max-width 680px. In Builder View, height is locked to 78dvh.

### badges
Degree involvement badges (Prime Mover, Synergist, Stabilizer, Passive) use
`--r-full` and `--text-xs`. Equipment and movement pattern tags use `--r-sm`
and read as secondary metadata.

### obs-stepper (Builder View)
Five-stage pipeline replay stepper. Stage titles use `--text-lg`, claim
labels `--text-xs`, claim values `--text-sm`. Method badges (`--r-sm`)
are color-coded by resolution method.
