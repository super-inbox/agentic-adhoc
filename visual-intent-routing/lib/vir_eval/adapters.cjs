"use strict";

const { execFile } = require("child_process");
const { performance } = require("perf_hooks");
const { promisify } = require("util");
const { resolveRoot } = require("./common.cjs");
const { CharacterNgramSimilarity } = require("./similarity.cjs");

const execFileAsync = promisify(execFile);

class RouterOutputError extends Error {
  constructor(message, code = "INVALID_ROUTER_OUTPUT", details = null) {
    super(message);
    this.name = "RouterOutputError";
    this.code = code;
    this.details = details;
  }
}

function extractRawPredictions(raw) {
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw?.predictions)) return raw.predictions;
  if (Array.isArray(raw?.matches)) {
    return raw.matches.map((match) => ({
      template_id: match.template_id,
      score: match.score ?? match.confidence,
      rank: match.rank,
    }));
  }
  if (typeof raw?.template_id === "string") return [raw];
  return null;
}

function normalizeRouterOutput({
  queryId,
  raw,
  registry,
  latencyMs = null,
  emptyMeansAbstain = false,
}) {
  if (!raw || typeof raw !== "object") {
    throw new RouterOutputError("Router output must be an object");
  }
  const extracted = extractRawPredictions(raw);
  if (!extracted) {
    throw new RouterOutputError("Router output contains no prediction array");
  }
  const explicitAbstention =
    raw.abstained === true ||
    raw.abstain === true ||
    (emptyMeansAbstain && extracted.length === 0);
  if (extracted.length === 0 && !explicitAbstention) {
    throw new RouterOutputError(
      "Router returned an empty result without marking abstention",
      "UNMARKED_EMPTY_RESULT",
    );
  }
  if (extracted.length > 0 && explicitAbstention) {
    throw new RouterOutputError(
      "Router cannot abstain and return predictions simultaneously",
    );
  }
  const predictions = [];
  const seen = new Set();
  for (let index = 0; index < extracted.length; index += 1) {
    const item = extracted[index];
    if (!item || typeof item !== "object") {
      throw new RouterOutputError(`Prediction ${index} must be an object`);
    }
    const originalId = item.template_id ?? item.templateId ?? item.id;
    if (typeof originalId !== "string") {
      throw new RouterOutputError(`Prediction ${index} has no template_id`);
    }
    const canonical = registry.canonicalize(originalId);
    if (!canonical) {
      throw new RouterOutputError(
        `Unknown router template: ${originalId}`,
        "UNKNOWN_TEMPLATE",
        { template_id: originalId },
      );
    }
    if (seen.has(canonical)) {
      throw new RouterOutputError(
        `Router returned duplicate template: ${canonical}`,
        "DUPLICATE_TEMPLATE",
      );
    }
    seen.add(canonical);
    const rawScore = item.score ?? item.confidence ?? null;
    if (
      rawScore !== null &&
      (typeof rawScore !== "number" ||
        !Number.isFinite(rawScore) ||
        rawScore < 0 ||
        rawScore > 1)
    ) {
      throw new RouterOutputError(
        `Malformed score for ${canonical}: ${rawScore}`,
        "MALFORMED_SCORE",
      );
    }
    const rawRank = item.rank ?? index + 1;
    if (!Number.isInteger(rawRank) || rawRank < 1) {
      throw new RouterOutputError(
        `Malformed rank for ${canonical}: ${rawRank}`,
        "MALFORMED_RANK",
      );
    }
    predictions.push({
      template_id: canonical,
      score: rawScore,
      rank: rawRank,
    });
  }
  predictions.sort((left, right) => left.rank - right.rank);
  for (let index = 0; index < predictions.length; index += 1) {
    if (predictions[index].rank !== index + 1) {
      throw new RouterOutputError(
        `Ranks must be contiguous from 1; received ${predictions
          .map((prediction) => prediction.rank)
          .join(",")}`,
        "MALFORMED_RANK",
      );
    }
  }
  return {
    query_id: queryId,
    predictions,
    abstained: explicitAbstention,
    latency_ms:
      typeof raw.latency_ms === "number" ? raw.latency_ms : latencyMs,
    match_score:
      typeof raw.match_score === "number"
        ? raw.match_score
        : typeof raw.max_score === "number"
          ? raw.max_score
          : predictions[0]?.score ?? null,
    retry_count: Number.isInteger(raw.retry_count) ? raw.retry_count : 0,
    raw_output: raw,
    error: null,
  };
}

class MockRouterAdapter {
  constructor({ registry, topK = 5, abstentionThreshold = 0.1 } = {}) {
    this.registry = registry;
    this.topK = topK;
    this.abstentionThreshold = abstentionThreshold;
    this.similarity = new CharacterNgramSimilarity();
    this.name = "mock-capability-lexical";
  }

  async predict(record) {
    const started = performance.now();
    const scored = this.registry.templates
      .map((entry) => ({
        template_id: entry.canonical_id,
        score: this.similarity.similarity(
          record.query,
          this.registry.capabilityText(entry),
        ),
      }))
      .sort(
        (left, right) =>
          right.score - left.score ||
          left.template_id.localeCompare(right.template_id),
      );
    const best = scored[0]?.score ?? 0;
    const candidates = scored.slice(0, this.topK).map((prediction, index) => ({
      template_id: prediction.template_id,
      score: Number(prediction.score.toFixed(6)),
      rank: index + 1,
    }));
    const predictions =
      best < this.abstentionThreshold ? [] : candidates;
    const raw = {
      predictions,
      // Preserve below-threshold evidence for error analysis without
      // representing it as an emitted prediction.
      candidates,
      abstained: predictions.length === 0,
      max_score: Number(best.toFixed(6)),
      latency_ms: Number((performance.now() - started).toFixed(3)),
      adapter: this.name,
    };
    return normalizeRouterOutput({
      queryId: record.id,
      raw,
      registry: this.registry,
    });
  }
}

class HttpRouterAdapter {
  constructor({ url, registry, headers = {}, timeoutMs = 20000 }) {
    if (!url) throw new Error("HTTP adapter requires url");
    this.url = url;
    this.registry = registry;
    this.headers = headers;
    this.timeoutMs = timeoutMs;
    this.name = "http";
  }

  async predict(record) {
    const started = performance.now();
    const response = await fetch(this.url, {
      method: "POST",
      headers: { "content-type": "application/json", ...this.headers },
      body: JSON.stringify({ query: record.query, query_id: record.id }),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!response.ok) {
      throw new RouterOutputError(
        `HTTP router returned ${response.status}`,
        "HTTP_ERROR",
      );
    }
    const raw = await response.json();
    return normalizeRouterOutput({
      queryId: record.id,
      raw,
      registry: this.registry,
      latencyMs: Number((performance.now() - started).toFixed(3)),
      // Current Curify /api/search-template-match uses matches:[] as its
      // explicit no-match contract.
      emptyMeansAbstain: Array.isArray(raw.matches),
    });
  }
}

class CliJsonlRouterAdapter {
  constructor({ command, args = [], registry, timeoutMs = 30000 }) {
    if (!command) throw new Error("CLI adapter requires command");
    this.command = command;
    this.args = args;
    this.registry = registry;
    this.timeoutMs = timeoutMs;
    this.name = "cli-jsonl";
  }

  async predict(record) {
    const started = performance.now();
    const { stdout } = await execFileAsync(this.command, this.args, {
      input: `${JSON.stringify({ id: record.id, query: record.query })}\n`,
      timeout: this.timeoutMs,
      maxBuffer: 4 * 1024 * 1024,
    });
    const lines = stdout.split(/\r?\n/).filter(Boolean);
    if (lines.length !== 1) {
      throw new RouterOutputError(
        `CLI adapter expected one JSONL output row, received ${lines.length}`,
        "OUTPUT_PARSE_ERROR",
      );
    }
    let raw;
    try {
      raw = JSON.parse(lines[0]);
    } catch (error) {
      throw new RouterOutputError(
        `CLI output parsing failed: ${error.message}`,
        "OUTPUT_PARSE_ERROR",
      );
    }
    return normalizeRouterOutput({
      queryId: record.id,
      raw,
      registry: this.registry,
      latencyMs: Number((performance.now() - started).toFixed(3)),
    });
  }
}

class ModuleFunctionRouterAdapter {
  constructor({ modulePath, exportName = "predict", registry }) {
    if (!modulePath) throw new Error("Module adapter requires modulePath");
    const loaded = require(resolveRoot(modulePath));
    const fn = exportName === "default" ? loaded.default ?? loaded : loaded[exportName];
    if (typeof fn !== "function") {
      throw new Error(`${modulePath} does not export function ${exportName}`);
    }
    this.fn = fn;
    this.registry = registry;
    this.name = "module-function";
  }

  async predict(record) {
    const started = performance.now();
    const raw = await this.fn(record.query, record);
    return normalizeRouterOutput({
      queryId: record.id,
      raw,
      registry: this.registry,
      latencyMs: Number((performance.now() - started).toFixed(3)),
    });
  }
}

function createAdapter(config, registry, overrides = {}) {
  const options = { ...config.router, ...overrides, registry };
  switch (options.adapter) {
    case "mock":
      return new MockRouterAdapter({
        registry,
        topK: options.top_k,
        abstentionThreshold: options.abstention_threshold,
      });
    case "http":
      return new HttpRouterAdapter({
        url: options.url,
        registry,
        headers: options.headers,
        timeoutMs: options.timeout_ms,
      });
    case "cli":
      return new CliJsonlRouterAdapter({
        command: options.command,
        args: options.args,
        registry,
        timeoutMs: options.timeout_ms,
      });
    case "module":
      return new ModuleFunctionRouterAdapter({
        modulePath: options.module_path,
        exportName: options.export_name,
        registry,
      });
    default:
      throw new Error(`Unknown router adapter: ${options.adapter}`);
  }
}

module.exports = {
  CliJsonlRouterAdapter,
  HttpRouterAdapter,
  MockRouterAdapter,
  ModuleFunctionRouterAdapter,
  RouterOutputError,
  createAdapter,
  normalizeRouterOutput,
};
