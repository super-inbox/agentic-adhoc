#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const {
  hashObject,
  loadConfig,
  loadJson,
  readJsonl,
  resolveRoot,
  writeJson,
  writeJsonl,
} = require("../lib/vir_eval/common.cjs");
const {
  buildRegistry,
  loadRegistry,
  validateRegistry,
} = require("../lib/vir_eval/registry.cjs");
const { loadSeeds } = require("../lib/vir_eval/schema.cjs");
const { expandDataset } = require("../lib/vir_eval/expand.cjs");
const {
  validateDataset,
  validateWithLlm,
  writeCsv,
} = require("../lib/vir_eval/validate.cjs");
const { createSplits } = require("../lib/vir_eval/split.cjs");
const { createAdapter } = require("../lib/vir_eval/adapters.cjs");
const { loadRunRecords, runRouter } = require("../lib/vir_eval/runner.cjs");
const { scoreDataset } = require("../lib/vir_eval/metrics.cjs");
const {
  flattenNumeric,
  generateReports,
} = require("../lib/vir_eval/reporting.cjs");
const {
  compareRuns,
  writeComparison,
} = require("../lib/vir_eval/compare.cjs");

const DEFAULT_CONFIG = "benchmarks/vir_v2/configs/default.yaml";

function parseArgs(argv) {
  const command = argv[0] && !argv[0].startsWith("--") ? argv[0] : "help";
  const start = command === "help" && argv[0]?.startsWith("--") ? 0 : 1;
  const options = {};
  for (let index = start; index < argv.length; index += 1) {
    const argument = argv[index];
    if (!argument.startsWith("--")) continue;
    const equal = argument.indexOf("=");
    if (equal > 0) {
      options[argument.slice(2, equal).replace(/-/g, "_")] =
        argument.slice(equal + 1);
      continue;
    }
    const key = argument.slice(2).replace(/-/g, "_");
    const next = argv[index + 1];
    if (next && !next.startsWith("--")) {
      options[key] = next;
      index += 1;
    } else {
      options[key] = true;
    }
  }
  return { command, options };
}

function context(options) {
  const config = loadConfig(options.config ?? DEFAULT_CONFIG);
  const seeds = loadSeeds(config.paths.seeds);
  const registry = loadRegistry(config.paths.registry, config.paths.catalog);
  return { config, seeds, registry };
}

function loadCandidateRecords(config) {
  return ["core", "content_gap", "challenge", "exploration"].flatMap((name) =>
    readJsonl(path.join(config.paths.candidate_dir, `${name}.jsonl`)),
  );
}

function loadValidatedRecords(config) {
  return ["core", "content_gap", "challenge", "exploration"].flatMap((name) =>
    readJsonl(path.join(config.paths.validated_dir, `${name}.jsonl`)),
  );
}

function routerOverrides(options) {
  const overrides = {};
  if (options.adapter) overrides.adapter = options.adapter;
  if (options.url) overrides.url = options.url;
  if (options.command) overrides.command = options.command;
  if (options.command_args) overrides.args = JSON.parse(options.command_args);
  if (options.module_path) overrides.module_path = options.module_path;
  if (options.export_name) overrides.export_name = options.export_name;
  if (options.abstention_threshold) {
    overrides.abstention_threshold = Number(options.abstention_threshold);
  }
  if (options.top_k) overrides.top_k = Number(options.top_k);
  return overrides;
}

function expansionOverrides(options) {
  const output = {};
  for (const [option, field] of [
    ["core_per_target", "core_per_target"],
    ["content_gap", "content_gap"],
    ["ambiguous", "ambiguous"],
    ["multi_intent", "multi_intent"],
    ["exploration", "exploration"],
  ]) {
    if (options[option] !== undefined) output[field] = Number(options[option]);
  }
  return output;
}

function inspectStage({ config, seeds, registry }) {
  const catalog = loadJson(config.paths.catalog);
  const kb = loadJson(config.paths.capability_kb);
  const explorationProfiles = loadJson(config.paths.exploration_profiles);
  const gapAudit = config.paths.full_catalog_gap_audit
    ? loadJson(config.paths.full_catalog_gap_audit)
    : null;
  const validation = validateRegistry(registry);
  const idPhoto = catalog.filter(
    (template) =>
      template.id === "template-portrait-retouching-blueprint" ||
      /(?:^|-)id-photo(?:-|$)|passport-photo/.test(template.id),
  );
  const output = {
    benchmark_version: config.benchmark_version,
    anchor_count: seeds.length,
    positive_anchor_count: seeds.filter((seed) => seed.gold_targets.length).length,
    abstention_anchor_count: seeds.filter((seed) => !seed.gold_targets.length)
      .length,
    registry_template_count: registry.templates.length,
    exploration: {
      profile_count: explorationProfiles.length,
      default_query_count: config.expansion.exploration,
      evaluation_k: config.metrics.exploration_k,
      headline_metric: "Relevant Effective Style Count@K",
      excluded_from_primary_core_accuracy: true,
    },
    registry_validation: validation,
    frozen_catalog: {
      template_count: catalog.length,
      generatable_count: catalog.filter(
        (template) => template.allow_generation === true,
      ).length,
      capability_kb_count: kb.templates?.length ?? 0,
    },
    current_full_catalog_audit: gapAudit
      ? {
          audit_version: gapAudit.audit_version,
          template_count: gapAudit.source_evidence.template_count,
          generatable_count:
            gapAudit.source_evidence.allow_generation_count,
          catalog_sha256: gapAudit.source_evidence.catalog_sha256,
          audited_gap_subjects: gapAudit.capability_checks.length,
        }
      : null,
    current_router_contract: {
      production_evidence:
        "../../curify-frontend/lib/searchTemplateMatch.ts and app/api/search-template-match/route.ts",
      normalized_adapters: ["module", "cli-jsonl", "http", "mock"],
    },
    known_conflicts: [
      "v1 is a Claude draft with multi-valid labels; v2 preserves the supplied single-target anchors separately.",
      "No dedicated text-only ID-photo template exists. An upload-only portrait-retouching blueprint is adjacent; production explicitly abstains in text-only planning.",
      "The interior mood-board catalog entry requires an uploaded reference image downstream, but remains the supplied routing target.",
    ],
    id_photo_related_catalog_entries: idPhoto.map((template) => ({
      id: template.id,
      allow_generation: template.allow_generation ?? false,
      requires_image_upload: template.requires_image_upload ?? false,
    })),
  };
  console.log(JSON.stringify(output, null, 2));
  return output;
}

function buildRegistryStage(ctx) {
  const result = buildRegistry(ctx.config);
  console.log(
    `Registry valid: ${result.validation.template_count} templates, ${result.validation.alias_count} aliases`,
  );
  return result;
}

async function expandStage(ctx, options) {
  const result = await expandDataset({
    ...ctx,
    provider: options.provider,
    dryRun: Boolean(options.dry_run),
    resume: !options.no_resume,
    quotas: expansionOverrides(options),
  });
  console.log(JSON.stringify(result.summary, null, 2));
  return result;
}

async function validateStage(ctx, options = {}) {
  const records = loadCandidateRecords(ctx.config);
  if (!records.length) throw new Error("No candidate data; run expand first");
  const result = validateDataset({
    records,
    registry: ctx.registry,
    capabilityKb: loadJson(ctx.config.paths.capability_kb),
    gapAudit: ctx.config.paths.full_catalog_gap_audit
      ? loadJson(ctx.config.paths.full_catalog_gap_audit)
      : null,
    config: ctx.config,
  });
  if (options.llm_validator) {
    const eligible = result.records.filter(
      (record) => record.validation.status === "needs_review",
    );
    const limit = options.limit
      ? Math.min(eligible.length, Number(options.limit))
      : eligible.length;
    let accepted = 0;
    let rejected = 0;
    for (const record of eligible.slice(0, limit)) {
      const independent = await validateWithLlm({
        record,
        registry: ctx.registry,
        config: ctx.config,
        model: options.validator_model ?? ctx.config.expansion.model,
      });
      const parsed = independent.parsed ?? {};
      record.validation.validator_model = independent.model;
      record.validation.validator_prompt_version =
        independent.prompt_version;
      record.validation.validator_prompt_hash = independent.prompt_hash;
      record.validation.target_consistency =
        typeof parsed.target_consistency === "boolean"
          ? parsed.target_consistency
          : null;
      record.validation.competing_targets = Array.isArray(
        parsed.competing_targets,
      )
        ? parsed.competing_targets
        : [];
      record.validation.rationale =
        parsed.rationale ?? record.validation.rationale;
      record.validation.raw_output = independent.raw_output;
      if (parsed.decision === "rejected" || parsed.decision === "reject") {
        record.validation.status = "rejected";
        rejected += 1;
      } else if (
        parsed.decision === "accepted" ||
        parsed.decision === "accept"
      ) {
        // Independent acceptance is recorded, but is not promoted to manual
        // approval. It stays in the human queue.
        accepted += 1;
      }
    }
    for (const [name, rows] of Object.entries({
      core: result.records.filter((record) => record.partition === "core"),
      content_gap: result.records.filter(
        (record) => record.partition === "content_gap",
      ),
      challenge: result.records.filter(
        (record) => record.partition === "challenge",
      ),
      exploration: result.records.filter(
        (record) => record.partition === "exploration",
      ),
    })) {
      writeJsonl(
        path.join(ctx.config.paths.validated_dir, `${name}.jsonl`),
        rows,
      );
    }
    result.summary.independent_llm_validation = {
      requested: limit,
      accepted_but_still_needs_human_review: accepted,
      rejected,
      model: options.validator_model ?? ctx.config.expansion.model,
      prompt_version: ctx.config.validation.validator_prompt_version,
    };
    writeJson(
      path.join(ctx.config.paths.manifest_dir, "dataset_validation.json"),
      result.summary,
    );
  }
  console.log(
    JSON.stringify(
      {
        records: result.summary.record_count,
        valid: result.summary.valid,
        statuses: result.summary.status_counts,
        review_queue: result.reviewRows.length,
      },
      null,
      2,
    ),
  );
  return result;
}

function splitStage(ctx) {
  const records = loadValidatedRecords(ctx.config);
  if (!records.length) throw new Error("No validated data; run validate first");
  const result = createSplits({
    ...ctx,
    records,
  });
  console.log(
    JSON.stringify(
      {
        counts: result.manifest.counts,
        leakage_collisions: result.leakage.length,
        test_sha256: result.manifest.test_file_sha256,
      },
      null,
      2,
    ),
  );
  return result;
}

async function runStage(ctx, options) {
  const records = loadRunRecords(ctx.config);
  if (!records.length) throw new Error("No split data; run split first");
  const adapter = createAdapter(
    ctx.config,
    ctx.registry,
    routerOverrides(options),
  );
  const outPath = path.join(ctx.config.paths.report_dir, "predictions.jsonl");
  const result = await runRouter({
    records,
    adapter,
    outPath,
    resume: !options.no_resume,
    maxRetries: Number(options.retries ?? 0),
  });
  writeJson(
    path.join(ctx.config.paths.report_dir, "run_summary.json"),
    result.summary,
  );
  console.log(JSON.stringify(result.summary, null, 2));
  return { ...result, adapter, records };
}

function scoreStage(ctx) {
  const records = loadRunRecords(ctx.config);
  const predictions = readJsonl(
    path.join(ctx.config.paths.report_dir, "predictions.jsonl"),
  );
  if (!predictions.length) throw new Error("No predictions; run run first");
  const score = scoreDataset({ records, predictions, config: ctx.config });
  writeJson(path.join(ctx.config.paths.report_dir, "metrics.json"), score.metrics);
  writeJson(
    path.join(ctx.config.paths.report_dir, "slice_metrics.json"),
    score.sliceMetrics,
  );
  writeJson(
    path.join(ctx.config.paths.report_dir, "exploration_metrics.json"),
    {
      summary: score.metrics.exploration,
      records: score.explorationRows,
    },
  );
  writeCsv(
    path.join(ctx.config.paths.report_dir, "exploration_metrics.csv"),
    [
      "id",
      "query",
      "language",
      "difficulty",
      "semantic_cluster_id",
      "profile_id",
      "evaluation_k",
      "returned_count",
      "relevant_count",
      "relevance_at_k",
      "distinct_relevant_style_count",
      "distinct_relevant_layout_count",
      "style_entropy_nats",
      "effective_style_count",
      "relevant_effective_style_count",
      "relevant_template_ids",
      "predicted_template_ids",
      "style_distribution",
      "layout_distribution",
      "abstained",
    ],
    score.explorationRows,
  );
  writeCsv(
    path.join(ctx.config.paths.report_dir, "metrics.csv"),
    ["metric", "value"],
    flattenNumeric(score.metrics),
  );
  console.log(
    JSON.stringify(
      {
        top1:
          score.metrics.primary_core.positive_query_top1_exact_accuracy.value,
        overall:
          score.metrics.primary_core.overall_exact_accuracy_including_no_match
            .value,
        abstention_f1: score.metrics.content_gap.abstention_f1,
        exploration_k: score.metrics.exploration.evaluation_k,
        relevant_effective_style_count_at_k:
          score.metrics.exploration.relevant_effective_style_count_at_k.value,
        errors: score.errors.length,
      },
      null,
      2,
    ),
  );
  return { score, records, predictions };
}

function reportStage(ctx, adapterName = null) {
  const scored = scoreStage(ctx);
  const validation = loadJson(
    path.join(ctx.config.paths.manifest_dir, "dataset_validation.json"),
  );
  const benchmarkManifest = loadJson(
    path.join(ctx.config.paths.manifest_dir, "benchmark_manifest.json"),
  );
  const runSummaryPath = resolveRoot(
    path.join(ctx.config.paths.report_dir, "run_summary.json"),
  );
  const runSummary = fs.existsSync(runSummaryPath)
    ? JSON.parse(fs.readFileSync(runSummaryPath, "utf8"))
    : {};
  const result = generateReports({
    config: ctx.config,
    records: scored.records,
    predictions: scored.predictions,
    score: scored.score,
    validation,
    benchmarkManifest,
    adapterName: adapterName ?? runSummary.adapter ?? ctx.config.router.adapter,
  });
  console.log(JSON.stringify(result, null, 2));
  return result;
}

function compareStage(ctx, options) {
  if (!options.baseline) {
    throw new Error("compare requires --baseline=<report-directory>");
  }
  const baseline = resolveRoot(options.baseline);
  const current = resolveRoot(ctx.config.paths.report_dir);
  const records = loadRunRecords(ctx.config);
  const comparison = compareRuns({
    records,
    baselinePredictions: readJsonl(path.join(baseline, "predictions.jsonl")),
    currentPredictions: readJsonl(path.join(current, "predictions.jsonl")),
    baselineMetrics: JSON.parse(
      fs.readFileSync(path.join(baseline, "metrics.json"), "utf8"),
    ),
    currentMetrics: JSON.parse(
      fs.readFileSync(path.join(current, "metrics.json"), "utf8"),
    ),
    baselineSlices: JSON.parse(
      fs.readFileSync(path.join(baseline, "slice_metrics.json"), "utf8"),
    ),
    currentSlices: JSON.parse(
      fs.readFileSync(path.join(current, "slice_metrics.json"), "utf8"),
    ),
    config: ctx.config,
  });
  writeComparison(path.join(current, "comparison"), comparison);
  console.log(
    JSON.stringify(
      {
        paired: comparison.paired_record_count,
        fixed: comparison.newly_fixed_records.length,
        broken: comparison.newly_broken_records.length,
        gates_passed: comparison.gates_passed,
      },
      null,
      2,
    ),
  );
  if (!comparison.gates_passed) process.exitCode = 2;
  return comparison;
}

function help() {
  console.log(`VIR v2 evaluation CLI

Usage:
  node scripts/vir-eval.cjs <command> [--config ${DEFAULT_CONFIG}]

Commands:
  inspect          Inspect anchors, registry, catalog, and router contract
  build-registry   Validate the evidence-grounded registry
  expand           Build deterministic candidates (or --provider=llm)
  validate         Run schema, collision, duplicate, and Gold-quality checks
  split            Create anchor/dev/test/challenge/exploration splits
  run              Run --adapter=mock|http|cli|module and normalize outputs
  score            Compute deterministic metrics
  report           Generate machine-readable and human-readable reports
  compare          Compare against --baseline=<report-directory>
  all              Run build-registry through report

Useful options:
  --dry-run --no-resume --core-per-target=30 --content-gap=80
  --ambiguous=60 --multi-intent=60 --exploration=30
  --abstention-threshold=0.1
  --llm-validator [--validator-model=gpt-4o-mini] [--limit=20]
  --url=http://localhost:3000/api/search-template-match
  --command=python --command-args='["router.py"]'
`);
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  if (command === "help" || options.help) {
    help();
    return;
  }
  const ctx = context(options);
  switch (command) {
    case "inspect":
      inspectStage(ctx);
      break;
    case "build-registry":
      buildRegistryStage(ctx);
      break;
    case "expand":
      await expandStage(ctx, options);
      break;
    case "validate":
      await validateStage(ctx, options);
      break;
    case "split":
      splitStage(ctx);
      break;
    case "run":
      await runStage(ctx, options);
      break;
    case "score":
      scoreStage(ctx);
      break;
    case "report":
      reportStage(ctx);
      break;
    case "compare":
      compareStage(ctx, options);
      break;
    case "all": {
      buildRegistryStage(ctx);
      await expandStage(ctx, options);
      await validateStage(ctx, options);
      splitStage(ctx);
      const run = await runStage(ctx, options);
      reportStage(ctx, run.adapter.name);
      break;
    }
    default:
      throw new Error(`Unknown command: ${command}`);
  }
}

main().catch((error) => {
  console.error(`vir-eval: ${error.stack ?? error.message ?? error}`);
  process.exitCode = 1;
});

module.exports = {
  context,
  inspectStage,
  loadCandidateRecords,
  loadValidatedRecords,
  parseArgs,
};
