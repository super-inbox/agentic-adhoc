"use strict";

const fs = require("fs");
const path = require("path");
const {
  mean,
  mulberry32,
  quantile,
  resolveRoot,
  writeJson,
} = require("./common.cjs");
const {
  evaluateRecord,
  explorationRecordMetrics,
} = require("./metrics.cjs");

function flattenMetrics(value, prefix = "", output = {}) {
  if (typeof value === "number") {
    output[prefix] = value;
  } else if (
    value &&
    typeof value === "object" &&
    !Array.isArray(value)
  ) {
    if (typeof value.value === "number") output[prefix] = value.value;
    else {
      for (const [key, child] of Object.entries(value)) {
        flattenMetrics(child, prefix ? `${prefix}.${key}` : key, output);
      }
    }
  }
  return output;
}

function pairedBootstrapDelta(
  baselineCorrect,
  currentCorrect,
  { samples = 1000, seed = 1234, confidence = 0.95 } = {},
) {
  if (
    baselineCorrect.length !== currentCorrect.length ||
    !baselineCorrect.length
  ) {
    return { lower: null, upper: null, confidence, samples: 0 };
  }
  const random = mulberry32(seed);
  const deltas = [];
  for (let sample = 0; sample < samples; sample += 1) {
    let baseline = 0;
    let current = 0;
    for (let index = 0; index < baselineCorrect.length; index += 1) {
      const picked = Math.floor(random() * baselineCorrect.length);
      baseline += baselineCorrect[picked] ? 1 : 0;
      current += currentCorrect[picked] ? 1 : 0;
    }
    deltas.push(
      current / baselineCorrect.length - baseline / baselineCorrect.length,
    );
  }
  const alpha = (1 - confidence) / 2;
  return {
    lower: quantile(deltas, alpha),
    upper: quantile(deltas, 1 - alpha),
    confidence,
    samples,
  };
}

function pairedBootstrapMeanDelta(
  baselineValues,
  currentValues,
  { samples = 1000, seed = 1234, confidence = 0.95 } = {},
) {
  if (
    baselineValues.length !== currentValues.length ||
    !baselineValues.length
  ) {
    return { lower: null, upper: null, confidence, samples: 0 };
  }
  const random = mulberry32(seed);
  const deltas = [];
  for (let sample = 0; sample < samples; sample += 1) {
    let baseline = 0;
    let current = 0;
    for (let index = 0; index < baselineValues.length; index += 1) {
      const picked = Math.floor(random() * baselineValues.length);
      baseline += baselineValues[picked];
      current += currentValues[picked];
    }
    deltas.push(
      (current - baseline) / baselineValues.length,
    );
  }
  const alpha = (1 - confidence) / 2;
  return {
    lower: quantile(deltas, alpha),
    upper: quantile(deltas, 1 - alpha),
    confidence,
    samples,
  };
}

function compareRuns({
  records,
  baselinePredictions,
  currentPredictions,
  baselineMetrics,
  currentMetrics,
  baselineSlices = [],
  currentSlices = [],
  config,
}) {
  const baselineById = new Map(
    baselinePredictions.map((prediction) => [prediction.query_id, prediction]),
  );
  const currentById = new Map(
    currentPredictions.map((prediction) => [prediction.query_id, prediction]),
  );
  const pairedRecords = records.filter(
    (record) => baselineById.has(record.id) && currentById.has(record.id),
  );
  const baselineEval = pairedRecords.map((record) =>
    evaluateRecord(record, baselineById.get(record.id)),
  );
  const currentEval = pairedRecords.map((record) =>
    evaluateRecord(record, currentById.get(record.id)),
  );
  const newlyFixed = [];
  const newlyBroken = [];
  pairedRecords.forEach((record, index) => {
    if (
      baselineEval[index].correct === false &&
      currentEval[index].correct === true
    ) {
      newlyFixed.push(record.id);
    }
    if (
      baselineEval[index].correct === true &&
      currentEval[index].correct === false
    ) {
      newlyBroken.push(record.id);
    }
  });
  const baseFlat = flattenMetrics(baselineMetrics);
  const currentFlat = flattenMetrics(currentMetrics);
  const metricDeltas = [];
  for (const metric of Object.keys(currentFlat).filter(
    (key) => key in baseFlat,
  )) {
    const absolute = currentFlat[metric] - baseFlat[metric];
    metricDeltas.push({
      metric,
      baseline: baseFlat[metric],
      current: currentFlat[metric],
      absolute_delta: absolute,
      relative_delta:
        baseFlat[metric] === 0 ? null : absolute / Math.abs(baseFlat[metric]),
    });
  }
  const baselineSliceMap = new Map(
    baselineSlices.map((row) => [`${row.dimension}\u0000${row.value}`, row]),
  );
  const perSlice = currentSlices
    .map((row) => {
      const previous = baselineSliceMap.get(
        `${row.dimension}\u0000${row.value}`,
      );
      if (!previous) return null;
      if (
        typeof previous.exact_accuracy !== "number" ||
        typeof row.exact_accuracy !== "number"
      ) {
        return null;
      }
      return {
        dimension: row.dimension,
        value: row.value,
        baseline: previous.exact_accuracy,
        current: row.exact_accuracy,
        absolute_delta: row.exact_accuracy - previous.exact_accuracy,
      };
    })
    .filter(Boolean)
    .sort((left, right) => left.absolute_delta - right.absolute_delta);
  const gates = [];
  for (const [metric, rule] of Object.entries(config.gates ?? {})) {
    const delta = metricDeltas.find((row) => row.metric === metric);
    if (!delta) {
      gates.push({ metric, passed: false, reason: "metric unavailable" });
      continue;
    }
    const passed =
      (rule.min_value === undefined || delta.current >= rule.min_value) &&
      (rule.min_delta === undefined ||
        delta.absolute_delta >= rule.min_delta);
    gates.push({ metric, passed, rule, ...delta });
  }
  const pairedExact = baselineEval
    .map((baseline, index) => ({
      baseline,
      current: currentEval[index],
    }))
    .filter(
      ({ baseline, current }) =>
        typeof baseline.correct === "boolean" &&
        typeof current.correct === "boolean",
    );
  const explorationPairs = pairedRecords
    .filter((record) => record.gold.target_mode === "exploration")
    .map((record) => ({
      baseline: explorationRecordMetrics(
        record,
        baselineById.get(record.id),
        config.metrics.exploration_k,
      ).relevant_effective_style_count,
      current: explorationRecordMetrics(
        record,
        currentById.get(record.id),
        config.metrics.exploration_k,
      ).relevant_effective_style_count,
    }));
  const baselineExploration = explorationPairs.map((row) => row.baseline);
  const currentExploration = explorationPairs.map((row) => row.current);
  const baselineExplorationMean = mean(baselineExploration);
  const currentExplorationMean = mean(currentExploration);
  const explorationDelta =
    baselineExplorationMean === null || currentExplorationMean === null
      ? null
      : currentExplorationMean - baselineExplorationMean;
  return {
    paired_record_count: pairedRecords.length,
    metric_deltas: metricDeltas,
    newly_fixed_records: newlyFixed,
    newly_broken_records: newlyBroken,
    per_slice_regressions: perSlice.filter((row) => row.absolute_delta < 0),
    paired_bootstrap_overall_exact_delta: pairedBootstrapDelta(
      pairedExact.map((item) => item.baseline.correct),
      pairedExact.map((item) => item.current.correct),
      {
        samples: config.metrics.bootstrap_samples,
        seed: config.random_seed,
        confidence: config.metrics.confidence_level,
      },
    ),
    style_exploration_lift_at_k: {
      metric: "relevant_effective_style_count_at_k",
      evaluation_k: config.metrics.exploration_k,
      paired_record_count: explorationPairs.length,
      baseline: baselineExplorationMean,
      current: currentExplorationMean,
      absolute_lift: explorationDelta,
      relative_lift:
        baselineExplorationMean
          ? explorationDelta / Math.abs(baselineExplorationMean)
          : null,
      paired_bootstrap_interval: pairedBootstrapMeanDelta(
        baselineExploration,
        currentExploration,
        {
          samples: config.metrics.bootstrap_samples,
          seed: config.random_seed + 97,
          confidence: config.metrics.confidence_level,
        },
      ),
    },
    gates,
    gates_passed: gates.every((gate) => gate.passed),
  };
}

function writeComparison(outDir, comparison) {
  const absolute = resolveRoot(outDir);
  fs.mkdirSync(absolute, { recursive: true });
  writeJson(path.join(absolute, "comparison.json"), comparison);
  const lines = [
    "# VIR regression comparison",
    "",
    `Paired records: ${comparison.paired_record_count}`,
    `Newly fixed: ${comparison.newly_fixed_records.length}`,
    `Newly broken: ${comparison.newly_broken_records.length}`,
    `Paired bootstrap CI for exact-accuracy delta: ${comparison.paired_bootstrap_overall_exact_delta.lower} to ${comparison.paired_bootstrap_overall_exact_delta.upper}`,
    `Style Exploration Lift@${comparison.style_exploration_lift_at_k.evaluation_k}: ${comparison.style_exploration_lift_at_k.absolute_lift ?? "n/a"} effective styles/query (paired CI ${comparison.style_exploration_lift_at_k.paired_bootstrap_interval.lower ?? "n/a"} to ${comparison.style_exploration_lift_at_k.paired_bootstrap_interval.upper ?? "n/a"})`,
    "",
    "| Metric | Baseline | Current | Absolute delta | Relative delta |",
    "|---|---:|---:|---:|---:|",
    ...comparison.metric_deltas.map(
      (row) =>
        `| ${row.metric} | ${row.baseline} | ${row.current} | ${row.absolute_delta} | ${row.relative_delta ?? "n/a"} |`,
    ),
    "",
  ];
  fs.writeFileSync(path.join(absolute, "comparison.md"), lines.join("\n"));
}

module.exports = {
  compareRuns,
  flattenMetrics,
  pairedBootstrapDelta,
  pairedBootstrapMeanDelta,
  writeComparison,
};
