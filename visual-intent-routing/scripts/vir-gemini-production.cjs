#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const {
  buildCurifyJobs,
  stageRecords,
} = require("./vir-image-tasks.cjs");

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_RUN_ID = "2026-08-03-production-gemini";
const DEFAULT_PLAN_SOURCE_RUN = "2026-08-01-full";
const DEFAULT_BASE_URL = "http://localhost:3000";
const MODEL = "gemini-3-pro-image-preview";

function parseArgs(argv) {
  const command = argv[0] && !argv[0].startsWith("--") ? argv[0] : "help";
  const options = {};
  for (let index = command === "help" ? 0 : 1; index < argv.length; index += 1) {
    const argument = argv[index];
    if (!argument.startsWith("--")) continue;
    const equals = argument.indexOf("=");
    if (equals > 0) {
      options[argument.slice(2, equals).replace(/-/g, "_")] =
        argument.slice(equals + 1);
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

function resolveRoot(value) {
  return path.isAbsolute(value) ? value : path.resolve(ROOT, value);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(resolveRoot(filePath), "utf8"));
}

function readJsonl(filePath) {
  const absolute = resolveRoot(filePath);
  if (!fs.existsSync(absolute)) return [];
  return fs
    .readFileSync(absolute, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function writeJson(filePath, value) {
  const absolute = resolveRoot(filePath);
  fs.mkdirSync(path.dirname(absolute), { recursive: true });
  fs.writeFileSync(absolute, `${JSON.stringify(value, null, 2)}\n`);
}

function writeJsonl(filePath, values) {
  const absolute = resolveRoot(filePath);
  fs.mkdirSync(path.dirname(absolute), { recursive: true });
  const contents = values.length
    ? `${values.map((value) => JSON.stringify(value)).join("\n")}\n`
    : "";
  fs.writeFileSync(absolute, contents);
}

function appendJsonl(filePath, value) {
  const absolute = resolveRoot(filePath);
  fs.mkdirSync(path.dirname(absolute), { recursive: true });
  fs.appendFileSync(absolute, `${JSON.stringify(value)}\n`);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function sha256File(filePath) {
  return sha256(fs.readFileSync(filePath));
}

function safeName(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function productionSlug(runId, stage, queryId, direction, templateId) {
  const identity = [runId, stage, queryId, direction, templateId].join("|");
  const readable = safeName(
    `${runId}-${stage}-${queryId}-${direction}-${templateId}`,
  ).slice(0, 130);
  return `${readable}-${sha256(identity).slice(0, 12)}`;
}

function runPaths(runId, stage) {
  const stageDir = resolveRoot(`reports/vir_v2/images/${runId}/${stage}`);
  return {
    stageDir,
    records: path.join(stageDir, "records.jsonl"),
    plans: path.join(stageDir, "curify-plans.jsonl"),
    input: path.join(stageDir, "curify-gemini-input.jsonl"),
    pending: path.join(stageDir, "curify-gemini-pending.jsonl"),
    results: path.join(stageDir, "curify-gemini-results.jsonl"),
    events: path.join(stageDir, "curify-gemini-events.jsonl"),
    outDir: path.join(stageDir, "curify-gemini"),
    manifest: path.join(stageDir, "stage-manifest.json"),
    gallery: path.join(stageDir, "gallery.html"),
  };
}

function sourcePlanPath(runId, stage) {
  return resolveRoot(
    `reports/vir_v2/images/${runId}/${stage}/curify-plans.jsonl`,
  );
}

function planMatchesRecord(plan, record) {
  return plan?.query_id === record.id &&
    plan?.query === record.query &&
    plan?.language === record.language;
}

async function postJson(url, body, timeoutMs = 300_000) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error(`HTTP ${response.status}: ${text.slice(0, 400)}`);
  }
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${payload.error ?? text.slice(0, 400)}`);
  }
  return payload;
}

async function completePlans({ rows, planPath, baseUrl, concurrency }) {
  const indexes = rows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => !["completed", "abstained"].includes(row.status))
    .map(({ index }) => index);
  let cursor = 0;
  const worker = async () => {
    while (cursor < indexes.length) {
      const position = cursor;
      cursor += 1;
      const index = indexes[position];
      const row = rows[index];
      try {
        const payload = await postJson(
          `${baseUrl.replace(/\/+$/, "")}/api/search-generation-plan`,
          {
            query: row.query,
            locale: row.language === "en" ? "en" : "zh",
          },
          180_000,
        );
        row.plan = payload;
        row.notice = payload.notice ?? null;
        row.status = payload.directions?.length ? "completed" : "abstained";
        row.error = null;
        row.attempts = (row.attempts ?? 0) + 1;
      } catch (error) {
        row.status = "failed";
        row.error = error instanceof Error ? error.message : String(error);
        row.attempts = (row.attempts ?? 0) + 1;
      }
      row.updated_at = new Date().toISOString();
      writeJsonl(planPath, rows);
      console.log(`[plan ${position + 1}/${indexes.length}] ${row.query_id}: ${row.status}`);
    }
  };
  const workerCount = Math.max(
    1,
    Math.min(Number(concurrency) || 1, indexes.length || 1),
  );
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return rows;
}

function buildGeminiJobs(curifyJobs, runId, stage) {
  return curifyJobs.map((job) => {
    const metadata = job.vir_metadata;
    const slug = productionSlug(
      runId,
      stage,
      job.vir_query_id,
      job.vir_direction,
      metadata.template_id,
    );
    return {
      schema_version: 1,
      query_id: job.vir_query_id,
      query: metadata.source_query,
      stage,
      partition: metadata.partition,
      language: metadata.language,
      direction: job.vir_direction,
      template_id: metadata.template_id,
      params: metadata.params ?? {},
      confidence: metadata.confidence ?? null,
      reason: metadata.reason ?? null,
      plan_source: metadata.plan_source ?? null,
      locale: metadata.language === "en" ? "en" : "zh",
      slug,
      expected_prompt: job.prompt,
      expected_prompt_sha256: sha256(job.prompt),
      model: MODEL,
      endpoint: "/api/generate-image",
    };
  });
}

function findGeminiOutput(job, outDir) {
  const absolute = resolveRoot(outDir);
  for (const extension of ["jpg", "png"] ) {
    const candidate = path.join(absolute, `${job.slug}.${extension}`);
    if (fs.existsSync(candidate) && fs.statSync(candidate).size > 0) {
      return candidate;
    }
  }
  return null;
}

function pendingGeminiJobs(jobs, outDir) {
  return jobs.filter((job) => !findGeminiOutput(job, outDir));
}

function validateImagePayload(buffer, extension) {
  if (!buffer.length) throw new Error("Generated image response was empty");
  const isPng =
    buffer.length >= 8 &&
    buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  const isJpeg = buffer.length >= 3 && buffer[0] === 255 && buffer[1] === 216 && buffer[2] === 255;
  if (extension === "png" && !isPng) {
    throw new Error("Image URL used .png but bytes were not PNG");
  }
  if (extension === "jpg" && !isJpeg) {
    throw new Error("Image URL used .jpg but bytes were not JPEG");
  }
}

function blockingGeminiError(message) {
  return /(?:resource[_ ]?exhausted|quota|rate.?limit|billing|HTTP 429)/i.test(message);
}

async function fetchGeneratedImage(baseUrl, url, maxAttempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(new URL(url, baseUrl), {
        signal: AbortSignal.timeout(60_000),
      });
      if (!response.ok) throw new Error(`Image GET HTTP ${response.status}`);
      return {
        buffer: Buffer.from(await response.arrayBuffer()),
        attempts: attempt,
      };
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1000));
      }
    }
  }
  throw lastError;
}

async function generateGeminiJob({ job, outDir, baseUrl, maxAttempts }) {
  const started = Date.now();
  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const payload = await postJson(
        `${baseUrl.replace(/\/+$/, "")}/api/generate-image`,
        {
          template_id: job.template_id,
          params: job.params,
          slug: job.slug,
          locale: job.locale,
        },
      );
      if (payload.prompt !== job.expected_prompt) {
        throw new Error("Curify endpoint prompt differs from the prepared prompt");
      }
      const match = new RegExp(
        `^/api/generate-image/${job.slug}\\.(jpg|png)$`,
      ).exec(payload.url ?? "");
      if (!match) {
        throw new Error(`Unexpected image URL: ${String(payload.url)}`);
      }
      const extension = match[1];
      const fetched = await fetchGeneratedImage(baseUrl, payload.url, maxAttempts);
      validateImagePayload(fetched.buffer, extension);
      const absoluteOutDir = resolveRoot(outDir);
      fs.mkdirSync(absoluteOutDir, { recursive: true });
      const finalPath = path.join(absoluteOutDir, `${job.slug}.${extension}`);
      const temporaryPath = `${finalPath}.partial`;
      fs.writeFileSync(temporaryPath, fetched.buffer);
      fs.renameSync(temporaryPath, finalPath);
      return {
        schema_version: 1,
        ...job,
        status: "completed",
        attempts: attempt,
        download_attempts: fetched.attempts,
        latency_ms: Date.now() - started,
        local_path: path.relative(ROOT, finalPath),
        mime_type: extension === "png" ? "image/png" : "image/jpeg",
        bytes: fetched.buffer.length,
        sha256: sha256(fetched.buffer),
        returned_prompt_sha256: sha256(payload.prompt),
        raw_output: { url: payload.url, bytes: payload.bytes ?? null },
        completed_at: new Date().toISOString(),
        error: null,
      };
    } catch (error) {
      lastError = error;
      const message = error instanceof Error ? error.message : String(error);
      if (blockingGeminiError(message)) break;
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 2000));
      }
    }
  }
  const message = lastError instanceof Error ? lastError.message : String(lastError);
  return {
    schema_version: 1,
    ...job,
    status: "failed",
    attempts: maxAttempts,
    latency_ms: Date.now() - started,
    local_path: null,
    mime_type: null,
    bytes: 0,
    sha256: null,
    failed_at: new Date().toISOString(),
    error: message,
    blocking_error: blockingGeminiError(message) ? "gemini_quota_or_billing" : null,
  };
}

async function renderGeminiJobs({
  jobs,
  outDir,
  resultPath,
  eventPath,
  baseUrl,
  concurrency = 2,
  maxAttempts = 3,
}) {
  const resultBySlug = new Map(
    readJsonl(resultPath).map((row) => [row.slug, row]),
  );
  const pending = pendingGeminiJobs(jobs, outDir);
  let cursor = 0;
  let blockingError = null;
  const checkpoint = (result) => {
    resultBySlug.set(result.slug, result);
    writeJsonl(
      resultPath,
      jobs
        .filter((job) => resultBySlug.has(job.slug))
        .map((job) => resultBySlug.get(job.slug)),
    );
    appendJsonl(eventPath, {
      timestamp: new Date().toISOString(),
      query_id: result.query_id,
      slug: result.slug,
      status: result.status,
      attempts: result.attempts,
      latency_ms: result.latency_ms,
      error: result.error,
      blocking_error: result.blocking_error ?? null,
    });
  };
  const worker = async () => {
    while (cursor < pending.length && !blockingError) {
      const position = cursor;
      cursor += 1;
      const job = pending[position];
      const result = await generateGeminiJob({
        job,
        outDir,
        baseUrl,
        maxAttempts: Number(maxAttempts),
      });
      checkpoint(result);
      console.log(
        `[gemini ${position + 1}/${pending.length}] ${job.query_id} direction=${job.direction}: ${result.status}`,
      );
      if (result.blocking_error) blockingError = result.blocking_error;
    }
  };
  const workerCount = Math.max(
    1,
    Math.min(Number(concurrency) || 1, pending.length || 1),
  );
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return {
    requested: pending.length,
    completed: [...resultBySlug.values()].filter((row) => row.status === "completed").length,
    failed: [...resultBySlug.values()].filter((row) => row.status === "failed").length,
    blocking_error: blockingError,
  };
}

function resultForJob(job, outDir, cached) {
  const output = findGeminiOutput(job, outDir);
  if (!output) {
    const prior = cached.get(job.slug);
    return prior?.status === "failed"
      ? prior
      : { ...job, status: "pending", local_path: null, bytes: 0, sha256: null };
  }
  const stats = fs.statSync(output);
  const extension = path.extname(output).slice(1);
  return {
    ...(cached.get(job.slug) ?? job),
    status: "completed",
    local_path: path.relative(ROOT, output),
    mime_type: extension === "png" ? "image/png" : "image/jpeg",
    bytes: stats.size,
    sha256: sha256File(output),
    error: null,
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function productionGallery({ stage, records, results, omissions }) {
  const byQuery = new Map();
  for (const row of results) {
    const values = byQuery.get(row.query_id) ?? [];
    values.push(row);
    byQuery.set(row.query_id, values);
  }
  const omissionByQuery = new Map(omissions.map((row) => [row.query_id, row]));
  const cards = records.map((record) => {
    const rows = byQuery.get(record.id) ?? [];
    const images = rows.length
      ? rows.map((row) => {
          const src = row.local_path
            ? `curify-gemini/${path.basename(row.local_path)}`
            : null;
          const caption = `${row.template_id} · direction ${row.direction} · ${row.status}`;
          return `<figure>${src ? `<img loading="lazy" src="${escapeHtml(src)}" alt="${escapeHtml(caption)}">` : '<div class="placeholder">Pending / failed</div>'}<figcaption>${escapeHtml(caption)}</figcaption></figure>`;
        }).join("")
      : '<p class="missing">No image task.</p>';
    const omission = omissionByQuery.get(record.id);
    return `<article><code>${escapeHtml(record.id)}</code><h2>${escapeHtml(record.query)}</h2><p>${escapeHtml(record.language)} · ${escapeHtml(record.partition)} · ${escapeHtml(record.difficulty)}</p>${omission ? `<p class="notice">${escapeHtml(omission.status)}: ${escapeHtml(omission.reason)}</p>` : ""}<div class="images">${images}</div></article>`;
  }).join("\n");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VIR v2 ${escapeHtml(stage)} Curify Gemini gallery</title><style>body{font-family:ui-sans-serif,system-ui;margin:0;background:#f5f5f2;color:#171714}main{max-width:1500px;margin:auto;padding:32px}article{background:#fff;border:1px solid #ddd;border-radius:14px;padding:20px;margin:22px 0}h2{margin:8px 0;font-size:1.25rem}p,figcaption{color:#666}.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}figure{margin:0}img,.placeholder{width:100%;aspect-ratio:4/3;object-fit:contain;background:#eee;border-radius:8px}.placeholder{display:grid;place-items:center}.notice{padding:10px;background:#fff3cd;border-radius:8px}</style></head><body><main><h1>VIR v2 Production Track — ${escapeHtml(stage)}</h1><p>Curify routing/template prompt → ${MODEL}. Visual inspection only; routing Gold metrics remain separate.</p>${cards}</main></body></html>`;
}

async function prepare(options) {
  const stage = options.stage;
  if (!stage) throw new Error("prepare requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const planSourceRun = options.plan_source_run ?? DEFAULT_PLAN_SOURCE_RUN;
  const paths = runPaths(runId, stage);
  fs.mkdirSync(paths.outDir, { recursive: true });
  let records = stageRecords(stage);
  if (options.limit) records = records.slice(0, Number(options.limit));
  writeJsonl(paths.records, records);

  const current = new Map(readJsonl(paths.plans).map((row) => [row.query_id, row]));
  const sourcePath = sourcePlanPath(planSourceRun, stage);
  const source = new Map(readJsonl(sourcePath).map((row) => [row.query_id, row]));
  const rows = records.map((record) => {
    const cached = current.get(record.id);
    if (planMatchesRecord(cached, record)) return cached;
    const reused = source.get(record.id);
    if (planMatchesRecord(reused, record)) {
      return { ...reused, reused_from_run: planSourceRun };
    }
    return {
      query_id: record.id,
      query: record.query,
      language: record.language,
      status: "pending",
      attempts: 0,
      plan: null,
      error: null,
    };
  });
  writeJsonl(paths.plans, rows);
  if (!options.dry_run) {
    await completePlans({
      rows,
      planPath: paths.plans,
      baseUrl: options.base_url ?? DEFAULT_BASE_URL,
      concurrency: Number(options.plan_concurrency ?? 4),
    });
  }
  const templates = readJson(
    options.catalog ?? "../../curify-frontend/public/data/nano_templates.json",
  );
  const { jobs: promptJobs, omissions } = buildCurifyJobs(
    records,
    rows,
    templates,
    stage,
  );
  const jobs = buildGeminiJobs(promptJobs, runId, stage);
  const pending = pendingGeminiJobs(jobs, paths.outDir);
  writeJsonl(paths.input, jobs);
  writeJsonl(paths.pending, pending);
  const manifest = {
    schema_version: 1,
    benchmark_version: "vir-v2",
    track: "production",
    run_id: runId,
    stage,
    prepared_at: new Date().toISOString(),
    record_count: records.length,
    record_ids_sha256: sha256(records.map((record) => record.id).join("\n")),
    curify_pipeline: {
      routing_and_template_planning: "Curify search-generation-plan",
      image_model: MODEL,
      generation_endpoint: "/api/generate-image",
      controlled_backend: false,
    },
    plan_source: {
      run_id: planSourceRun,
      path: fs.existsSync(sourcePath) ? path.relative(ROOT, sourcePath) : null,
      reused: rows.filter((row) => row.reused_from_run === planSourceRun).length,
      completed: rows.filter((row) => row.status === "completed").length,
      abstained: rows.filter((row) => row.status === "abstained").length,
      failed: rows.filter((row) => row.status === "failed").length,
    },
    image_jobs: {
      total: jobs.length,
      completed: jobs.length - pending.length,
      pending: pending.length,
      omissions,
      input: path.relative(ROOT, paths.input),
      output_dir: path.relative(ROOT, paths.outDir),
    },
    comparison_reference: {
      gpt_direct_run_id: DEFAULT_PLAN_SOURCE_RUN,
      note: "End-to-end production comparison; image backends are intentionally not controlled.",
    },
  };
  writeJson(paths.manifest, manifest);
  console.log(JSON.stringify(manifest, null, 2));
  return { manifest, paths };
}

async function render(options) {
  const stage = options.stage;
  if (!stage) throw new Error("render requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const paths = runPaths(runId, stage);
  const jobs = readJsonl(paths.input);
  if (!jobs.length && !fs.existsSync(paths.input)) {
    throw new Error(`Missing prepared input: ${paths.input}`);
  }
  const summary = await renderGeminiJobs({
    jobs,
    outDir: paths.outDir,
    resultPath: paths.results,
    eventPath: paths.events,
    baseUrl: options.base_url ?? DEFAULT_BASE_URL,
    concurrency: Number(options.concurrency ?? 2),
    maxAttempts: Number(options.max_attempts ?? 3),
  });
  console.log(JSON.stringify(summary, null, 2));
  if (summary.blocking_error) {
    throw new Error(`${summary.blocking_error}; completed images were checkpointed`);
  }
  return summary;
}

function finalize(options) {
  const stage = options.stage;
  if (!stage) throw new Error("finalize requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const paths = runPaths(runId, stage);
  const manifest = readJson(paths.manifest);
  const jobs = readJsonl(paths.input);
  const cached = new Map(readJsonl(paths.results).map((row) => [row.slug, row]));
  const results = jobs.map((job) => resultForJob(job, paths.outDir, cached));
  writeJsonl(paths.results, results);
  const pending = results.filter((row) => row.status === "pending");
  writeJsonl(paths.pending, pending);
  fs.writeFileSync(
    paths.gallery,
    productionGallery({
      stage,
      records: readJsonl(paths.records),
      results,
      omissions: manifest.image_jobs.omissions ?? [],
    }),
  );
  const completed = results.filter((row) => row.status === "completed");
  const failed = results.filter((row) => row.status === "failed");
  const updated = {
    ...manifest,
    finalized_at: new Date().toISOString(),
    image_jobs: {
      ...manifest.image_jobs,
      completed: completed.length,
      failed: failed.length,
      pending: pending.length,
      bytes: completed.reduce((sum, row) => sum + row.bytes, 0),
      results: path.relative(ROOT, paths.results),
    },
    system_metrics: {
      latency_mean_ms: completed.length
        ? completed.reduce((sum, row) => sum + (row.latency_ms ?? 0), 0) / completed.length
        : null,
      error_rate: results.length ? failed.length / results.length : 0,
    },
    gallery: path.relative(ROOT, paths.gallery),
  };
  writeJson(paths.manifest, updated);
  console.log(JSON.stringify(updated, null, 2));
  return updated;
}

async function all(options) {
  await prepare(options);
  await render(options);
  return finalize(options);
}

function help() {
  console.log(`VIR v2 Curify production image runner

Usage:
  node scripts/vir-gemini-production.cjs prepare --stage anchors [--run-id ${DEFAULT_RUN_ID}] [--plan-source-run ${DEFAULT_PLAN_SOURCE_RUN}]
  node scripts/vir-gemini-production.cjs render --stage anchors [--base-url ${DEFAULT_BASE_URL}] [--concurrency 2]
  node scripts/vir-gemini-production.cjs finalize --stage anchors
  node scripts/vir-gemini-production.cjs all --stage anchors [--limit 1]

Stages: anchors | exploration | core | challenge-gap

This track intentionally follows the production Curify pipeline:
Curify route/template prompt -> ${MODEL}. Existing controlled gpt-image-2
artifacts are preserved in a separate run and are never overwritten.`);
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  if (command === "prepare") await prepare(options);
  else if (command === "render") await render(options);
  else if (command === "finalize") finalize(options);
  else if (command === "all") await all(options);
  else help();
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack ?? error.message ?? error);
    process.exitCode = 1;
  });
}

module.exports = {
  MODEL,
  buildGeminiJobs,
  findGeminiOutput,
  generateGeminiJob,
  parseArgs,
  pendingGeminiJobs,
  productionSlug,
  renderGeminiJobs,
  validateImagePayload,
};
