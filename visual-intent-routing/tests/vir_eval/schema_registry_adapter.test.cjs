"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const path = require("node:path");

const { loadConfig } = require("../../lib/vir_eval/common.cjs");
const {
  loadRegistry,
  validateRegistry,
} = require("../../lib/vir_eval/registry.cjs");
const {
  anchorRecord,
  loadSeeds,
  validateRecord,
} = require("../../lib/vir_eval/schema.cjs");
const {
  RouterOutputError,
  normalizeRouterOutput,
} = require("../../lib/vir_eval/adapters.cjs");

const config = loadConfig("benchmarks/vir_v2/configs/default.yaml");
const seeds = loadSeeds(config.paths.seeds);
const registry = loadRegistry(config.paths.registry, config.paths.catalog);

test("loads all 16 supplied anchors exactly and traceably", () => {
  assert.equal(seeds.length, 16);
  assert.deepEqual(seeds[0], {
    seed_id: "vir-s01",
    subject: "vocabulary",
    query: "单词",
    seed_language: "zh",
    seed_difficulty: "high",
    gold_targets: ["template-vocabulary"],
  });
  assert.deepEqual(seeds[15], {
    seed_id: "vir-s16",
    subject: "content-gap",
    query: "证件照",
    seed_language: "zh",
    seed_difficulty: "medium",
    gold_targets: [],
    expected_abstention: true,
  });
  const anchor = anchorRecord(seeds[15], registry);
  assert.equal(anchor.source_seed_id, "vir-s16");
  assert.equal(anchor.query, "证件照");
  assert.equal(anchor.gold.target_mode, "none");
  assert.equal(anchor.validation.status, "approved");
});

test("registry canonicalizes canonical and historical IDs", () => {
  assert.equal(
    registry.canonicalize("template-travel-zh"),
    "template-travel",
  );
  assert.equal(
    registry.canonicalize("template-travel"),
    "template-travel",
  );
  assert.equal(registry.canonicalize("template-not-real"), null);
  const validation = validateRegistry(registry);
  assert.equal(validation.valid, true);
  assert.equal(validation.template_count, 15);
});

test("schema validates a correct record and rejects an invalid target", () => {
  const record = anchorRecord(seeds[0], registry);
  assert.equal(validateRecord(record, registry).valid, true);
  const invalid = structuredClone(record);
  invalid.gold.targets = ["template-not-real"];
  const result = validateRecord(invalid, registry);
  assert.equal(result.valid, false);
  assert.match(result.errors.join(" "), /invalid target/);
});

test("normalizer aliases IDs and validates rank/score shape", () => {
  const prediction = normalizeRouterOutput({
    queryId: "q1",
    registry,
    raw: {
      predictions: [
        { template_id: "template-travel-zh", score: 0.8, rank: 1 },
      ],
      abstained: false,
    },
  });
  assert.equal(prediction.predictions[0].template_id, "template-travel");
  assert.equal(prediction.predictions[0].score, 0.8);
});

test("unknown, duplicate, malformed, and unmarked empty outputs fail visibly", () => {
  assert.throws(
    () =>
      normalizeRouterOutput({
        queryId: "q",
        registry,
        raw: {
          predictions: [
            { template_id: "template-not-real", score: 0.7, rank: 1 },
          ],
          abstained: false,
        },
      }),
    (error) =>
      error instanceof RouterOutputError && error.code === "UNKNOWN_TEMPLATE",
  );
  assert.throws(
    () =>
      normalizeRouterOutput({
        queryId: "q",
        registry,
        raw: {
          predictions: [
            { template_id: "template-travel", score: 0.7, rank: 1 },
            { template_id: "template-travel-zh", score: 0.6, rank: 2 },
          ],
          abstained: false,
        },
      }),
    /duplicate template/i,
  );
  assert.throws(
    () =>
      normalizeRouterOutput({
        queryId: "q",
        registry,
        raw: {
          predictions: [
            { template_id: "template-travel", score: 2, rank: 1 },
          ],
          abstained: false,
        },
      }),
    /malformed score/i,
  );
  assert.throws(
    () =>
      normalizeRouterOutput({
        queryId: "q",
        registry,
        raw: { predictions: [] },
      }),
    (error) => error.code === "UNMARKED_EMPTY_RESULT",
  );
});
