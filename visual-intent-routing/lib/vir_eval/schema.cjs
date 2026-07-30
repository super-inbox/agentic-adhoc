"use strict";

const { loadJson, nowIso, slug } = require("./common.cjs");

const ENUMS = {
  partition: new Set(["core", "content_gap", "challenge"]),
  split: new Set(["anchor", "dev", "test", "challenge", "candidate"]),
  challenge_type: new Set([
    null,
    "ambiguous",
    "boundary",
    "multi_intent",
    "conflicting_style_information",
    "supported_plus_unsupported",
    "mixed_language_noisy",
  ]),
  language: new Set(["zh", "en", "mixed"]),
  difficulty: new Set(["low", "medium", "high"]),
  target_mode: new Set(["single", "multi", "none", "ambiguous"]),
  validation_status: new Set([
    "pending",
    "auto_accepted",
    "needs_review",
    "approved",
    "rejected",
  ]),
};

const REQUIRED_TOP_LEVEL = [
  "id",
  "benchmark_version",
  "source_seed_id",
  "semantic_cluster_id",
  "partition",
  "challenge_type",
  "subject",
  "query",
  "language",
  "difficulty",
  "transformation_types",
  "ontology",
  "gold",
  "provenance",
  "validation",
];

function loadSeeds(filePath) {
  const seeds = loadJson(filePath);
  if (!Array.isArray(seeds)) throw new Error("Seed data must be a JSON array");
  const ids = new Set();
  for (const seed of seeds) {
    for (const field of [
      "seed_id",
      "subject",
      "query",
      "seed_language",
      "seed_difficulty",
      "gold_targets",
    ]) {
      if (!(field in seed)) throw new Error(`${seed.seed_id}: missing ${field}`);
    }
    if (ids.has(seed.seed_id)) throw new Error(`Duplicate seed: ${seed.seed_id}`);
    ids.add(seed.seed_id);
  }
  return seeds;
}

function validateRecord(record, registry) {
  const errors = [];
  const warnings = [];
  for (const field of REQUIRED_TOP_LEVEL) {
    if (!(field in record)) errors.push(`missing ${field}`);
  }
  if (record.benchmark_version !== "vir-v2") {
    errors.push("benchmark_version must be vir-v2");
  }
  for (const key of [
    "partition",
    "language",
    "difficulty",
  ]) {
    if (!ENUMS[key].has(record[key])) errors.push(`invalid ${key}: ${record[key]}`);
  }
  if (record.split && !ENUMS.split.has(record.split)) {
    errors.push(`invalid split: ${record.split}`);
  }
  if (!ENUMS.challenge_type.has(record.challenge_type ?? null)) {
    errors.push(`invalid challenge_type: ${record.challenge_type}`);
  }
  if (typeof record.query !== "string" || !record.query.trim()) {
    errors.push("query must be a non-empty string");
  }
  if (!Array.isArray(record.transformation_types)) {
    errors.push("transformation_types must be an array");
  }
  for (const key of ["subject_event", "information_type", "style_layout"]) {
    if (typeof record.ontology?.[key] !== "string" || !record.ontology[key]) {
      errors.push(`ontology.${key} is required`);
    }
  }
  const gold = record.gold ?? {};
  if (!ENUMS.target_mode.has(gold.target_mode)) {
    errors.push(`invalid gold.target_mode: ${gold.target_mode}`);
  }
  if (!Array.isArray(gold.targets)) errors.push("gold.targets must be an array");
  if (!Array.isArray(gold.acceptable_target_sets)) {
    errors.push("gold.acceptable_target_sets must be an array");
  }
  for (const target of gold.targets ?? []) {
    if (!registry.has(target)) errors.push(`invalid target: ${target}`);
  }
  for (const [index, set] of (gold.acceptable_target_sets ?? []).entries()) {
    if (!Array.isArray(set) || !set.length) {
      errors.push(`acceptable_target_sets[${index}] must be non-empty`);
      continue;
    }
    for (const target of set) {
      if (!registry.has(target)) errors.push(`invalid acceptable target: ${target}`);
    }
  }
  if (gold.target_mode === "none") {
    if ((gold.targets ?? []).length) errors.push("none mode requires empty targets");
    if (gold.must_abstain !== true) errors.push("none mode must set must_abstain");
  } else if (gold.must_abstain === true) {
    errors.push(`${gold.target_mode} mode cannot require abstention`);
  }
  if (gold.target_mode === "single" && gold.targets?.length !== 1) {
    errors.push("single mode requires exactly one target");
  }
  if (
    gold.target_mode === "multi" &&
    gold.targets?.length < 2 &&
    !(gold.targets?.length === 1 && gold.unsupported_components?.length)
  ) {
    errors.push(
      "multi mode requires two targets, or one target plus an unsupported component",
    );
  }
  if (
    gold.target_mode === "ambiguous" &&
    !(gold.acceptable_target_sets ?? []).length
  ) {
    errors.push("ambiguous mode requires acceptable target sets");
  }
  if (
    record.partition === "content_gap" &&
    gold.target_mode !== "none"
  ) {
    errors.push("content_gap partition requires none mode");
  }
  if (
    record.partition !== "challenge" &&
    record.challenge_type !== null
  ) {
    errors.push("challenge_type is only valid in challenge partition");
  }
  if (
    record.partition === "challenge" &&
    !record.challenge_type
  ) {
    errors.push("challenge partition requires challenge_type");
  }
  if (!ENUMS.validation_status.has(record.validation?.status)) {
    errors.push(`invalid validation.status: ${record.validation?.status}`);
  }
  return { valid: errors.length === 0, errors, warnings };
}

function anchorRecord(seed, registry, { randomSeed = 1234 } = {}) {
  const target = seed.gold_targets[0] ?? null;
  const capability = target ? registry.get(target) : null;
  return {
    id: `vir-v2-anchor-${seed.seed_id}`,
    benchmark_version: "vir-v2",
    source_seed_id: seed.seed_id,
    semantic_cluster_id: `anchor-${seed.seed_id}`,
    partition: target ? "core" : "content_gap",
    split: "anchor",
    challenge_type: null,
    subject: seed.subject,
    query: seed.query,
    language: seed.seed_language,
    difficulty: seed.seed_difficulty,
    transformation_types: ["manual_anchor"],
    ontology: capability?.ontology ?? {
      subject_event: "identity or passport portrait",
      information_type: "portrait creation or retouching",
      style_layout: "official ID-photo crop",
    },
    gold: {
      target_mode: target ? "single" : "none",
      targets: target ? [target] : [],
      acceptable_target_sets: [],
      must_abstain: !target,
    },
    provenance: {
      generation_method: "manual",
      generator_model: null,
      generator_prompt_version: "manual-anchor-v1",
      random_seed: randomSeed,
      generated_at: "2026-07-29T00:00:00.000Z",
    },
    validation: {
      status: "approved",
      validator_model: null,
      validator_prompt_version: null,
      validator_prompt_hash: null,
      target_consistency: true,
      competing_targets: [],
      rationale: "Manually selected anchor supplied as authoritative vir-v2 input.",
      raw_output: null,
    },
  };
}

function makeRecord({
  id,
  seed,
  clusterId,
  partition,
  challengeType = null,
  query,
  language,
  difficulty,
  transformations,
  ontology,
  gold,
  randomSeed,
  generationMethod = "rule",
  promptVersion = "vir-query-expander-v1",
  generatedAt = "2026-07-29T00:00:00.000Z",
}) {
  return {
    id,
    benchmark_version: "vir-v2",
    source_seed_id: seed?.seed_id ?? null,
    semantic_cluster_id: clusterId,
    partition,
    split: "candidate",
    challenge_type: challengeType,
    subject: seed?.subject ?? ontology.subject_event,
    query,
    language,
    difficulty,
    transformation_types: transformations,
    ontology,
    gold,
    provenance: {
      generation_method: generationMethod,
      generator_model: null,
      generator_prompt_version: promptVersion,
      random_seed: randomSeed,
      generated_at: generatedAt,
    },
    validation: {
      status: "pending",
      validator_model: null,
      validator_prompt_version: null,
      validator_prompt_hash: null,
      target_consistency: null,
      competing_targets: [],
      rationale: null,
      raw_output: null,
    },
  };
}

module.exports = {
  ENUMS,
  anchorRecord,
  loadSeeds,
  makeRecord,
  validateRecord,
};
