"use strict";

const path = require("path");
const { readJsonl, writeJson, writeJsonl } = require("./common.cjs");

async function predictWithRetries(adapter, record, maxRetries = 0) {
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    try {
      const prediction = await adapter.predict(record);
      prediction.retry_count = attempt;
      return prediction;
    } catch (error) {
      lastError = error;
      if (attempt === maxRetries) break;
    }
  }
  return {
    query_id: record.id,
    predictions: [],
    abstained: false,
    latency_ms: null,
    retry_count: maxRetries,
    raw_output: null,
    error: {
      code: lastError?.code ?? "ROUTER_ERROR",
      message: lastError?.message ?? String(lastError),
      details: lastError?.details ?? null,
    },
  };
}

async function runRouter({
  records,
  adapter,
  outPath,
  resume = true,
  maxRetries = 0,
}) {
  const existing = resume && outPath ? readJsonl(outPath) : [];
  const byId = new Map(existing.map((prediction) => [prediction.query_id, prediction]));
  for (const record of records) {
    if (byId.has(record.id)) continue;
    byId.set(
      record.id,
      await predictWithRetries(adapter, record, maxRetries),
    );
  }
  const predictions = records.map((record) => byId.get(record.id));
  if (outPath) writeJsonl(outPath, predictions);
  return {
    predictions,
    summary: {
      adapter: adapter.name,
      record_count: records.length,
      error_count: predictions.filter((prediction) => prediction.error).length,
      abstention_count: predictions.filter(
        (prediction) => prediction.abstained,
      ).length,
      resumed_count: existing.length,
    },
  };
}

function loadRunRecords(config, splits = ["anchor", "dev", "test", "challenge"]) {
  return splits.flatMap((split) =>
    readJsonl(path.join(config.paths.split_dir, `${split}.jsonl`)),
  );
}

module.exports = { loadRunRecords, predictWithRetries, runRouter };
