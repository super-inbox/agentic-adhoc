"use strict";

const fs = require("fs");
const path = require("path");
const {
  hashObject,
  loadJson,
  readJsonl,
  resolveRoot,
  writeJson,
  writeJsonl,
} = require("./common.cjs");
const { writeCsv } = require("./validate.cjs");

function flattenNumeric(value, prefix = "", output = []) {
  if (typeof value === "number" || value === null) {
    output.push({ metric: prefix, value });
  } else if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [key, child] of Object.entries(value)) {
      flattenNumeric(child, prefix ? `${prefix}.${key}` : key, output);
    }
  }
  return output;
}

function formatMetric(value) {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "object" && "value" in value) {
    const percent =
      value.value === null ? "n/a" : `${(value.value * 100).toFixed(2)}%`;
    if (value.interval?.lower !== null) {
      return `${percent} (95% CI ${(value.interval.lower * 100).toFixed(
        2,
      )}–${(value.interval.upper * 100).toFixed(2)}; n=${value.total})`;
    }
    return percent;
  }
  if (typeof value === "number") return value.toFixed(4);
  return String(value);
}

function distributionTable(distributions) {
  const lines = ["| Dimension | Value | Count |", "|---|---|---:|"];
  for (const [dimension, counts] of Object.entries(distributions ?? {})) {
    for (const [value, count] of Object.entries(counts)) {
      lines.push(`| ${dimension} | ${value} | ${count} |`);
    }
  }
  return lines.join("\n");
}

function examplesTable(rows, limit = 10) {
  if (!rows.length) return "_None._";
  const lines = [
    "| Query | Lang / difficulty | Transformations | Ontology | Gold | Predicted ranking | Confidence / closest competitor | Seed / status |",
    "|---|---|---|---|---|---|---|---|",
  ];
  for (const row of rows.slice(0, limit)) {
    const escapeCell = (value) =>
      String(value ?? "")
        .replace(/\|/g, "\\|")
        .replace(/\r?\n/g, " ");
    const ontology = [
      row.ontology?.subject_event,
      row.ontology?.information_type,
      row.ontology?.style_layout,
    ]
      .filter(Boolean)
      .join(" / ");
    const ranking = row.abstained
      ? "ABSTAIN"
      : row.predicted_ranking
          .map(
            (prediction) =>
              `${prediction.rank}:${prediction.template_id}${
                prediction.score === null || prediction.score === undefined
                  ? ""
                  : ` (${prediction.score})`
              }`,
          )
          .join(", ") || "ERROR";
    lines.push(
      `| ${escapeCell(row.query)} | ${row.language} / ${row.difficulty} | ${escapeCell(
        row.transformation_types.join(", "),
      )} | ${escapeCell(ontology)} | ${escapeCell(
        row.gold_targets.join(", ") || "ABSTAIN",
      )} | ${escapeCell(ranking)} | ${row.confidence ?? "n/a"} / ${escapeCell(
        row.closest_competing_template ?? "n/a",
      )} | ${row.source_seed_id ?? "generated"} / ${row.validation_status} |`,
    );
  }
  return lines.join("\n");
}

function renderReport({
  metrics,
  validation,
  benchmarkManifest,
  errors,
  confusion,
  records,
  runMetadata,
}) {
  const falseRouting = errors.filter(
    (row) => row.gold_mode === "none" && !row.abstained,
  );
  const falseAbstention = errors.filter(
    (row) => row.gold_mode !== "none" && row.abstained,
  );
  const topConfusions = confusion.filter(
    (row) => row.gold_template !== row.predicted_template,
  );
  const pending = records.filter(
    (record) => record.validation.status === "needs_review",
  ).length;
  const lines = [
    "# Visual Intent Routing v2 evaluation report",
    "",
    "## 1. Benchmark and run metadata",
    "",
    `- Benchmark: \`${metrics.benchmark_version}\``,
    `- Router adapter: \`${runMetadata.adapter}\``,
    `- Records evaluated: ${records.length}`,
    `- Run configuration hash: \`${runMetadata.configuration_hash}\``,
    `- Locked test SHA256: \`${benchmarkManifest.test_file_sha256}\``,
    `- Registry version: \`${benchmarkManifest.template_registry_version}\``,
    "",
    "This report evaluates query-to-template routing only. It does not judge generated-image quality.",
    "",
    "## 2. Dataset counts and distributions",
    "",
    `- Requested candidates: ${benchmarkManifest.dataset_counts?.requested ?? "n/a"}`,
    `- Generated candidates: ${benchmarkManifest.dataset_counts?.generated ?? "n/a"}`,
    `- Rejected: ${benchmarkManifest.dataset_counts?.rejected ?? 0}`,
    `- Needs review: ${benchmarkManifest.dataset_counts?.needs_review ?? 0}`,
    `- Auto-accepted: ${benchmarkManifest.dataset_counts?.auto_accepted ?? 0}`,
    `- Manually approved anchors: ${benchmarkManifest.dataset_counts?.manually_approved ?? 0}`,
    "",
    distributionTable(validation.distributions),
    "",
    "## 3. Validation warnings",
    "",
    `- Schema errors: ${validation.schema_errors.length}`,
    `- Rejected: ${validation.status_counts.rejected ?? 0}`,
    `- Needs human review: ${validation.status_counts.needs_review ?? 0}`,
    `- Auto-accepted (not human-approved): ${validation.status_counts.auto_accepted ?? 0}`,
    `- Near-duplicate pairs: ${validation.near_duplicates.length}`,
    `- Content-gap catalog-collision warnings: ${validation.content_gap_collisions.length}`,
    `- Full-catalog gap audit: ${validation.full_catalog_gap_audit?.audit_version ?? "not supplied"} (${validation.full_catalog_gap_audit?.source_template_count ?? "n/a"} templates; ${validation.full_catalog_gap_audit?.unaudited_record_ids?.length ?? "n/a"} unaudited records)`,
    `- Balance warnings: ${validation.balance_warnings.join("; ") || "none"}`,
    "",
    "## 4. Primary metrics",
    "",
    `- Positive top-1 exact accuracy: ${formatMetric(
      metrics.primary_core.positive_query_top1_exact_accuracy,
    )}`,
    `- Macro top-1 across templates: ${formatMetric(
      metrics.primary_core.macro_top1_accuracy_across_templates,
    )}`,
    `- Overall exact accuracy including no-match: ${formatMetric(
      metrics.primary_core.overall_exact_accuracy_including_no_match,
    )}`,
    `- Recall@3: ${formatMetric(metrics.primary_core.recall_at_3)}`,
    `- Recall@5: ${formatMetric(metrics.primary_core.recall_at_5)}`,
    `- MRR: ${formatMetric(metrics.primary_core.mean_reciprocal_rank)}`,
    "",
    "## 5. Content-gap results",
    "",
    `- Abstention precision: ${formatMetric(
      metrics.content_gap.abstention_precision,
    )}`,
    `- Abstention recall: ${formatMetric(metrics.content_gap.abstention_recall)}`,
    `- Abstention F1: ${formatMetric(metrics.content_gap.abstention_f1)}`,
    `- False-routing rate: ${formatMetric(
      metrics.content_gap.false_routing_rate_on_content_gap,
    )}`,
    `- False-abstention rate: ${formatMetric(
      metrics.content_gap.false_abstention_rate_on_supported,
    )}`,
    `- Match-confidence AUROC / AUPRC: ${formatMetric(
      metrics.content_gap.match_confidence_auroc,
    )} / ${formatMetric(metrics.content_gap.match_confidence_auprc)}`,
    "",
    "## 6. Robustness",
    "",
    `- Semantic-cluster consistency: ${formatMetric(
      metrics.robustness.semantic_cluster_prediction_consistency,
    )}`,
    `- Translation consistency: ${formatMetric(
      metrics.robustness.translation_consistency,
    )}`,
    `- Paraphrase consistency: ${formatMetric(
      metrics.robustness.paraphrase_consistency,
    )}`,
    `- Typo/noise accuracy: ${formatMetric(
      metrics.robustness.typo_noise_accuracy,
    )}`,
    `- Explicit-to-implicit drop: ${formatMetric(
      metrics.robustness.explicit_to_implicit.drop,
    )}`,
    "",
    "## 7. Language and difficulty gaps",
    "",
    `- Language accuracy: \`${JSON.stringify(
      metrics.robustness.language_accuracy,
    )}\``,
    `- Language gap: ${formatMetric(
      metrics.robustness.language_performance_gap,
    )}`,
    `- Difficulty accuracy: \`${JSON.stringify(
      metrics.robustness.difficulty_accuracy,
    )}\``,
    `- Low-to-high change: ${formatMetric(
      metrics.robustness.low_to_high_drop,
    )}`,
    "",
    "## 8. Per-template results",
    "",
    "See `slice_metrics.csv` rows where `dimension=template` for full counts and Wilson intervals.",
    "",
    "## 9. Top confusion pairs",
    "",
    "| Gold | Predicted | Count |",
    "|---|---|---:|",
    ...topConfusions
      .slice(0, 15)
      .map(
        (row) =>
          `| ${row.gold_template} | ${row.predicted_template} | ${row.count} |`,
      ),
    "",
    "## 10. False routing examples",
    "",
    examplesTable(falseRouting),
    "",
    "## 11. False abstention examples",
    "",
    examplesTable(falseAbstention),
    "",
    "## 12. Ambiguous and multi-intent challenges",
    "",
    `- Ambiguous acceptable-set match: ${formatMetric(
      metrics.challenges.ambiguous.acceptable_target_set_match_rate,
    )}`,
    `- Ambiguous abstention: ${formatMetric(
      metrics.challenges.ambiguous.abstention_rate,
    )}`,
    `- Multi exact set match: ${formatMetric(
      metrics.challenges.multi_intent.exact_set_match,
    )}`,
    `- Multi set precision / recall / F1: ${formatMetric(
      metrics.challenges.multi_intent.set_precision,
    )} / ${formatMetric(
      metrics.challenges.multi_intent.set_recall,
    )} / ${formatMetric(metrics.challenges.multi_intent.set_f1)}`,
    "",
    "Challenge results are excluded from primary core accuracy.",
    "",
    "## 13. Latency and system failures",
    "",
    `- Mean / median latency: ${formatMetric(
      metrics.system.latency_mean_ms,
    )} / ${formatMetric(metrics.system.latency_median_ms)} ms`,
    `- p90 / p95 latency: ${formatMetric(
      metrics.system.latency_p90_ms,
    )} / ${formatMetric(metrics.system.latency_p95_ms)} ms`,
    `- Error rate: ${formatMetric(metrics.system.error_rate)}`,
    `- Retry rate: ${formatMetric(metrics.system.retry_rate)}`,
    "",
    "## 14. Limitations",
    "",
    "- The committed pilot uses a deterministic lexical mock over the capability registry; it is plumbing validation, not a production-quality baseline.",
    "- Generated candidate annotations have not received independent human approval.",
    "- Character n-gram similarity is a reproducible fallback, not a semantic embedding model.",
    "- Current text-only routing treats reference-image ID-photo work as out of scope.",
    "- Confidence calibration metrics are only meaningful for adapters returning valid scores.",
    "",
    "## 15. Records awaiting human review",
    "",
    `${pending} records remain in \`review_queue.csv\` / \`review_queue.jsonl\`. Auto-accepted records are still distinguishable from the 16 manually approved anchors.`,
    "",
  ];
  return lines.join("\n");
}

function renderHtmlReport(markdown) {
  const escape = (value) =>
    value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const html = escape(markdown)
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>\n");
  return `<!doctype html><html lang="en"><meta charset="utf-8"><title>VIR v2 report</title><style>body{font:15px/1.5 system-ui;max-width:1100px;margin:32px auto;padding:0 20px;color:#1f2933}code{background:#eef2f5;padding:2px 4px}h2{margin-top:32px}br+br{display:block;margin:6px}</style><body>${html}</body></html>`;
}

function generateReports({
  config,
  records,
  predictions,
  score,
  validation,
  benchmarkManifest,
  adapterName,
}) {
  const reportDir = resolveRoot(config.paths.report_dir);
  fs.mkdirSync(reportDir, { recursive: true });
  const runMetadata = {
    adapter: adapterName,
    configuration_hash: hashObject({
      router: config.router,
      metrics: config.metrics,
    }),
    generated_at: new Date().toISOString(),
  };
  writeJson(path.join(reportDir, "metrics.json"), score.metrics);
  writeCsv(
    path.join(reportDir, "metrics.csv"),
    ["metric", "value"],
    flattenNumeric(score.metrics),
  );
  writeJsonl(path.join(reportDir, "predictions.jsonl"), predictions);
  writeCsv(
    path.join(reportDir, "error_cases.csv"),
    [
      "id",
      "query",
      "language",
      "difficulty",
      "transformation_types",
      "ontology",
      "gold_mode",
      "gold_targets",
      "acceptable_target_sets",
      "predicted_ranking",
      "confidence",
      "closest_competing_template",
      "source_seed_id",
      "validation_status",
      "partition",
      "challenge_type",
      "abstained",
      "system_error",
    ],
    score.errors,
  );
  writeCsv(
    path.join(reportDir, "confusion_matrix.csv"),
    ["gold_template", "predicted_template", "count"],
    score.confusion,
  );
  writeCsv(
    path.join(reportDir, "slice_metrics.csv"),
    [
      "dimension",
      "value",
      "count",
      "correct",
      "exact_accuracy",
      "ci_lower",
      "ci_upper",
      "abstention_rate",
      "error_rate",
    ],
    score.sliceMetrics,
  );
  writeJson(path.join(reportDir, "slice_metrics.json"), score.sliceMetrics);
  writeJson(path.join(reportDir, "dataset_validation.json"), validation);
  writeJson(path.join(reportDir, "benchmark_manifest.json"), benchmarkManifest);
  writeJson(path.join(reportDir, "run_metadata.json"), runMetadata);
  const markdown = renderReport({
    metrics: score.metrics,
    validation,
    benchmarkManifest,
    errors: score.errors,
    confusion: score.confusion,
    records,
    runMetadata,
  });
  fs.writeFileSync(path.join(reportDir, "report.md"), markdown);
  fs.writeFileSync(path.join(reportDir, "report.html"), renderHtmlReport(markdown));
  return {
    report_dir: reportDir,
    report_md: path.join(reportDir, "report.md"),
    report_html: path.join(reportDir, "report.html"),
  };
}

module.exports = {
  examplesTable,
  flattenNumeric,
  formatMetric,
  generateReports,
  renderHtmlReport,
  renderReport,
};
