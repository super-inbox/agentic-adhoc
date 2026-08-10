"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  loadConfig,
  loadJson,
  sha256,
} = require("../../lib/vir_eval/common.cjs");
const { loadRegistry } = require("../../lib/vir_eval/registry.cjs");
const { loadSeeds } = require("../../lib/vir_eval/schema.cjs");
const {
  generateChallenges,
  generateCore,
  generateExploration,
  loadCachedResponse,
} = require("../../lib/vir_eval/expand.cjs");
const { MockRouterAdapter } = require("../../lib/vir_eval/adapters.cjs");
const { runRouter } = require("../../lib/vir_eval/runner.cjs");
const { scoreDataset } = require("../../lib/vir_eval/metrics.cjs");
const { generateReports } = require("../../lib/vir_eval/reporting.cjs");
const {
  compareRuns,
  pairedBootstrapDelta,
} = require("../../lib/vir_eval/compare.cjs");

const config = loadConfig("benchmarks/vir_v2/configs/default.yaml");
const registry = loadRegistry(config.paths.registry, config.paths.catalog);
const seeds = loadSeeds(config.paths.seeds);

test("rule expansion is deterministic at a fixed seed and quota", () => {
  const args = { seeds, registry, countPerTarget: 5, randomSeed: 1234 };
  const first = generateCore(args);
  const second = generateCore(args);
  assert.deepEqual(first, second);
  assert.equal(first.length, 75);
  assert.equal(new Set(first.map((record) => record.id)).size, 75);
  assert.equal(
    first.every(
      (record) =>
        record.provenance.random_seed === 1234 &&
        record.validation.status === "pending",
    ),
    true,
  );
});

test("exploration expansion is deterministic, multilingual, and capability-tagged", () => {
  const profiles = loadJson(config.paths.exploration_profiles);
  const args = {
    profiles,
    registry,
    count: 30,
    randomSeed: 1234,
    evaluationK: 3,
  };
  const first = generateExploration(args);
  assert.deepEqual(first, generateExploration(args));
  assert.equal(first.length, 30);
  assert.deepEqual(
    Object.fromEntries(
      ["zh", "en", "mixed"].map((language) => [
        language,
        first.filter((record) => record.language === language).length,
      ]),
    ),
    { zh: 10, en: 10, mixed: 10 },
  );
  assert.ok(first.every((record) => record.query.length <= 200));
  assert.equal(
    first.every(
      (record) =>
        record.partition === "exploration" &&
        record.gold.target_mode === "exploration" &&
        new Set(
          Object.values(
            record.gold.exploration.target_style_families,
          ),
        ).size >= 2,
    ),
    true,
  );
});

test("generated challenge queries fit the current Curify input contract", () => {
  const records = generateChallenges({
    registry,
    ambiguousCount: 60,
    multiCount: 60,
    randomSeed: 1234,
  });
  assert.equal(records.length, 120);
  assert.ok(records.every((record) => record.query.length <= 200));
});

test("cached LLM response loader checks the prompt hash", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "vir-cache-test-"));
  const file = path.join(temp, "response.json");
  const promptHash = sha256("prompt");
  fs.writeFileSync(
    file,
    JSON.stringify({ prompt_hash: promptHash, raw_output: "{}", parsed: {} }),
  );
  assert.equal(loadCachedResponse(file, promptHash).raw_output, "{}");
  assert.equal(loadCachedResponse(file, sha256("other")), null);
});

function tinyRecord(id, query, target, partition = "core") {
  return {
    id,
    benchmark_version: "vir-v2",
    source_seed_id: null,
    semantic_cluster_id: `cluster-${id}`,
    partition,
    split: "dev",
    challenge_type: null,
    subject: target ? "vocabulary" : "gap",
    query,
    language: "en",
    difficulty: "low",
    transformation_types: ["explicit_artifact"],
    ontology: {
      subject_event: target ? "topic vocabulary" : "unsupported design",
      information_type: target ? "bilingual learning" : "unsupported request",
      style_layout: target ? "card grid" : "functional artifact",
    },
    gold: {
      target_mode: target ? "single" : "none",
      targets: target ? [target] : [],
      acceptable_target_sets: [],
      must_abstain: !target,
    },
    provenance: { generation_method: "manual" },
    validation: { status: "auto_accepted" },
  };
}

test("mock end-to-end execution and report generation need no network", async () => {
  const records = [
    tinyRecord(
      "q1",
      "Create English Spanish fruit bilingual vocabulary cards",
      "template-vocabulary",
    ),
    tinyRecord(
      "q2",
      "Generate a production-ready mobile banking wireframe",
      null,
      "content_gap",
    ),
  ];
  const adapter = new MockRouterAdapter({
    registry,
    topK: 3,
    abstentionThreshold: 0.1,
  });
  const run = await runRouter({ records, adapter, resume: false });
  assert.equal(run.predictions.length, 2);
  assert.equal(run.summary.error_count, 0);
  const score = scoreDataset({
    records,
    predictions: run.predictions,
    config,
  });
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "vir-report-test-"));
  const tempConfig = {
    ...config,
    paths: { ...config.paths, report_dir: temp },
  };
  const validation = {
    distributions: {
      partition: { core: 1, content_gap: 1 },
      language: { en: 2 },
    },
    schema_errors: [],
    status_counts: { auto_accepted: 2 },
    near_duplicates: [],
    content_gap_collisions: [],
    balance_warnings: [],
  };
  const manifest = {
    test_file_sha256: "test-sha",
    template_registry_version: registry.document.registry_version,
  };
  const report = generateReports({
    config: tempConfig,
    records,
    predictions: run.predictions,
    score,
    validation,
    benchmarkManifest: manifest,
    adapterName: adapter.name,
  });
  assert.equal(fs.existsSync(report.report_md), true);
  assert.equal(fs.existsSync(path.join(temp, "metrics.json")), true);
  assert.match(fs.readFileSync(report.report_md, "utf8"), /Primary metrics/);
  assert.match(fs.readFileSync(report.report_md, "utf8"), /Style exploration/);
  assert.equal(
    fs.existsSync(path.join(temp, "exploration_metrics.csv")),
    true,
  );
});

test("baseline comparison reports fixed/broken records and paired interval", () => {
  const records = [
    tinyRecord("q1", "bilingual fruit cards", "template-vocabulary"),
    tinyRecord("q2", "trip map", "template-travel"),
  ];
  const prediction = (id, template) => ({
    query_id: id,
    predictions: template
      ? [{ template_id: template, score: 0.8, rank: 1 }]
      : [],
    abstained: !template,
    latency_ms: 1,
    retry_count: 0,
    raw_output: {},
    error: null,
  });
  const baselinePredictions = [
    prediction("q1", "template-recipe"),
    prediction("q2", "template-travel"),
  ];
  const currentPredictions = [
    prediction("q1", "template-vocabulary"),
    prediction("q2", "template-recipe"),
  ];
  const comparison = compareRuns({
    records,
    baselinePredictions,
    currentPredictions,
    baselineMetrics: { accuracy: 0.5 },
    currentMetrics: { accuracy: 0.5 },
    config,
  });
  assert.deepEqual(comparison.newly_fixed_records, ["q1"]);
  assert.deepEqual(comparison.newly_broken_records, ["q2"]);
  assert.equal(comparison.paired_record_count, 2);
  const interval = pairedBootstrapDelta([false, true], [true, false], {
    samples: 100,
    seed: 1,
  });
  assert.equal(interval.samples, 100);
  assert.equal(typeof interval.lower, "number");
});

test("baseline comparison reports Style Exploration Lift at K", () => {
  const item = tinyRecord(
    "explore",
    "Explore several relevant visual directions",
    "template-vocabulary",
    "exploration",
  );
  item.split = "exploration";
  item.gold = {
    target_mode: "exploration",
    targets: ["template-vocabulary", "template-recipe", "template-travel"],
    acceptable_target_sets: [],
    must_abstain: false,
    exploration: {
      profile_id: "compare-test",
      evaluation_k: 3,
      required_subject_event: "broad theme",
      required_information_type: "open exploration",
      target_style_families: {
        "template-vocabulary": "illustrated-flashcard",
        "template-recipe": "food-photography",
        "template-travel": "hand-drawn-watercolor-map",
      },
      target_layout_families: {
        "template-vocabulary": "card-grid",
        "template-recipe": "recipe-poster",
        "template-travel": "map-itinerary",
      },
      acceptable_visual_style_families: [
        "illustrated-flashcard",
        "food-photography",
        "hand-drawn-watercolor-map",
      ],
    },
  };
  const prediction = (templates) => ({
    query_id: item.id,
    predictions: templates.map((template_id, index) => ({
      template_id,
      score: 0.9 - index * 0.1,
      rank: index + 1,
    })),
    abstained: false,
    latency_ms: 1,
    raw_output: {},
    error: null,
  });
  const comparison = compareRuns({
    records: [item],
    baselinePredictions: [
      prediction([
        "template-vocabulary",
        "template-product-poster",
        "template-fashion-inspired-gown-design-sheet",
      ]),
    ],
    currentPredictions: [
      prediction([
        "template-vocabulary",
        "template-recipe",
        "template-travel",
      ]),
    ],
    baselineMetrics: {},
    currentMetrics: {},
    config,
  });
  assert.equal(
    comparison.style_exploration_lift_at_k.baseline,
    1 / 3,
  );
  assert.ok(
    Math.abs(comparison.style_exploration_lift_at_k.current - 3) < 1e-12,
  );
  assert.ok(
    comparison.style_exploration_lift_at_k.absolute_lift > 2.66,
  );
});
