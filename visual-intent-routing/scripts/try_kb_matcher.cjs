#!/usr/bin/env node
// Quick A/B try-out: current LLM matcher vs a KB-enriched matcher (Option D / b3).
//
// For a HANDFUL of queries (passed on argv, or a default representative set),
// prints side by side, with gold verdicts:
//   Path A         — keyword/alias retrieval (offline), same as eval_template_routing.cjs
//   Path B (desc)  — the CURRENT production matcher: catalog = English description only
//                    (mirror of lib/searchTemplateMatch.ts::buildCatalogBlob)
//   Path B (KB)    — SAME prompt, SAME model, but catalog ENRICHED from
//                    scripts/configs/template_capability_kb.json:
//                    + real example param values, + search aliases (incl. CJK), + topics
//
// Only the catalog blob differs between the two B variants, so any delta is
// attributable to the KB enrichment. Prompt/model/params are held constant.
//
// Constraints: reads only local JSON; OPENAI_API_KEY read from .env.local only,
// never printed or persisted. No production file is modified.
//
// Usage:
//   node scripts/try_kb_matcher.cjs                       # default sample set
//   node scripts/try_kb_matcher.cjs 单词 chiikawa "spring flowers"
//   node scripts/try_kb_matcher.cjs --kb-cap=6            # cap KB fields per template

"use strict";
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const argv = process.argv.slice(2);
const capArg = argv.find((a) => a.startsWith("--kb-cap="));
const KB_CAP = capArg ? parseInt(capArg.slice(9), 10) : 6;
const cliQueries = argv.filter((a) => !a.startsWith("--"));

const TEMPLATES = JSON.parse(fs.readFileSync(path.join(ROOT, "public/data/nano_templates.json"), "utf-8"));
const INSP = JSON.parse(fs.readFileSync(path.join(ROOT, "public/data/nano_inspiration.json"), "utf-8"));
const EN_NANO = JSON.parse(fs.readFileSync(path.join(ROOT, "messages/en/nano.json"), "utf-8"));
const KB = JSON.parse(fs.readFileSync(path.join(ROOT, "scripts/configs/template_capability_kb.json"), "utf-8"));
const GOLD = JSON.parse(fs.readFileSync(path.join(ROOT, "scripts/configs/vir_routing_gold.json"), "utf-8"));
const GOLD_BY_Q = new Map((GOLD.queries || GOLD).map((r) => [r.query, r]));
const GEN_IDS = new Set(TEMPLATES.filter((t) => t.allow_generation === true).map((t) => t.id));
const KB_BY_ID = new Map((KB.templates || KB).map((t) => [t.template_id, t]));

// Default sample: queries that stress the two known B blind spots (CJK +
// capability-beyond-name), plus two controls B already handles well.
const DEFAULT_QUERIES = [
  "单词",                                    // CJK vocab — B(desc) returns []
  "植物",                                    // CJK plants — B(desc) returns []
  "证件照",                                  // CJK id photo
  "chiikawa",                                // capability-beyond-name (fandom grid)
  "食物",                                    // CJK food
  "minimalist autumn outfit for japan travel", // control: B(desc) already wins
];

// ============================================================
// Path A — keyword/alias retrieval (compact port of eval_template_routing.cjs)
// ============================================================
const templateBlob = new Map();
for (const loc of ["en", "zh"]) {
  let entries;
  try { entries = JSON.parse(fs.readFileSync(path.join(ROOT, `messages/${loc}/nano.json`), "utf-8")); } catch { continue; }
  for (const [tid, e] of Object.entries(entries)) {
    if (!e) continue;
    const parts = [e.category, e.title, e.description, e?.content?.sections?.what, e?.content?.sections?.who]
      .filter((v) => typeof v === "string" && v.length > 0);
    if (parts.length === 0) continue;
    templateBlob.set(tid, (templateBlob.get(tid) ?? "") + " " + parts.join(" ").toLowerCase());
  }
}
const STOPWORDS = new Set(["the","a","an","of","in","on","is","are","and","or","to","for","with","by","at","as","be","this","that","的","了","和","及","topic","topics","theme","themes","category","categories","insights","highlights","guide","guides"]);
const normalizeForSearch = (s) => s.toLowerCase().replace(/×/g, "x");
function buildSearchTokens(query) {
  const primary = normalizeForSearch(query).split(/[\s,，、。.:：=·\/|()\[\]+*]+/).map((w) => w.trim()).filter((w) => w && !STOPWORDS.has(w));
  const bigrams = [];
  if (primary.length === 1 && /[一-龥]/.test(primary[0]) && primary[0].length >= 2) {
    const w = primary[0];
    for (let i = 0; i < w.length - 1; i++) { const bg = w.slice(i, i + 2); if (/^[一-龥]{2}$/.test(bg)) bigrams.push(bg); }
  }
  return { primary, bigrams };
}
const relaxedPrimaryThreshold = (n) => (n <= 1 ? 1 : Math.ceil(n / 2));
const bigramHitThreshold = (n) => (n <= 1 ? 1 : n <= 3 ? 2 : 3);
function tokenInBlob(blob, t) {
  if (!t) return false;
  if (/[一-龥]/.test(t)) return blob.includes(t);
  const esc = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^a-z0-9])${esc}([^a-z0-9]|$)`).test(blob);
}
function scoreBlob(blob, tokens) {
  let primaryHits = 0; for (const t of tokens.primary) if (tokenInBlob(blob, t)) primaryHits++;
  let bigramHits = 0; for (const t of tokens.bigrams) if (blob.includes(t)) bigramHits++;
  return { primaryHits, bigramHits, allPrimary: primaryHits === tokens.primary.length };
}
function scoreOnce(query) {
  const tokens = buildSearchTokens(query);
  if (tokens.primary.length === 0 && tokens.bigrams.length === 0) return { strictTpl: new Set(), tplI18n: new Set(), matchedIds: new Set() };
  const bigramThr = bigramHitThreshold(tokens.bigrams.length);
  const relaxedThr = relaxedPrimaryThreshold(tokens.primary.length);
  const strictTpl = new Set(), relaxedTpl = new Set();
  for (const [tid, blob] of templateBlob) {
    const s = scoreBlob(blob, tokens);
    if (s.allPrimary || s.bigramHits >= bigramThr) strictTpl.add(tid);
    else if (s.primaryHits >= relaxedThr && relaxedThr > 0) relaxedTpl.add(tid);
  }
  const tplI18n = strictTpl.size > 0 ? strictTpl : relaxedTpl;
  const strictIds = new Set(), relaxedIds = new Set();
  for (const r of INSP) {
    if (strictTpl.has(r.template_id)) { strictIds.add(r.id); continue; }
    const localeFields = Object.values(r.locales ?? {}).flatMap((l) => [l?.title, l?.category]);
    const blob = normalizeForSearch([r.id, r.template_id, ...(r.tags ?? []), ...(r.search_aliases ?? []), ...Object.values(r.params ?? {}), ...localeFields].filter((v) => typeof v === "string" && v.length > 0).join(" "));
    const s = scoreBlob(blob, tokens);
    if (s.allPrimary || s.bigramHits >= bigramThr) strictIds.add(r.id);
    else if (s.primaryHits >= relaxedThr && relaxedThr > 0) relaxedIds.add(r.id);
  }
  const matchedIds = strictIds.size > 0 ? strictIds : relaxedIds;
  return { strictTpl, tplI18n, matchedIds };
}
const INSP_TEMPLATE = new Map(INSP.map((r) => [r.id, r.template_id]));
function pathARanked(query) {
  const { strictTpl, tplI18n, matchedIds } = scoreOnce(query);
  const inspCount = new Map();
  for (const id of matchedIds) { const tid = INSP_TEMPLATE.get(id); if (tid) inspCount.set(tid, (inspCount.get(tid) || 0) + 1); }
  const cand = new Set([...tplI18n, ...inspCount.keys()]);
  return [...cand].filter((tid) => GEN_IDS.has(tid))
    .map((tid) => ({ tid, strict: strictTpl.has(tid) ? 1 : 0, n: inspCount.get(tid) || 0 }))
    .sort((a, b) => b.strict - a.strict || b.n - a.n || a.tid.localeCompare(b.tid))
    .map((x) => x.tid);
}

// ============================================================
// Path B — two catalog variants (prompt/model/params identical)
// ============================================================
const B_MODEL = "gpt-4o-mini";

// CURRENT production catalog: id | params | English description (≤180). desc-only.
function catalogPlain() {
  const lines = [];
  for (const t of TEMPLATES) {
    if (t.allow_generation !== true) continue;
    const desc = ((EN_NANO[t.id] || {}).description || "").replace(/\s+/g, " ").slice(0, 180);
    const params = ((t.locales?.en?.parameters) || []).map((p) => p.name).filter(Boolean).join(",");
    lines.push(`- ${t.id} | params=[${params}] | ${desc}`);
  }
  return lines.join("\n");
}

// KB-enriched catalog (Option D): same line + capability evidence mined from
// real inspirations — example param values, search aliases (incl. CJK), topics.
function catalogKB() {
  const lines = [];
  for (const t of TEMPLATES) {
    if (t.allow_generation !== true) continue;
    const desc = ((EN_NANO[t.id] || {}).description || "").replace(/\s+/g, " ").slice(0, 180);
    const params = ((t.locales?.en?.parameters) || []).map((p) => p.name).filter(Boolean).join(",");
    const kb = KB_BY_ID.get(t.id);
    let line = `- ${t.id} | params=[${params}] | ${desc}`;
    if (kb) {
      const ex = (kb.sample_param_values || []).slice(0, KB_CAP);
      // aka = aliases + topics, CJK-FIRST so the CJK signal survives the cap
      // (the whole point of enrichment is to make CJK queries matchable).
      const hasCJK = (s) => /[一-龥]/.test(s);
      const aka = [...new Set([...(kb.search_aliases || []), ...(kb.inspiration_topics || []), ...(kb.template_topics || [])])]
        .sort((a, b) => (hasCJK(b) ? 1 : 0) - (hasCJK(a) ? 1 : 0))
        .slice(0, KB_CAP);
      if (ex.length) line += ` | examples: ${ex.join("; ")}`;
      if (aka.length) line += ` | aka: ${aka.join(", ")}`;
    }
    lines.push(line);
  }
  return lines.join("\n");
}

// EXACT production system prompt — kept in sync with lib/searchTemplateMatch.ts.
const B_SYSTEM = `You match user search queries to Curify image-generation templates that could create content for those queries.

For EACH query, decide:
- top 2-3 best-fit templates (ordered by confidence desc; fewer is fine if no clear fit)
- for each pick: concrete parameter values extracted from the query
- confidence in 0.0..1.0 (be honest — 0.3 + reason is fine if uncertain)
- short reason (<= 80 chars)

CRITICAL — read EVERY modifier in the query, not just the subject noun. Templates are differentiated by visual style AND layout, not only topic:

- **Style modifiers** (watercolor / retro / vintage / minimalist / photorealistic / anime / kawaii / ink / monochrome) — pick a template whose OUTPUT natively has that style. "Watercolor map" needs a watercolor map template, not a generic destination list.
- **Format / layout modifiers** (chart / grid / list of N / top 10 / 16 types / dual / before-after / comparison / timeline) — pick the template whose LAYOUT matches. "Chart of 16 MBTI types" needs a grid/chart template, NOT a single-character profile.
- **Audience modifiers** (for kids / for beginners / educational) — pick the template whose style fits.
- **Artifact-type modifiers** (recipe poster / promotional poster / care guide / how-to / infographic) — these name the artifact directly. Prefer the template that explicitly produces that artifact.

Pick templates that can GENERATE content for the query AS TYPED, not just templates whose tags overlap with one word.

SUBJECT MATCH IS A HARD GATE (from human eval 2026-06-17). Verify the template's CORE SUBJECT actually serves the query's specific noun BEFORE you return it:

- **REJECT a template whose subject-axis is disjoint from the query, even if it shares the layout/format axis.**
  · "Brazil national team" wants a SQUAD POSTER → do NOT return mbti-of-team templates (different subject-axis: personality typing vs roster lineup).
  · "english spanish word comparison" → do NOT return english-CHINESE comparison templates (language-pair mismatch is a subject mismatch).
  · "diy craft tutorial poster" → do NOT return vegetable-planting-tutorial or action-vocab-card templates (their subjects are vegetables / language, not crafts).
  · "evolution snacks infographic" → do NOT return history-timeline or fashion-evolution templates (subjects are history / clothing, not food).
  · "amusement park map infographic" → do NOT return generic travel-poster templates (subject is parks / rides, not destinations).
  · "1950s vintage diner illustration" → do NOT return evolution / travel-journal / festival templates (none match the era + venue).

- **Franchise / IP-specific queries need IP-aware templates.** Generic "character info card" is NOT a fit for "chiikawa" or named characters — return the kawaii / franchise-specific template if one exists; if not, return [] rather than a generic fallback.

- **Iconic-moment / event-analysis intent ≠ team-or-player templates.** "Maradona Hand of God" / "most memorable World Cup moments" want sports iconic-event-analysis-poster (single-moment deep-dive), NOT squad poster or schedule.

- **When NO catalog template has the right subject, return fewer picks — or [] — rather than padding with layout-matching but subject-wrong templates.** An honest [] is a real signal that beats a confident wrong pick.

Quick worked examples (from human eval ground truth):
  Q: "fifa 2026" → ✓ world cup poster + world cup schedule (subject + format align)
  Q: "Maradona Hand of God" → ✓ sports iconic-event-analysis-poster; ✗ generic football poster
  Q: "english spanish word comparison" → ✓ english-spanish vocabulary template if any; ✗ english-chinese comparison
  Q: "chiikawa" → ✓ kawaii-IP profile/grid template; ✗ generic character analysis
  Q: "diy craft tutorial poster" → ✓ crafting-step-by-step-tutorial template; ✗ vegetable planting or action vocab
  Q: "证件照 / id photo" → ✓ portrait-id-photo template; ✗ product poster

Catalog:
{catalog}

Return ONLY a JSON object: {"matches": [{"template_id": "template-...", "params": {"key": "value"}, "confidence": 0.85, "reason": "..."}]}.
No prose, no markdown fences.`;

async function callB(query, client, catalogBlob) {
  const resp = await client.chat.completions.create({
    model: B_MODEL,
    messages: [{ role: "system", content: B_SYSTEM.replace("{catalog}", catalogBlob) }, { role: "user", content: `Query: ${query}` }],
    temperature: 0.2, max_tokens: 800,
  });
  let raw = (resp.choices?.[0]?.message?.content || "").trim().replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/i, "").trim();
  let parsed; try { parsed = JSON.parse(raw); } catch { return []; }
  const matches = Array.isArray(parsed.matches) ? parsed.matches : [];
  const seen = new Set(), out = [];
  for (const m of matches) {
    const tid = m && m.template_id;
    if (typeof tid !== "string" || !GEN_IDS.has(tid) || seen.has(tid)) continue;
    seen.add(tid); out.push(tid);
    if (out.length >= 3) break;
  }
  return out;
}

// ============================================================
// Verdict vs gold + pretty print
// ============================================================
function verdict(ranked, row) {
  if (!row) return "no-gold";
  const acc = new Set(row.acceptable_template_ids || []);
  const near = new Set(row.near_miss_template_ids || []);
  if (acc.size === 0) { // content gap
    const wrong = ranked.filter((t) => !near.has(t));
    return wrong.length === 0 ? "gap-clean ✓" : "gap-confusion ✗";
  }
  if (ranked[0] && acc.has(ranked[0])) return "top1 ✓";
  if (ranked.slice(0, 3).some((t) => acc.has(t))) return "top3 ✓";
  if (ranked.some((t) => acc.has(t))) return "rank-miss";
  return "recall-miss ✗";
}
const short = (ids) => ids.map((t) => t.replace("template-", "")).join(", ") || "—(empty)";

(async () => {
  const queries = cliQueries.length ? cliQueries : DEFAULT_QUERIES;

  // Catalog size delta (token proxy = chars/4).
  const cPlain = catalogPlain(), cKB = catalogKB();
  console.log(`KB-enriched matcher try-out — ${queries.length} queries · KB field cap=${KB_CAP}`);
  console.log(`catalog size:  desc-only ≈ ${Math.round(cPlain.length / 4)} tok  →  KB ≈ ${Math.round(cKB.length / 4)} tok  (${(cKB.length / cPlain.length).toFixed(1)}×)\n`);

  let dotenvOk = true;
  try { require("dotenv").config({ path: path.join(ROOT, ".env.local") }); } catch { dotenvOk = false; }
  let client = null;
  if (process.env.OPENAI_API_KEY) {
    try { const OpenAI = require("openai"); client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY, timeout: 60000 }); } catch {}
  }
  if (!client) {
    console.log(`[Path B skipped] no OPENAI_API_KEY (${dotenvOk ? ".env.local loaded but key missing" : "dotenv/.env.local not found"}). Path A still shown.\n`);
  }

  for (const q of queries) {
    const row = GOLD_BY_Q.get(q);
    const goldStr = row
      ? `[${row.locale},${row.ambiguity}] gold: ${short(row.acceptable_template_ids || [])}${(row.acceptable_template_ids || []).length === 0 ? " (content-gap)" : ""}`
      : "[not in gold set]";
    console.log(`■ QUERY: ${q}`);
    console.log(`  ${goldStr}`);

    const a = pathARanked(q).slice(0, 3);
    console.log(`  Path A        : ${short(a).padEnd(52)} ${verdict(a, row)}`);

    if (client) {
      let bPlain = [], bKB = [];
      try { bPlain = await callB(q, client, cPlain); } catch (e) { bPlain = [`ERR:${e.message}`]; }
      try { bKB = await callB(q, client, cKB); } catch (e) { bKB = [`ERR:${e.message}`]; }
      console.log(`  Path B (desc) : ${short(bPlain).padEnd(52)} ${verdict(bPlain, row)}`);
      console.log(`  Path B (KB)   : ${short(bKB).padEnd(52)} ${verdict(bKB, row)}`);
    }
    console.log("");
  }
})();
