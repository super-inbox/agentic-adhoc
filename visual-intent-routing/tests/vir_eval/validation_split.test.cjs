"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { loadConfig, loadJson } = require("../../lib/vir_eval/common.cjs");
const { loadRegistry } = require("../../lib/vir_eval/registry.cjs");
const { anchorRecord, loadSeeds } = require("../../lib/vir_eval/schema.cjs");
const {
  findNearDuplicates,
  validateDataset,
} = require("../../lib/vir_eval/validate.cjs");
const { CharacterNgramSimilarity } = require("../../lib/vir_eval/similarity.cjs");
const {
  auditSplitLeakage,
  splitRecords,
} = require("../../lib/vir_eval/split.cjs");

const config = loadConfig("benchmarks/vir_v2/configs/default.yaml");
const registry = loadRegistry(config.paths.registry, config.paths.catalog);
const seeds = loadSeeds(config.paths.seeds);
const capabilityKb = loadJson(config.paths.capability_kb);

function candidate(seedIndex, id, query, cluster) {
  const record = anchorRecord(seeds[seedIndex], registry);
  record.id = id;
  record.query = query;
  record.semantic_cluster_id = cluster;
  record.split = "candidate";
  record.provenance.generation_method = "rule";
  record.validation.status = "pending";
  return record;
}

test("deterministic validation catches duplicate and contradictory records", () => {
  const left = candidate(0, "left", "中英水果词汇卡", "a");
  const right = candidate(0, "right", "中英水果词汇卡", "b");
  right.gold.targets = ["template-travel"];
  const result = validateDataset({
    records: [left, right],
    registry,
    capabilityKb,
    config,
    writeOutputs: false,
  });
  assert.equal(result.summary.exact_duplicates.length, 1);
  assert.equal(result.summary.contradictory_annotations.length, 1);
  assert.equal(
    result.records.every((record) => record.validation.status === "rejected"),
    true,
  );
});

test("near-duplicate detector distinguishes semantic clusters", () => {
  const records = [
    candidate(0, "a", "Create English Spanish fruit vocabulary cards", "x"),
    candidate(0, "b", "Create English-Spanish fruits vocabulary cards", "y"),
  ];
  const duplicates = findNearDuplicates(
    records,
    0.65,
    new CharacterNgramSimilarity(),
  );
  assert.equal(duplicates.length, 1);
  assert.equal(duplicates[0].same_semantic_cluster, false);
});

test("cluster-aware split keeps variants together and audits leakage", () => {
  const records = [
    candidate(0, "a1", "English Spanish fruit vocabulary cards", "cluster-a"),
    candidate(0, "a2", "英西水果词汇卡", "cluster-a"),
    candidate(0, "b1", "English Korean weather vocabulary", "cluster-b"),
    candidate(0, "b2", "英韩天气词汇", "cluster-b"),
  ];
  for (const record of records) record.validation.status = "auto_accepted";
  const result = splitRecords(records, {
    seed: 44,
    devFraction: 0.5,
    threshold: 0.9,
  });
  for (const cluster of ["cluster-a", "cluster-b"]) {
    const splits = new Set([
      ...result.dev
        .filter((record) => record.semantic_cluster_id === cluster)
        .map((record) => record.split),
      ...result.test
        .filter((record) => record.semantic_cluster_id === cluster)
        .map((record) => record.split),
    ]);
    assert.equal(splits.size, 1);
  }
  assert.equal(auditSplitLeakage(result.dev, result.test, 0.9).length, 0);
  assert.equal(
    auditSplitLeakage([records[0]], [{ ...records[0], id: "copy" }], 0.9)
      .length,
    1,
  );
});

test("exploration records stay in a separate split and cannot change dev/test", () => {
  const core = [
    candidate(0, "core-a", "English Spanish fruit vocabulary cards", "a"),
    candidate(0, "core-b", "English Korean weather vocabulary", "b"),
  ];
  const exploration = candidate(
    0,
    "exploration-a",
    "Explore several directions for a language-learning food story",
    "exploration-cluster",
  );
  exploration.partition = "exploration";
  exploration.gold = {
    target_mode: "exploration",
    targets: ["template-vocabulary", "template-recipe"],
    acceptable_target_sets: [],
    must_abstain: false,
    exploration: {
      profile_id: "split-test",
      evaluation_k: 3,
      required_subject_event: "language and food",
      required_information_type: "open exploration",
      target_style_families: {
        "template-vocabulary": "illustrated-flashcard",
        "template-recipe": "food-photography",
      },
      target_layout_families: {
        "template-vocabulary": "card-grid",
        "template-recipe": "recipe-poster",
      },
      acceptable_visual_style_families: [
        "illustrated-flashcard",
        "food-photography",
      ],
    },
  };
  for (const record of [...core, exploration]) {
    record.validation.status = "auto_accepted";
  }
  const withoutExploration = splitRecords(core, {
    seed: 1234,
    devFraction: 0.5,
    threshold: 0.9,
  });
  const withExploration = splitRecords([...core, exploration], {
    seed: 1234,
    devFraction: 0.5,
    threshold: 0.9,
  });
  assert.deepEqual(withExploration.dev, withoutExploration.dev);
  assert.deepEqual(withExploration.test, withoutExploration.test);
  assert.equal(withExploration.exploration.length, 1);
  assert.equal(withExploration.exploration[0].split, "exploration");
});
