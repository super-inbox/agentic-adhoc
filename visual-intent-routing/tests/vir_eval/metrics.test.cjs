"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { loadConfig } = require("../../lib/vir_eval/common.cjs");
const {
  ambiguousMatch,
  explorationRecordMetrics,
  scoreDataset,
  setMetrics,
} = require("../../lib/vir_eval/metrics.cjs");

const config = loadConfig("benchmarks/vir_v2/configs/default.yaml");

function record(id, mode, targets, extra = {}) {
  return {
    id,
    benchmark_version: "vir-v2",
    source_seed_id: null,
    semantic_cluster_id: extra.cluster ?? `cluster-${id}`,
    partition: extra.partition ?? "core",
    split: extra.split ?? "dev",
    challenge_type: extra.challenge_type ?? null,
    subject: extra.subject ?? "test",
    query: extra.query ?? `query ${id}`,
    language: extra.language ?? "en",
    difficulty: extra.difficulty ?? "low",
    transformation_types: extra.transformations ?? ["explicit_artifact"],
    ontology: {
      subject_event: "test subject",
      information_type: "test operation",
      style_layout: "test layout",
    },
    gold: {
      target_mode: mode,
      targets,
      acceptable_target_sets: extra.acceptable ?? [],
      must_abstain: mode === "none",
      ...(extra.exploration ? { exploration: extra.exploration } : {}),
    },
    provenance: {},
    validation: { status: "auto_accepted" },
  };
}

function prediction(id, ids, { abstained = false, scores = [] } = {}) {
  return {
    query_id: id,
    predictions: ids.map((template_id, index) => ({
      template_id,
      rank: index + 1,
      score: scores[index] ?? 0.8 - index * 0.1,
    })),
    abstained,
    latency_ms: 10,
    retry_count: 0,
    raw_output: {},
    error: null,
  };
}

test("scores single targets, top-k, and MRR deterministically", () => {
  const records = [
    record("q1", "single", ["template-vocabulary"]),
    record("q2", "single", ["template-travel"], {
      language: "zh",
      difficulty: "high",
      transformations: ["typo_noise"],
    }),
  ];
  const predictions = [
    prediction("q1", ["template-recipe", "template-vocabulary"]),
    prediction("q2", ["template-travel"]),
  ];
  const result = scoreDataset({ records, predictions, config });
  assert.equal(
    result.metrics.primary_core.positive_query_top1_exact_accuracy.value,
    0.5,
  );
  assert.equal(result.metrics.primary_core.recall_at_1.value, 0.5);
  assert.equal(result.metrics.primary_core.recall_at_3.value, 1);
  assert.equal(result.metrics.primary_core.mean_reciprocal_rank, 0.75);
});

test("scores empty-target abstention as a separate classification problem", () => {
  const records = [
    record("supported", "single", ["template-vocabulary"]),
    record("gap", "none", [], {
      partition: "content_gap",
      subject: "gap",
    }),
  ];
  const predictions = [
    prediction("supported", ["template-vocabulary"]),
    prediction("gap", [], { abstained: true }),
  ];
  const result = scoreDataset({ records, predictions, config });
  assert.equal(
    result.metrics.primary_core.overall_exact_accuracy_including_no_match.value,
    1,
  );
  assert.equal(result.metrics.content_gap.abstention_precision, 1);
  assert.equal(result.metrics.content_gap.abstention_recall, 1);
  assert.equal(result.metrics.content_gap.false_routing_rate_on_content_gap.value, 0);
});

test("scores multi-target exact and partial set metrics", () => {
  assert.deepEqual(
    setMetrics(
      ["template-vocabulary", "template-recipe"],
      ["template-vocabulary", "template-recipe"],
    ),
    {
      exact: true,
      precision: 1,
      recall: 1,
      f1: 1,
      partial: true,
      intersection: 2,
    },
  );
  const records = [
    record("multi", "multi", ["template-vocabulary", "template-recipe"], {
      partition: "challenge",
      split: "challenge",
      challenge_type: "multi_intent",
    }),
  ];
  const predictions = [
    prediction("multi", ["template-vocabulary", "template-recipe"]),
  ];
  const result = scoreDataset({ records, predictions, config });
  assert.equal(result.metrics.challenges.multi_intent.exact_set_match.value, 1);
  assert.equal(result.metrics.challenges.multi_intent.set_f1, 1);
});

test("scores ambiguous acceptable target sets without merging into core", () => {
  const ambiguous = record(
    "amb",
    "ambiguous",
    ["template-travel", "template-intangible-heritage"],
    {
      partition: "challenge",
      split: "challenge",
      challenge_type: "ambiguous",
      acceptable: [
        ["template-travel"],
        ["template-intangible-heritage"],
      ],
    },
  );
  const pred = prediction("amb", ["template-intangible-heritage"]);
  assert.equal(ambiguousMatch(ambiguous, ["template-travel"], false), true);
  const result = scoreDataset({
    records: [ambiguous],
    predictions: [pred],
    config,
  });
  assert.equal(
    result.metrics.challenges.ambiguous.acceptable_target_set_match_rate.value,
    1,
  );
  assert.equal(
    result.metrics.challenges.ambiguous.excluded_from_primary_core_accuracy,
    true,
  );
});

test("aggregates language and difficulty slices", () => {
  const records = [
    record("en-low", "single", ["template-vocabulary"], {
      language: "en",
      difficulty: "low",
    }),
    record("zh-high", "single", ["template-travel"], {
      language: "zh",
      difficulty: "high",
    }),
  ];
  const predictions = [
    prediction("en-low", ["template-vocabulary"]),
    prediction("zh-high", ["template-recipe"]),
  ];
  const result = scoreDataset({ records, predictions, config });
  const language = result.sliceMetrics.filter(
    (row) => row.dimension === "language",
  );
  assert.equal(language.find((row) => row.value === "en").exact_accuracy, 1);
  assert.equal(language.find((row) => row.value === "zh").exact_accuracy, 0);
  assert.equal(result.metrics.robustness.difficulty_accuracy.low, 1);
  assert.equal(result.metrics.robustness.difficulty_accuracy.high, 0);
});

test("scores only relevant style diversity in the exploration partition", () => {
  const exploration = {
    profile_id: "test-profile",
    evaluation_k: 3,
    required_subject_event: "broad discovery theme",
    required_information_type: "open visual exploration",
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
  };
  const item = record(
    "explore",
    "exploration",
    ["template-vocabulary", "template-recipe", "template-travel"],
    {
      partition: "exploration",
      split: "exploration",
      transformations: ["open_ended_exploration"],
      exploration,
    },
  );
  const diverse = prediction("explore", [
    "template-vocabulary",
    "template-recipe",
    "template-travel",
  ]);
  const diverseMetric = explorationRecordMetrics(item, diverse);
  assert.equal(diverseMetric.relevant_count, 3);
  assert.equal(diverseMetric.distinct_relevant_style_count, 3);
  assert.ok(
    Math.abs(diverseMetric.relevant_effective_style_count - 3) < 1e-12,
  );

  const mostlyIrrelevant = prediction("explore", [
    "template-vocabulary",
    "template-product-poster",
    "template-fashion-inspired-gown-design-sheet",
  ]);
  assert.equal(
    explorationRecordMetrics(item, mostlyIrrelevant)
      .relevant_effective_style_count,
    1 / 3,
  );

  const result = scoreDataset({
    records: [item],
    predictions: [diverse],
    config,
  });
  assert.ok(
    Math.abs(
      result.metrics.exploration.relevant_effective_style_count_at_k.value -
        3,
    ) < 1e-12,
  );
  assert.equal(
    result.sliceMetrics.find(
      (row) => row.dimension === "partition" && row.value === "exploration",
    ).exact_accuracy,
    null,
  );
  assert.equal(result.errors.length, 0);
});

module.exports = { prediction, record };
