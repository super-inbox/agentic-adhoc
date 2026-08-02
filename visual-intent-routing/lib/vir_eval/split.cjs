"use strict";

const fs = require("fs");
const path = require("path");
const {
  hashObject,
  resolveRoot,
  normalizeQuery,
  sha256,
  sha256File,
  shuffle,
  writeJson,
  writeJsonl,
} = require("./common.cjs");
const { CharacterNgramSimilarity } = require("./similarity.cjs");
const { anchorRecord } = require("./schema.cjs");

class UnionFind {
  constructor(values) {
    this.parent = new Map(values.map((value) => [value, value]));
  }

  find(value) {
    let parent = this.parent.get(value);
    if (parent !== value) {
      parent = this.find(parent);
      this.parent.set(value, parent);
    }
    return parent;
  }

  union(left, right) {
    const a = this.find(left);
    const b = this.find(right);
    if (a !== b) this.parent.set(b, a);
  }
}

function recordTarget(record) {
  return record.gold.targets[0] ?? "__none__";
}

function buildLeakageComponents(records, threshold) {
  const similarity = new CharacterNgramSimilarity();
  const uf = new UnionFind(records.map((record) => record.id));
  const byCluster = new Map();
  for (const record of records) {
    byCluster.set(record.semantic_cluster_id, [
      ...(byCluster.get(record.semantic_cluster_id) ?? []),
      record,
    ]);
  }
  for (const group of byCluster.values()) {
    for (let index = 1; index < group.length; index += 1) {
      uf.union(group[0].id, group[index].id);
    }
  }
  for (let left = 0; left < records.length; left += 1) {
    for (let right = left + 1; right < records.length; right += 1) {
      const a = records[left];
      const b = records[right];
      if (uf.find(a.id) === uf.find(b.id)) continue;
      if (
        normalizeQuery(a.query) === normalizeQuery(b.query) ||
        similarity.similarity(a.query, b.query) >= threshold
      ) {
        uf.union(a.id, b.id);
      }
    }
  }
  const components = new Map();
  for (const record of records) {
    const root = uf.find(record.id);
    components.set(root, [...(components.get(root) ?? []), record]);
  }
  return [...components.values()];
}

function componentBucket(component) {
  const targets = {};
  for (const record of component) {
    const target = recordTarget(record);
    targets[target] = (targets[target] ?? 0) + 1;
  }
  return Object.entries(targets).sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
  )[0][0];
}

function splitRecords(records, { seed = 1234, devFraction = 0.5, threshold = 0.88 } = {}) {
  const eligible = records.filter(
    (record) =>
      !["challenge", "exploration"].includes(record.partition) &&
      record.validation.status !== "rejected",
  );
  const challenges = records
    .filter(
      (record) =>
        record.partition === "challenge" &&
        record.validation.status !== "rejected",
    )
    .map((record) => ({ ...record, split: "challenge" }));
  const exploration = records
    .filter(
      (record) =>
        record.partition === "exploration" &&
        record.validation.status !== "rejected",
    )
    .map((record) => ({ ...record, split: "exploration" }));
  const components = buildLeakageComponents(eligible, threshold);
  const buckets = new Map();
  for (const component of components) {
    const bucket = componentBucket(component);
    buckets.set(bucket, [...(buckets.get(bucket) ?? []), component]);
  }
  const dev = [];
  const test = [];
  for (const [bucket, bucketComponents] of [...buckets.entries()].sort()) {
    const bucketSeed =
      seed +
      [...bucket].reduce((total, char) => total + char.codePointAt(0), 0);
    const ordered = shuffle(bucketComponents, bucketSeed);
    let devCount = 0;
    let testCount = 0;
    for (const component of ordered) {
      const totalAfter = devCount + testCount + component.length;
      const desiredDev = totalAfter * devFraction;
      const assignDev =
        devCount < desiredDev ||
        (devCount === testCount && hashObject(component.map((r) => r.id))[0] < "8");
      const destination = assignDev ? dev : test;
      for (const record of component) {
        destination.push({ ...record, split: assignDev ? "dev" : "test" });
      }
      if (assignDev) devCount += component.length;
      else testCount += component.length;
    }
  }
  return {
    dev: dev.sort((a, b) => a.id.localeCompare(b.id)),
    test: test.sort((a, b) => a.id.localeCompare(b.id)),
    challenge: challenges.sort((a, b) => a.id.localeCompare(b.id)),
    exploration: exploration.sort((a, b) => a.id.localeCompare(b.id)),
    component_count: components.length,
  };
}

function auditSplitLeakage(dev, test, threshold = 0.88) {
  const similarity = new CharacterNgramSimilarity();
  const collisions = [];
  for (const left of dev) {
    for (const right of test) {
      const exact = normalizeQuery(left.query) === normalizeQuery(right.query);
      const score = exact ? 1 : similarity.similarity(left.query, right.query);
      if (score >= threshold) {
        collisions.push({
          dev_id: left.id,
          test_id: right.id,
          similarity: Number(score.toFixed(4)),
          same_semantic_cluster:
            left.semantic_cluster_id === right.semantic_cluster_id,
        });
      }
    }
  }
  return collisions;
}

function countBy(records, getter) {
  const counts = {};
  for (const record of records) {
    const values = getter(record);
    for (const value of Array.isArray(values) ? values : [values]) {
      counts[value] = (counts[value] ?? 0) + 1;
    }
  }
  return counts;
}

function splitDistributions(records) {
  return {
    target: countBy(records, (record) =>
      record.gold.targets.length ? record.gold.targets : ["__none__"],
    ),
    language: countBy(records, (record) => record.language),
    difficulty: countBy(records, (record) => record.difficulty),
    transformation_type: countBy(
      records,
      (record) => record.transformation_types,
    ),
  };
}

function createSplits({ config, seeds, registry, records, writeOutputs = true }) {
  const anchors = seeds.map((seed) =>
    anchorRecord(seed, registry, { randomSeed: config.random_seed }),
  );
  const result = splitRecords(records, {
    seed: config.random_seed,
    devFraction: config.split.dev_fraction,
    threshold: config.validation.split_leakage_threshold,
  });
  const leakage = auditSplitLeakage(
    result.dev,
    result.test,
    config.validation.split_leakage_threshold,
  );
  if (leakage.length) {
    throw new Error(
      `Post-split leakage audit found ${leakage.length} dev/test collisions`,
    );
  }
  const paths = {
    anchor: path.join(config.paths.split_dir, "anchor.jsonl"),
    dev: path.join(config.paths.split_dir, "dev.jsonl"),
    test: path.join(config.paths.split_dir, "test.jsonl"),
    challenge: path.join(config.paths.split_dir, "challenge.jsonl"),
    exploration: path.join(config.paths.split_dir, "exploration.jsonl"),
  };
  if (writeOutputs) {
    writeJsonl(paths.anchor, anchors);
    writeJsonl(paths.dev, result.dev);
    writeJsonl(paths.test, result.test);
    writeJsonl(paths.challenge, result.challenge);
    writeJsonl(paths.exploration, result.exploration);
  }
  const testBody = result.test.map((record) => JSON.stringify(record)).join("\n");
  const explorationBody = result.exploration
    .map((record) => JSON.stringify(record))
    .join("\n");
  const expansionSummaryPath = resolveRoot(
    path.join(config.paths.manifest_dir, "expansion_summary.json"),
  );
  const expansionSummary = fs.existsSync(expansionSummaryPath)
    ? JSON.parse(fs.readFileSync(expansionSummaryPath, "utf8"))
    : null;
  const gapAuditPath = config.paths.full_catalog_gap_audit
    ? resolveRoot(config.paths.full_catalog_gap_audit)
    : null;
  const gapAudit =
    gapAuditPath && fs.existsSync(gapAuditPath)
      ? JSON.parse(fs.readFileSync(gapAuditPath, "utf8"))
      : null;
  const statusCounts = {};
  for (const record of records) {
    statusCounts[record.validation.status] =
      (statusCounts[record.validation.status] ?? 0) + 1;
  }
  const manifest = {
    benchmark_version: config.benchmark_version,
    template_registry_version: registry.document.registry_version,
    created_at: "2026-07-29T00:00:00.000Z",
    random_seed: config.random_seed,
    creation_configuration: {
      expansion: config.expansion,
      split: config.split,
      validation: config.validation,
      full_catalog_gap_audit: gapAudit
        ? {
            audit_version: gapAudit.audit_version,
            source_catalog_sha256:
              gapAudit.source_evidence?.catalog_sha256 ?? null,
          }
        : null,
    },
    creation_configuration_sha256: hashObject({
      expansion: config.expansion,
      split: config.split,
      validation: config.validation,
      full_catalog_gap_audit_version: gapAudit?.audit_version ?? null,
    }),
    locked_test: config.split.locked_test,
    counts: {
      anchor: anchors.length,
      dev: result.dev.length,
      test: result.test.length,
      challenge: result.challenge.length,
      exploration: result.exploration.length,
    },
    dataset_counts: {
      requested: expansionSummary?.requested?.total ?? null,
      generated: expansionSummary?.generated?.total ?? records.length,
      rejected: statusCounts.rejected ?? 0,
      needs_review: statusCounts.needs_review ?? 0,
      auto_accepted: statusCounts.auto_accepted ?? 0,
      manually_approved: anchors.length,
    },
    distributions: {
      dev: splitDistributions(result.dev),
      test: splitDistributions(result.test),
      exploration: splitDistributions(result.exploration),
    },
    test_file: paths.test,
    test_file_sha256: writeOutputs
      ? sha256File(paths.test)
      : sha256(testBody ? `${testBody}\n` : ""),
    exploration_file: paths.exploration,
    exploration_file_sha256: writeOutputs
      ? sha256File(paths.exploration)
      : sha256(explorationBody ? `${explorationBody}\n` : ""),
    exploration_profiles_sha256: sha256File(
      config.paths.exploration_profiles,
    ),
    registry_sha256: hashObject(registry.document),
    post_split_similarity_audit: {
      layer: "character-3gram-jaccard",
      threshold: config.validation.split_leakage_threshold,
      collision_count: leakage.length,
      collisions: leakage,
    },
    note: "Do not tune routing rules or abstention thresholds on this locked test manifest.",
  };
  if (writeOutputs) {
    writeJson(path.join(config.paths.manifest_dir, "test_manifest.json"), manifest);
    writeJson(
      path.join(config.paths.manifest_dir, "benchmark_manifest.json"),
      manifest,
    );
  }
  return { anchors, ...result, leakage, manifest };
}

module.exports = {
  auditSplitLeakage,
  buildLeakageComponents,
  createSplits,
  splitDistributions,
  splitRecords,
};
