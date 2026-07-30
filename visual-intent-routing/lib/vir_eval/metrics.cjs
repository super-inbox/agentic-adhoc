"use strict";

const { mean, quantile } = require("./common.cjs");

function safeDivide(numerator, denominator) {
  return denominator ? numerator / denominator : null;
}

function f1(precision, recall) {
  return precision !== null && recall !== null && precision + recall
    ? (2 * precision * recall) / (precision + recall)
    : precision === 0 && recall === 0
      ? 0
      : null;
}

// Peter J. Acklam's rational approximation for the inverse standard-normal
// CDF. This keeps Wilson intervals dependency-free and honors configurable
// confidence levels.
function inverseNormalCdf(probability) {
  if (probability <= 0 || probability >= 1) {
    throw new RangeError("Normal quantile probability must be between 0 and 1");
  }
  const a = [
    -39.69683028665376, 220.9460984245205, -275.9285104469687,
    138.357751867269, -30.66479806614716, 2.506628277459239,
  ];
  const b = [
    -54.47609879822406, 161.5858368580409, -155.6989798598866,
    66.80131188771972, -13.28068155288572,
  ];
  const c = [
    -0.007784894002430293, -0.3223964580411365, -2.400758277161838,
    -2.549732539343734, 4.374664141464968, 2.938163982698783,
  ];
  const d = [
    0.007784695709041462, 0.3224671290700398, 2.445134137142996,
    3.754408661907416,
  ];
  const lower = 0.02425;
  const upper = 1 - lower;
  if (probability < lower) {
    const q = Math.sqrt(-2 * Math.log(probability));
    return (
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q +
        c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }
  if (probability > upper) {
    const q = Math.sqrt(-2 * Math.log(1 - probability));
    return -(
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q +
        c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }
  const q = probability - 0.5;
  const r = q * q;
  return (
    (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r +
      a[5]) *
    q /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r +
      1)
  );
}

function wilsonInterval(successes, total, confidence = 0.95) {
  if (!total) return { lower: null, upper: null, confidence };
  const z = inverseNormalCdf(0.5 + confidence / 2);
  const p = successes / total;
  const denominator = 1 + (z * z) / total;
  const center = (p + (z * z) / (2 * total)) / denominator;
  const margin =
    (z / denominator) *
    Math.sqrt((p * (1 - p)) / total + (z * z) / (4 * total * total));
  return {
    lower: Math.max(0, center - margin),
    upper: Math.min(1, center + margin),
    confidence,
  };
}

function setMetrics(expected, predicted) {
  const gold = new Set(expected);
  const output = new Set(predicted);
  let intersection = 0;
  for (const value of output) if (gold.has(value)) intersection += 1;
  const precision = safeDivide(intersection, output.size);
  const recall = safeDivide(intersection, gold.size);
  return {
    exact:
      gold.size === output.size &&
      [...gold].every((value) => output.has(value)),
    precision: precision ?? (gold.size === 0 && output.size === 0 ? 1 : 0),
    recall: recall ?? (gold.size === 0 ? 1 : 0),
    f1: f1(
      precision ?? (gold.size === 0 && output.size === 0 ? 1 : 0),
      recall ?? (gold.size === 0 ? 1 : 0),
    ),
    partial: intersection > 0,
    intersection,
  };
}

function ambiguousMatch(record, predictedIds, abstained) {
  if (abstained) {
    return (record.gold.acceptable_target_sets ?? []).some(
      (set) => set.length === 0,
    );
  }
  return (record.gold.acceptable_target_sets ?? []).some((acceptable) => {
    const prefix = predictedIds.slice(0, acceptable.length);
    return setMetrics(acceptable, prefix).exact;
  });
}

function evaluateRecord(record, prediction) {
  const predictedIds = (prediction.predictions ?? [])
    .slice()
    .sort((left, right) => left.rank - right.rank)
    .map((item) => item.template_id);
  const top1 = predictedIds[0] ?? null;
  const mode = record.gold.target_mode;
  let correct = false;
  if (mode === "single") {
    correct = !prediction.abstained && top1 === record.gold.targets[0];
  } else if (mode === "none") {
    correct = prediction.abstained === true;
  } else if (mode === "multi") {
    correct = setMetrics(record.gold.targets, predictedIds).exact;
  } else if (mode === "ambiguous") {
    correct = ambiguousMatch(record, predictedIds, prediction.abstained);
  }
  const targetRanks = record.gold.targets
    .map((target) => predictedIds.indexOf(target) + 1)
    .filter((rank) => rank > 0);
  const bestRank = targetRanks.length ? Math.min(...targetRanks) : null;
  return {
    record,
    prediction,
    mode,
    predicted_ids: predictedIds,
    top1,
    correct,
    best_rank: bestRank,
    reciprocal_rank: bestRank ? 1 / bestRank : 0,
    top1_score:
      typeof prediction.match_score === "number"
        ? prediction.match_score
        : prediction.predictions?.[0]?.score ?? null,
  };
}

function proportion(successes, total, confidence = 0.95) {
  return {
    value: safeDivide(successes, total),
    successes,
    total,
    interval: wilsonInterval(successes, total, confidence),
  };
}

function rocAuc(labels, scores) {
  if (!labels.length || new Set(labels).size < 2) return null;
  const pairs = labels.map((label, index) => ({
    label,
    score: scores[index],
  }));
  const positives = pairs.filter((pair) => pair.label === 1).length;
  const negatives = pairs.length - positives;
  let favorable = 0;
  for (const positive of pairs.filter((pair) => pair.label === 1)) {
    for (const negative of pairs.filter((pair) => pair.label === 0)) {
      if (positive.score > negative.score) favorable += 1;
      else if (positive.score === negative.score) favorable += 0.5;
    }
  }
  return favorable / (positives * negatives);
}

function averagePrecision(labels, scores) {
  const positives = labels.reduce((total, label) => total + label, 0);
  if (!positives || positives === labels.length) return null;
  const ordered = labels
    .map((label, index) => ({ label, score: scores[index] }))
    .sort((left, right) => right.score - left.score);
  let seenPositive = 0;
  let sum = 0;
  ordered.forEach((item, index) => {
    if (item.label === 1) {
      seenPositive += 1;
      sum += seenPositive / (index + 1);
    }
  });
  return sum / positives;
}

function primaryMetrics(evaluated, confidence) {
  const corePositive = evaluated.filter(
    (item) =>
      item.record.partition === "core" && item.record.gold.target_mode === "single",
  );
  const coreAndGap = evaluated.filter((item) =>
    ["core", "content_gap"].includes(item.record.partition),
  );
  const top1Success = corePositive.filter((item) => item.correct).length;
  const perTemplate = new Map();
  for (const item of corePositive) {
    const target = item.record.gold.targets[0];
    perTemplate.set(target, [...(perTemplate.get(target) ?? []), item]);
  }
  const macro = mean(
    [...perTemplate.values()].map(
      (items) => items.filter((item) => item.correct).length / items.length,
    ),
  );
  const topK = {};
  for (const k of [1, 3, 5]) {
    const hits = corePositive.filter(
      (item) => item.best_rank !== null && item.best_rank <= k,
    ).length;
    topK[`recall_at_${k}`] = proportion(hits, corePositive.length, confidence);
  }
  return {
    positive_query_top1_exact_accuracy: proportion(
      top1Success,
      corePositive.length,
      confidence,
    ),
    macro_top1_accuracy_across_templates: macro,
    micro_top1_accuracy: safeDivide(top1Success, corePositive.length),
    overall_exact_accuracy_including_no_match: proportion(
      coreAndGap.filter((item) => item.correct).length,
      coreAndGap.length,
      confidence,
    ),
    ...topK,
    mean_reciprocal_rank: mean(
      corePositive.map((item) => item.reciprocal_rank),
    ),
    unknown_template_prediction_rate: proportion(
      evaluated.filter(
        (item) => item.prediction.error?.code === "UNKNOWN_TEMPLATE",
      ).length,
      evaluated.length,
      confidence,
    ),
    record_counts: {
      core_positive: corePositive.length,
      core_and_content_gap: coreAndGap.length,
    },
  };
}

function abstentionMetrics(evaluated, config, confidence) {
  const rows = evaluated.filter((item) =>
    ["core", "content_gap"].includes(item.record.partition),
  );
  let tp = 0;
  let fp = 0;
  let fn = 0;
  let tn = 0;
  for (const item of rows) {
    const should = item.record.gold.target_mode === "none";
    const did = item.prediction.abstained === true;
    if (should && did) tp += 1;
    else if (!should && did) fp += 1;
    else if (should && !did) fn += 1;
    else tn += 1;
  }
  const precision = safeDivide(tp, tp + fp) ?? 0;
  const recall = safeDivide(tp, tp + fn) ?? 0;
  const scoredRows = rows.filter(
    (item) => typeof item.top1_score === "number",
  );
  const labels = scoredRows.map((item) =>
    item.record.gold.target_mode === "none" ? 0 : 1,
  );
  const scores = scoredRows.map((item) => item.top1_score);
  const thresholdSweep =
    scoredRows.length === rows.length
      ? config.metrics.thresholds.map((threshold) => {
          let thresholdTp = 0;
          let thresholdFp = 0;
          let thresholdFn = 0;
          let thresholdTn = 0;
          scoredRows.forEach((item, index) => {
            const shouldAbstain = labels[index] === 0;
            const predictsAbstain = scores[index] < threshold;
            if (shouldAbstain && predictsAbstain) thresholdTp += 1;
            else if (!shouldAbstain && predictsAbstain) thresholdFp += 1;
            else if (shouldAbstain) thresholdFn += 1;
            else thresholdTn += 1;
          });
          const p =
            safeDivide(thresholdTp, thresholdTp + thresholdFp) ?? 0;
          const r =
            safeDivide(thresholdTp, thresholdTp + thresholdFn) ?? 0;
          return {
            threshold,
            abstention_precision: p,
            abstention_recall: r,
            abstention_f1: f1(p, r),
            false_routing_rate: safeDivide(
              thresholdFn,
              thresholdTp + thresholdFn,
            ),
            false_abstention_rate: safeDivide(
              thresholdFp,
              thresholdTn + thresholdFp,
            ),
          };
        })
      : null;
  return {
    confusion: { true_abstain: tp, false_abstain: fp, false_route: fn, true_route: tn },
    abstention_precision: precision,
    abstention_recall: recall,
    abstention_f1: f1(precision, recall),
    false_routing_rate_on_content_gap: proportion(fn, tp + fn, confidence),
    false_abstention_rate_on_supported: proportion(fp, tn + fp, confidence),
    threshold_sweep: thresholdSweep,
    match_confidence_auroc:
      scoredRows.length === rows.length ? rocAuc(labels, scores) : null,
    match_confidence_auprc:
      scoredRows.length === rows.length
        ? averagePrecision(labels, scores)
        : null,
  };
}

function challengeMetrics(evaluated, confidence) {
  const multi = evaluated.filter((item) => item.mode === "multi");
  const multiSets = multi.map((item) =>
    setMetrics(item.record.gold.targets, item.predicted_ids),
  );
  const ambiguous = evaluated.filter((item) => item.mode === "ambiguous");
  const choiceDistribution = {};
  for (const item of ambiguous) {
    const choice = item.top1 ?? "__abstain__";
    choiceDistribution[choice] = (choiceDistribution[choice] ?? 0) + 1;
  }
  return {
    multi_intent: {
      count: multi.length,
      exact_set_match: proportion(
        multiSets.filter((metric) => metric.exact).length,
        multi.length,
        confidence,
      ),
      set_precision: mean(multiSets.map((metric) => metric.precision)),
      set_recall: mean(multiSets.map((metric) => metric.recall)),
      set_f1: mean(multiSets.map((metric) => metric.f1)),
      partial_match_rate: proportion(
        multiSets.filter((metric) => metric.partial).length,
        multi.length,
        confidence,
      ),
    },
    ambiguous: {
      count: ambiguous.length,
      acceptable_target_set_match_rate: proportion(
        ambiguous.filter((item) => item.correct).length,
        ambiguous.length,
        confidence,
      ),
      primary_choice_distribution: choiceDistribution,
      abstention_rate: proportion(
        ambiguous.filter((item) => item.prediction.abstained).length,
        ambiguous.length,
        confidence,
      ),
      excluded_from_primary_core_accuracy: true,
    },
  };
}

function consistency(items) {
  if (items.length < 2) return null;
  const choices = items.map((item) =>
    item.prediction.abstained ? "__abstain__" : item.top1,
  );
  return new Set(choices).size === 1 ? 1 : 0;
}

function accuracy(items) {
  return safeDivide(
    items.filter((item) => item.correct).length,
    items.length,
  );
}

function robustnessMetrics(evaluated) {
  const core = evaluated.filter(
    (item) =>
      item.record.partition === "core" && item.record.gold.target_mode === "single",
  );
  const clusters = new Map();
  for (const item of core) {
    clusters.set(item.record.semantic_cluster_id, [
      ...(clusters.get(item.record.semantic_cluster_id) ?? []),
      item,
    ]);
  }
  const clusterValues = [...clusters.values()]
    .map(consistency)
    .filter((value) => value !== null);
  const translated = [...clusters.values()]
    .filter(
      (items) => new Set(items.map((item) => item.record.language)).size > 1,
    )
    .map(consistency)
    .filter((value) => value !== null);
  const transformGroups = {
    paraphrase: core.filter((item) =>
      item.record.transformation_types.includes("paraphrase"),
    ),
    typo_noise: core.filter((item) =>
      item.record.transformation_types.includes("typo_noise"),
    ),
    explicit_intent: core.filter((item) =>
      item.record.transformation_types.includes("explicit_artifact"),
    ),
    implicit_intent: core.filter((item) =>
      item.record.transformation_types.includes("implicit_intent"),
    ),
  };
  const difficulty = Object.fromEntries(
    ["low", "medium", "high"].map((level) => [
      level,
      accuracy(core.filter((item) => item.record.difficulty === level)),
    ]),
  );
  const language = Object.fromEntries(
    ["zh", "en", "mixed"].map((label) => [
      label,
      accuracy(core.filter((item) => item.record.language === label)),
    ]),
  );
  const validLanguage = Object.values(language).filter(
    (value) => value !== null,
  );
  const transformations = {};
  const allTransformations = new Set(
    core.flatMap((item) => item.record.transformation_types),
  );
  for (const transformation of [...allTransformations].sort()) {
    const rows = core.filter((item) =>
      item.record.transformation_types.includes(transformation),
    );
    transformations[transformation] = {
      count: rows.length,
      accuracy: accuracy(rows),
    };
  }
  const cleanAccuracy = accuracy(transformGroups.explicit_intent);
  for (const value of Object.values(transformations)) {
    value.degradation_relative_to_clean =
      cleanAccuracy === null || value.accuracy === null
        ? null
        : value.accuracy - cleanAccuracy;
  }
  return {
    semantic_cluster_prediction_consistency: mean(clusterValues),
    translation_consistency: mean(translated),
    paraphrase_consistency: mean(
      [...clusters.values()]
        .filter((items) =>
          items.some((item) =>
            item.record.transformation_types.includes("paraphrase"),
          ),
        )
        .map(consistency)
        .filter((value) => value !== null),
    ),
    typo_noise_accuracy: accuracy(transformGroups.typo_noise),
    explicit_to_implicit: {
      explicit_accuracy: accuracy(transformGroups.explicit_intent),
      implicit_accuracy: accuracy(transformGroups.implicit_intent),
      drop:
        accuracy(transformGroups.explicit_intent) === null ||
        accuracy(transformGroups.implicit_intent) === null
          ? null
          : accuracy(transformGroups.implicit_intent) -
            accuracy(transformGroups.explicit_intent),
    },
    difficulty_accuracy: difficulty,
    low_to_high_drop:
      difficulty.low === null || difficulty.high === null
        ? null
        : difficulty.high - difficulty.low,
    language_accuracy: language,
    language_performance_gap:
      validLanguage.length > 1
        ? Math.max(...validLanguage) - Math.min(...validLanguage)
        : null,
    transformation_metrics: transformations,
  };
}

function queryLengthBucket(query) {
  const length = [...query].length;
  if (length <= 15) return "short_0_15";
  if (length <= 45) return "medium_16_45";
  return "long_46_plus";
}

function sliceRows(evaluated, confidence) {
  const dimensions = {
    template: (item) =>
      item.record.gold.targets.length
        ? item.record.gold.targets
        : ["__none__"],
    subject: (item) => [item.record.subject],
    language: (item) => [item.record.language],
    difficulty: (item) => [item.record.difficulty],
    transformation_type: (item) => item.record.transformation_types,
    partition: (item) => [item.record.partition],
    challenge_type: (item) => [item.record.challenge_type ?? "__none__"],
    query_length_bucket: (item) => [
      queryLengthBucket(item.record.query),
    ],
  };
  const rows = [];
  for (const [dimension, getter] of Object.entries(dimensions)) {
    const groups = new Map();
    for (const item of evaluated) {
      for (const value of getter(item)) {
        groups.set(value, [...(groups.get(value) ?? []), item]);
      }
    }
    for (const [value, items] of [...groups.entries()].sort()) {
      const successful = items.filter((item) => item.correct).length;
      rows.push({
        dimension,
        value,
        count: items.length,
        correct: successful,
        exact_accuracy: safeDivide(successful, items.length),
        ci_lower: wilsonInterval(successful, items.length, confidence).lower,
        ci_upper: wilsonInterval(successful, items.length, confidence).upper,
        abstention_rate: safeDivide(
          items.filter((item) => item.prediction.abstained).length,
          items.length,
        ),
        error_rate: safeDivide(
          items.filter((item) => item.prediction.error).length,
          items.length,
        ),
      });
    }
  }
  return rows;
}

function systemMetrics(evaluated) {
  const latencies = evaluated
    .map((item) => item.prediction.latency_ms)
    .filter((value) => typeof value === "number" && Number.isFinite(value));
  return {
    latency_mean_ms: mean(latencies),
    latency_median_ms: quantile(latencies, 0.5),
    latency_p90_ms: quantile(latencies, 0.9),
    latency_p95_ms: quantile(latencies, 0.95),
    latency_sample_count: latencies.length,
    error_rate: safeDivide(
      evaluated.filter((item) => item.prediction.error).length,
      evaluated.length,
    ),
    retry_rate: safeDivide(
      evaluated.filter((item) => (item.prediction.retry_count ?? 0) > 0).length,
      evaluated.length,
    ),
  };
}

function confusionRows(evaluated) {
  const counts = new Map();
  for (const item of evaluated.filter(
    (value) => value.record.gold.target_mode === "single",
  )) {
    const gold = item.record.gold.targets[0];
    const predicted = item.prediction.abstained
      ? "__abstain__"
      : item.top1 ?? "__error__";
    const key = `${gold}\u0000${predicted}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([key, count]) => {
      const [gold_template, predicted_template] = key.split("\u0000");
      return { gold_template, predicted_template, count };
    })
    .sort(
      (left, right) =>
        right.count - left.count ||
        left.gold_template.localeCompare(right.gold_template),
    );
}

function errorRows(evaluated) {
  return evaluated
    .filter((item) => !item.correct)
    .map((item) => {
      const closestCandidate = item.prediction.raw_output?.candidates?.[0];
      return {
        id: item.record.id,
        query: item.record.query,
        language: item.record.language,
        difficulty: item.record.difficulty,
        transformation_types: item.record.transformation_types,
        ontology: item.record.ontology,
        gold_mode: item.record.gold.target_mode,
        gold_targets: item.record.gold.targets,
        acceptable_target_sets: item.record.gold.acceptable_target_sets,
        predicted_ranking: item.prediction.predictions,
        confidence:
          item.top1_score ??
          closestCandidate?.score ??
          item.prediction.match_score,
        closest_competing_template:
          item.top1 ??
          closestCandidate?.template_id ??
          item.prediction.raw_output?.closest_competing_template ??
          null,
        source_seed_id: item.record.source_seed_id,
        validation_status: item.record.validation.status,
        partition: item.record.partition,
        challenge_type: item.record.challenge_type,
        abstained: item.prediction.abstained,
        system_error: item.prediction.error,
      };
    });
}

function scoreDataset({ records, predictions, config }) {
  const predictionById = new Map(
    predictions.map((prediction) => [prediction.query_id, prediction]),
  );
  const missing = records.filter((record) => !predictionById.has(record.id));
  if (missing.length) {
    throw new Error(
      `Missing predictions for ${missing.length} records: ${missing
        .slice(0, 5)
        .map((record) => record.id)
        .join(", ")}`,
    );
  }
  const evaluated = records.map((record) =>
    evaluateRecord(record, predictionById.get(record.id)),
  );
  const confidence = config.metrics.confidence_level;
  const metrics = {
    benchmark_version: config.benchmark_version,
    scoring_contract:
      "Exact canonical template-ID equality; ambiguous sets and abstention use explicit deterministic rules.",
    confidence_intervals: `Wilson intervals at ${confidence * 100}% for important proportions.`,
    primary_core: primaryMetrics(evaluated, confidence),
    content_gap: abstentionMetrics(evaluated, config, confidence),
    challenges: challengeMetrics(evaluated, confidence),
    robustness: robustnessMetrics(evaluated),
    system: systemMetrics(evaluated),
  };
  return {
    metrics,
    evaluated,
    sliceMetrics: sliceRows(evaluated, confidence),
    confusion: confusionRows(evaluated),
    errors: errorRows(evaluated),
  };
}

module.exports = {
  ambiguousMatch,
  averagePrecision,
  evaluateRecord,
  inverseNormalCdf,
  queryLengthBucket,
  rocAuc,
  safeDivide,
  scoreDataset,
  setMetrics,
  sliceRows,
  wilsonInterval,
};
