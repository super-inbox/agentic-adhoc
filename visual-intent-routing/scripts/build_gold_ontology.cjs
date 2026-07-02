#!/usr/bin/env node
/**
 * build_gold_ontology.cjs
 * ---------------------------------------------------------------------------
 * Enrich vir_routing_gold.json with 3-tier ontology coordinates and write
 * scripts/configs/vir_routing_gold_on.json.
 *
 * Per the three-tier ontology (docs/search-and-content.md#three-tier-ontology),
 * every template sits at a cell (Subject × Info-type × Layout):
 *   Tier I   Subject   — from taxonomy.template_subjects            (auto-derived tag)
 *   Tier II  Info-type — from taxonomy.template_information_types   (auto-derived tag)
 *   Tier III Layout    — heuristic from template-id substrings      (NOT yet a real tag;
 *                        same LAYOUT_RULES as scripts/build_3d_gap_matrix.cjs)
 *
 * This turns Layer-1 routing scoring from a flat hit/miss into per-axis
 * attribution: a wrong route is a NEIGHBOR cell — usually right on subject,
 * wrong on info-type or layout. Each near_miss carries `axis_mismatch` telling
 * you exactly which axis it diverges on vs the gold cell.
 *
 *   gold_cell        = coordinate of primary_template_id (the single best route)
 *   acceptable_cells = coordinates of every acceptable id (the multi-valid spread)
 *   near_miss_cells  = coordinates + axis_mismatch of every near-miss
 *
 * Pure over local JSON. Re-runnable: node scripts/build_gold_ontology.cjs
 * Contamination note: coordinates are derived from the SHIPPED taxonomy maps
 * (facts about the catalog), not from a router — safe to attach to the gold.
 */
const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');
const CFG = path.join(__dirname, 'configs');
const GOLD_IN = path.join(CFG, 'vir_routing_gold.json');
const GOLD_OUT = path.join(CFG, 'vir_routing_gold_on.json');
const TAX_PATH = path.join(REPO, 'lib', 'taxonomy.json');

const gold = JSON.parse(fs.readFileSync(GOLD_IN, 'utf-8'));
const tax = JSON.parse(fs.readFileSync(TAX_PATH, 'utf-8'));
const templateSubjects = tax.template_subjects || {};
const templateInfoTypes = tax.template_information_types || {};

// Canonical Tier-I subjects worth reporting on (mirror build_3d_gap_matrix.cjs
// MATRIX_SUBJECTS + tier1) — used to filter the raw template_subjects tag soup
// down to meaningful subject coordinates.
const CANON_SUBJECTS = new Set([
  ...(Array.isArray(tax.tier1) ? tax.tier1 : Object.keys(tax.tier1 || {})),
  'character', 'mbti', 'language', 'vocabulary', 'learning', 'lifestyle',
  'travel', 'culture', 'food', 'fashion', 'history', 'science',
  'sports', 'world-cup', 'anime', 'celebrity', 'product', 'design',
]);

// Tier-III layout heuristic — copied verbatim from build_3d_gap_matrix.cjs so
// both tools classify identically. Layout is NOT a queryable tag yet
// (2026-06-01 audit Open item 2); this is an id-substring approximation.
const LAYOUT_RULES = [
  { layout: 'flashcard',      test: (id) => /flashcard|flashcards|vocab-poster|vocab-flashcard|learning-card/.test(id) },
  { layout: 'matching-chart', test: (id) => /matching-chart|9-traits/.test(id) },
  { layout: 'grid',           test: (id) => /grid|fandom-character-grid|book-recommendation|top10|photo-grid/.test(id) },
  { layout: 'timeline',       test: (id) => /timeline|life-journey|evolution-timeline|flowing-journey|wolf-path/.test(id) },
  { layout: 'map',            test: (id) => /-map$|-map-|landmark-map|travel-map|word-origins-map|theme-map/.test(id) },
  { layout: 'before-after',   test: (id) => /before-after|then-vs-now|generation-comparison|stereotype-vs-reality/.test(id) },
  { layout: 'vs-battle',      test: (id) => /battle|-vs-|-comparison|contrast/.test(id) },
  { layout: 'collage',        test: (id) => /collage|scrapbook|deconstruction-board|stamp-collection|red-envelope-set/.test(id) },
  { layout: 'mood-board',     test: (id) => /mood-board/.test(id) },
  { layout: 'carousel',       test: (id) => /series-infographic|series-travel/.test(id) },
  { layout: 'infographic',    test: (id) => /infographic/.test(id) },
  { layout: 'guide-card',     test: (id) => /guide|tutorial|step-by-step|routine|recipe|plan|how-to/.test(id) },
  { layout: 'character-card', test: (id) => /character-card|character-profile|mbti-|character-analysis|profile/.test(id) },
  { layout: 'poster',         test: (id) => /poster|illustration|sketch|painting/.test(id) },
];
const classifyLayout = (id) => (LAYOUT_RULES.find((r) => r.test(id)) || { layout: 'single-image' }).layout;

// Coordinate of one template id.
function cellOf(templateId) {
  const rawSubjects = templateSubjects[templateId] || [];
  const subjects = rawSubjects.filter((s) => CANON_SUBJECTS.has(s));
  return {
    template_id: templateId,
    subjects: subjects.length ? subjects : rawSubjects, // fall back to raw if none canonical
    info_types: templateInfoTypes[templateId] || [],
    layout: classifyLayout(templateId),
    // flags so a reviewer sees where the coordinate is weak / missing
    _subject_source: subjects.length ? 'canonical' : rawSubjects.length ? 'raw-fallback' : 'MISSING',
    _info_type_source: (templateInfoTypes[templateId] || []).length ? 'taxonomy' : 'MISSING',
    _layout_source: 'heuristic',
  };
}

const overlaps = (a, b) => a.some((x) => b.includes(x));

// vs the gold cell, which axes does this cell diverge on?
function axisMismatch(cell, goldCell) {
  if (!goldCell) return null;
  const m = [];
  if (goldCell.subjects.length && cell.subjects.length && !overlaps(cell.subjects, goldCell.subjects)) m.push('subject');
  if (goldCell.info_types.length && cell.info_types.length && !overlaps(cell.info_types, goldCell.info_types)) m.push('info_type');
  if (goldCell.layout && cell.layout && cell.layout !== goldCell.layout) m.push('layout');
  return m;
}

let withCell = 0;
let gapNoCell = 0;
const enriched = gold.queries.map((q) => {
  const isGap = !q.acceptable_template_ids || q.acceptable_template_ids.length === 0;
  const goldCell = q.primary_template_id ? cellOf(q.primary_template_id) : null;
  if (goldCell) withCell++;
  if (isGap) gapNoCell++;

  const acceptable_cells = (q.acceptable_template_ids || []).map(cellOf);
  const near_miss_cells = (q.near_miss_template_ids || []).map((id) => {
    const c = cellOf(id);
    return { ...c, axis_mismatch: axisMismatch(c, goldCell) };
  });

  return {
    ...q,
    ontology: {
      gold_cell: goldCell, // coordinate of primary (the single best route); null for content-gap queries
      gold_cell_source: goldCell ? 'derived-from-primary' : 'content-gap-no-cell',
      acceptable_cells, // the multi-valid spread around the gold cell
      near_miss_cells, // each carries axis_mismatch vs gold_cell
    },
  };
});

const out = {
  schema_version: (gold.schema_version || 1),
  ontology_schema_version: 1,
  generated: gold.generated || null,
  title: (gold.title || 'VIR routing gold') + ' — ontology-enriched (Subject × Info-type × Layout)',
  description:
    'vir_routing_gold.json enriched with 3-tier ontology coordinates per template, ' +
    'for per-axis routing-error attribution. Regenerate via scripts/build_gold_ontology.cjs. ' +
    'Base gold is still the source of truth for the labels themselves.',
  ontology_legend: {
    tiers: {
      'I_subject': 'from taxonomy.template_subjects (auto-derived tag), filtered to canonical subjects',
      'II_info_type': 'from taxonomy.template_information_types (auto-derived tag)',
      'III_layout': 'HEURISTIC from template-id substrings (same LAYOUT_RULES as build_3d_gap_matrix.cjs); Layout is NOT yet a queryable tag (2026-06-01 audit Open item 2), so treat as approximate',
    },
    fields: {
      gold_cell: 'coordinate of primary_template_id — the single intended cell (null for content-gap queries)',
      acceptable_cells: 'coordinate of each acceptable id — the multi-valid spread of cells that are also correct',
      near_miss_cells: 'coordinate of each near-miss + axis_mismatch = which of [subject, info_type, layout] it diverges from gold_cell on',
      _subject_source: "canonical | raw-fallback | MISSING — flags weak/absent subject coordinates for review",
      _info_type_source: 'taxonomy | MISSING',
    },
    caveat: 'Coordinates are derived from the shipped catalog taxonomy (facts), not from any router, so they do not contaminate a KB/router eval. But the base labels (acceptable_template_ids) are still a Claude draft pending human review — see vir-routing-eval-v1-review-checklist.md.',
  },
  review_status: gold.review_status,
  label_legend: gold.label_legend,
  queries: enriched,
};

fs.writeFileSync(GOLD_OUT, JSON.stringify(out, null, 2));

// Coverage report so weak coordinates are visible immediately.
let missSubj = 0, missInfo = 0;
enriched.forEach((q) => {
  const cells = [q.ontology.gold_cell, ...q.ontology.acceptable_cells].filter(Boolean);
  cells.forEach((c) => {
    if (c._subject_source === 'MISSING') missSubj++;
    if (c._info_type_source === 'MISSING') missInfo++;
  });
});
console.log(
  `Wrote ${GOLD_OUT}\n` +
  `  queries:            ${enriched.length}\n` +
  `  with gold_cell:     ${withCell}\n` +
  `  content-gap (null): ${gapNoCell}\n` +
  `  cells missing subject tag: ${missSubj}\n` +
  `  cells missing info-type tag: ${missInfo}`
);
