#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { queryImageName } = require("./vir-image-names.cjs");

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_RUN_ID = "2026-08-01-full";
const DEFAULT_BASE_URL = "http://localhost:3000";
const DEFAULT_IMAGE_MODEL = "gpt-image-2";

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
  fs.writeFileSync(
    absolute,
    values.length ? `${values.map((value) => JSON.stringify(value)).join("\n")}\n` : "",
  );
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function sha256File(filePath) {
  return sha256(fs.readFileSync(filePath));
}

function stageRecords(stage) {
  const splitDir = resolveRoot("benchmarks/vir_v2/data/splits");
  const anchor = readJsonl(path.join(splitDir, "anchor.jsonl"));
  const dev = readJsonl(path.join(splitDir, "dev.jsonl"));
  const test = readJsonl(path.join(splitDir, "test.jsonl"));
  if (stage === "anchors") return anchor;
  if (stage === "exploration") {
    return readJsonl(path.join(splitDir, "exploration.jsonl"));
  }
  if (stage === "core") {
    // The 465 supported core total includes 15 positive anchors already run in
    // phase one. This stage intentionally emits only the remaining 450.
    return [...dev, ...test].filter((record) => record.partition === "core");
  }
  if (stage === "challenge-gap") {
    const challenge = readJsonl(path.join(splitDir, "challenge.jsonl"));
    const gaps = [...dev, ...test].filter(
      (record) => record.partition === "content_gap",
    );
    return [...challenge, ...gaps];
  }
  throw new Error(`Unknown stage: ${stage}`);
}

function outputName(recordId, direction, templateId = null, query = null) {
  return queryImageName(query ?? recordId, recordId, direction, "jpeg");
}

function gptPrompt(record, direction, directionCount) {
  if (directionCount === 1) return record.query;
  return `${record.query}\n\nGenerate one standalone finished image for visual direction ${direction} of ${directionCount}. Choose a meaningfully distinct visual concept, composition, and style for this direction. Do not include an explanation outside the image.`;
}

function imageJob({ prompt, out, queryId, direction, metadata }) {
  return {
    prompt,
    out,
    model: DEFAULT_IMAGE_MODEL,
    size: "auto",
    quality: "medium",
    output_format: "jpeg",
    output_compression: 90,
    moderation: "auto",
    vir_query_id: queryId,
    vir_direction: direction,
    vir_metadata: metadata,
  };
}

function buildGptJobs(records, stage) {
  const directionCount = stage === "exploration" ? 3 : 1;
  return records.flatMap((record) =>
    Array.from({ length: directionCount }, (_, offset) => {
      const direction = offset + 1;
      return imageJob({
        prompt: gptPrompt(record, direction, directionCount),
        out: outputName(record.id, direction, null, record.query),
        queryId: record.id,
        direction,
        metadata: {
          system: "gpt-direct",
          stage,
          partition: record.partition,
          language: record.language,
          source_query: record.query,
          prompt_policy:
            directionCount === 1
              ? "exact-query"
              : "exact-query-plus-direction-index",
        },
      });
    }),
  );
}

function chooseBasePrompt(template, locale) {
  return (
    template.locales?.[locale]?.base_prompt ??
    template.locales?.en?.base_prompt ??
    template.locales?.zh?.base_prompt ??
    template.base_prompt ??
    null
  );
}

function fillPrompt(basePrompt, params) {
  return basePrompt.replace(/\{(\w+)\}/g, (_, key) =>
    Object.prototype.hasOwnProperty.call(params, key) ? params[key] : `{${key}}`,
  );
}

function buildCurifyJobs(records, plans, templates, stage) {
  const maxDirections = stage === "exploration" ? 3 : 1;
  const templateById = new Map(
    templates.map((template) => [template.id, template]),
  );
  const recordById = new Map(records.map((record) => [record.id, record]));
  const jobs = [];
  const omissions = [];
  for (const planRow of plans) {
    const record = recordById.get(planRow.query_id);
    if (!record) continue;
    if (planRow.status !== "completed") {
      omissions.push({
        query_id: record.id,
        status: planRow.status,
        reason: planRow.notice ?? planRow.error ?? "no generation direction",
      });
      continue;
    }
    const directions = (planRow.plan?.directions ?? []).slice(0, maxDirections);
    if (!directions.length) {
      omissions.push({
        query_id: record.id,
        status: "abstained",
        reason: planRow.plan?.notice ?? "Curify returned no direction",
      });
      continue;
    }
    directions.forEach((direction, offset) => {
      const template = templateById.get(direction.template_id);
      const locale = record.language === "en" ? "en" : "zh";
      const basePrompt = template ? chooseBasePrompt(template, locale) : null;
      if (!basePrompt) {
        omissions.push({
          query_id: record.id,
          status: "prompt_error",
          reason: `Missing base prompt for ${direction.template_id}`,
        });
        return;
      }
      const rank = offset + 1;
      jobs.push(
        imageJob({
          prompt: fillPrompt(basePrompt, direction.params ?? {}),
          out: outputName(record.id, rank, direction.template_id, record.query),
          queryId: record.id,
          direction: rank,
          metadata: {
            system: "curify",
            stage,
            partition: record.partition,
            language: record.language,
            source_query: record.query,
            plan_source: planRow.plan.source,
            template_id: direction.template_id,
            params: direction.params,
            confidence: direction.confidence,
            reason: direction.reason,
            prompt_policy: "curify-template-filled-prompt",
          },
        }),
      );
    });
  }
  return { jobs, omissions };
}

async function postJson(url, body, maxAttempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(180_000),
      });
      const text = await response.text();
      let payload;
      try {
        payload = JSON.parse(text);
      } catch {
        throw new Error(`HTTP ${response.status}: ${text.slice(0, 300)}`);
      }
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${payload.error ?? text.slice(0, 300)}`);
      }
      return { payload, attempts: attempt };
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 2000 * attempt));
      }
    }
  }
  throw lastError;
}

async function buildPlans({
  records,
  planPath,
  baseUrl,
  dryRun = false,
  concurrency = 4,
}) {
  const existing = new Map(
    readJsonl(planPath).map((row) => [row.query_id, row]),
  );
  const rows = records.map((record) => {
    const cached = existing.get(record.id);
    if (cached && cached.query === record.query && cached.language === record.language) {
      return cached;
    }
    return {
      query_id: record.id,
      query: record.query,
      language: record.language,
      status: "pending",
      attempts: 0,
      plan: null,
      error: null,
      cache_invalidated:
        cached == null ? null : "query_or_language_changed",
    };
  });
  writeJsonl(planPath, rows);
  if (dryRun) return rows;
  const pendingIndexes = rows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => !["completed", "abstained"].includes(row.status))
    .map(({ index }) => index);
  let cursor = 0;
  const worker = async () => {
    while (cursor < pendingIndexes.length) {
      const pendingPosition = cursor;
      cursor += 1;
      const index = pendingIndexes[pendingPosition];
      const row = rows[index];
      try {
        const { payload, attempts } = await postJson(
          `${baseUrl.replace(/\/+$/, "")}/api/search-generation-plan`,
          {
            query: row.query,
            locale: row.language === "en" ? "en" : "zh",
          },
        );
        row.attempts += attempts;
        row.plan = payload;
        row.notice = payload.notice ?? null;
        row.status = payload.directions?.length ? "completed" : "abstained";
        row.error = null;
      } catch (error) {
        row.attempts += 3;
        row.status = "failed";
        row.error = error instanceof Error ? error.message : String(error);
      }
      row.updated_at = new Date().toISOString();
      // Synchronous checkpoint writes make concurrent workers interruption-safe.
      writeJsonl(planPath, rows);
      console.log(
        `[plan ${pendingPosition + 1}/${pendingIndexes.length}] ${row.query_id}: ${row.status}`,
      );
    }
  };
  const workerCount = Math.max(
    1,
    Math.min(Number(concurrency) || 1, pendingIndexes.length || 1),
  );
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return rows;
}

function terminalFailureMap(filePath) {
  return new Map(readJsonl(filePath).map((row) => [row.out, row]));
}

function terminalFailureForJob(job, failures) {
  const failure = failures.get(job.out);
  if (!failure) return null;
  return failure.prompt_sha256 === sha256(job.prompt) ? failure : null;
}

function pendingJobs(jobs, outDir, failures = new Map()) {
  const absolute = resolveRoot(outDir);
  return jobs.filter((job) => {
    const filePath = path.join(absolute, job.out);
    const missing = !fs.existsSync(filePath) || fs.statSync(filePath).size === 0;
    return missing && !terminalFailureForJob(job, failures);
  });
}

function jobResult(job, outDir, failures = new Map()) {
  const filePath = path.join(resolveRoot(outDir), job.out);
  if (!fs.existsSync(filePath) || fs.statSync(filePath).size === 0) {
    const failure = terminalFailureForJob(job, failures);
    if (failure) {
      return {
        ...job,
        status: "failed",
        failure_reason: failure.reason,
        failed_at: failure.marked_at,
        local_path: null,
        bytes: 0,
        sha256: null,
      };
    }
    return { ...job, status: "pending", local_path: null, bytes: 0, sha256: null };
  }
  const stats = fs.statSync(filePath);
  return {
    ...job,
    status: "completed",
    local_path: path.relative(ROOT, filePath),
    bytes: stats.size,
    sha256: sha256File(filePath),
  };
}

function summarizeImagegenLog(logPath) {
  if (!fs.existsSync(logPath)) return null;
  const allText = fs.readFileSync(logPath, "utf8");
  const segmentStarts = [
    ...allText.matchAll(/^\[\d{4}-\d{2}-\d{2}T.*?\] pending=/gm),
  ];
  const lastText = segmentStarts.length
    ? allText.slice(segmentStarts.at(-1).index)
    : allText;
  const summarize = (text) => {
    const count = (pattern) => (text.match(pattern) ?? []).length;
    const exitCodes = [...text.matchAll(/exit_code=(\d+)/g)].map((match) =>
      Number(match[1]),
    );
    return {
      completed_attempts: count(/completed in/g),
      moderation_blocked: count(/moderation_blocked/g),
      billing_hard_limit_reached: count(/billing_hard_limit_reached/g),
      last_exit_code: exitCodes.length ? exitCodes.at(-1) : null,
    };
  };
  return {
    path: path.relative(ROOT, logPath),
    ...summarize(allText),
    last_run: summarize(lastText),
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderGalleryHtml({ stage, records, gptResults, curifyResults, omissions }) {
  const group = (rows) => {
    const grouped = new Map();
    for (const row of rows) {
      const values = grouped.get(row.vir_query_id) ?? [];
      values.push(row);
      grouped.set(row.vir_query_id, values);
    }
    return grouped;
  };
  const gptByQuery = group(gptResults);
  const curifyByQuery = group(curifyResults);
  const omissionByQuery = new Map(
    (omissions ?? []).map((item) => [item.query_id, item]),
  );
  const renderRows = (rows, system) => {
    if (!rows.length) return '<p class="missing">No image task.</p>';
    return rows
      .map((row) => {
        const template = row.vir_metadata?.template_id;
        const caption = [
          `direction ${row.vir_direction}`,
          template,
          row.status,
        ]
          .filter(Boolean)
          .join(" · ");
        const source = row.local_path
          ? path.posix.join(
              system,
              path.basename(row.local_path),
            )
          : null;
        return `<figure>${
          source
            ? `<img loading="lazy" src="${escapeHtml(source)}" alt="${escapeHtml(caption)}">`
            : '<div class="placeholder">Pending / failed</div>'
        }<figcaption>${escapeHtml(caption)}</figcaption></figure>`;
      })
      .join("");
  };
  const cards = records
    .map((record) => {
      const gpt = gptByQuery.get(record.id) ?? [];
      const curify = curifyByQuery.get(record.id) ?? [];
      const omission = omissionByQuery.get(record.id);
      return `<article><header><code>${escapeHtml(record.id)}</code><h2>${escapeHtml(record.query)}</h2><p>${escapeHtml(record.language)} · ${escapeHtml(record.partition)} · ${escapeHtml(record.difficulty)}</p></header><div class="systems"><section><h3>GPT-direct</h3><div class="images">${renderRows(gpt, "gpt-direct")}</div></section><section><h3>Curify</h3>${
        omission
          ? `<p class="notice">${escapeHtml(omission.status)}: ${escapeHtml(omission.reason)}</p>`
          : ""
      }<div class="images">${renderRows(curify, "curify")}</div></section></div></article>`;
    })
    .join("\n");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VIR v2 ${escapeHtml(stage)} image gallery</title><style>body{font-family:ui-sans-serif,system-ui;margin:0;background:#f5f5f2;color:#171714}main{max-width:1500px;margin:auto;padding:32px}h1{margin-bottom:4px}.meta{color:#666;margin-top:0}article{background:#fff;border:1px solid #ddd;border-radius:14px;padding:20px;margin:22px 0}header h2{margin:8px 0;font-size:1.25rem}header p,figcaption{color:#666}.systems{display:grid;grid-template-columns:1fr 1fr;gap:20px}.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}figure{margin:0}img,.placeholder{width:100%;aspect-ratio:4/3;object-fit:contain;background:#eee;border-radius:8px}.placeholder{display:grid;place-items:center;color:#777}.notice{padding:10px;background:#fff3cd;border-radius:8px}.missing{color:#777}@media(max-width:800px){.systems{grid-template-columns:1fr}}</style></head><body><main><h1>VIR v2 paired image gallery — ${escapeHtml(stage)}</h1><p class="meta">Human inspection only. Images are not included in routing accuracy metrics.</p>${cards}</main></body></html>`;
}

function runPaths(runId, stage) {
  const stageDir = resolveRoot(`reports/vir_v2/images/${runId}/${stage}`);
  return {
    stageDir,
    records: path.join(stageDir, "records.jsonl"),
    plans: path.join(stageDir, "curify-plans.jsonl"),
    gptInput: path.join(stageDir, "gpt-direct-input.jsonl"),
    gptPending: path.join(stageDir, "gpt-direct-pending.jsonl"),
    curifyInput: path.join(stageDir, "curify-input.jsonl"),
    curifyPending: path.join(stageDir, "curify-pending.jsonl"),
    pairedPending: path.join(stageDir, "paired-pending.jsonl"),
    gptOut: path.join(stageDir, "gpt-direct"),
    curifyOut: path.join(stageDir, "curify"),
    gptTerminalFailures: path.join(
      stageDir,
      "gpt-direct-terminal-failures.jsonl",
    ),
    curifyTerminalFailures: path.join(
      stageDir,
      "curify-terminal-failures.jsonl",
    ),
    manifest: path.join(stageDir, "stage-manifest.json"),
  };
}

async function prepare(options) {
  const stage = options.stage;
  if (!stage) throw new Error("prepare requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const paths = runPaths(runId, stage);
  fs.mkdirSync(paths.gptOut, { recursive: true });
  fs.mkdirSync(paths.curifyOut, { recursive: true });
  let records = stageRecords(stage);
  if (options.limit) records = records.slice(0, Number(options.limit));
  writeJsonl(paths.records, records);
  const gptJobs = buildGptJobs(records, stage);
  const gptFailures = terminalFailureMap(paths.gptTerminalFailures);
  const curifyFailures = terminalFailureMap(paths.curifyTerminalFailures);
  writeJsonl(paths.gptInput, gptJobs);
  const pendingGptJobs = pendingJobs(gptJobs, paths.gptOut, gptFailures);
  writeJsonl(paths.gptPending, pendingGptJobs);

  const plans = await buildPlans({
    records,
    planPath: paths.plans,
    baseUrl: options.base_url ?? DEFAULT_BASE_URL,
    dryRun: Boolean(options.dry_run),
    concurrency: Number(options.plan_concurrency ?? 4),
  });
  const templates = readJson(
    options.catalog ?? "../../curify-frontend/public/data/nano_templates.json",
  );
  const { jobs: curifyJobs, omissions } = buildCurifyJobs(
    records,
    plans,
    templates,
    stage,
  );
  writeJsonl(paths.curifyInput, curifyJobs);
  const pendingCurifyJobs = pendingJobs(
    curifyJobs,
    paths.curifyOut,
    curifyFailures,
  );
  writeJsonl(paths.curifyPending, pendingCurifyJobs);
  const terminalGptJobs = gptJobs.filter((job) =>
    terminalFailureForJob(job, gptFailures),
  );
  const terminalCurifyJobs = curifyJobs.filter((job) =>
    terminalFailureForJob(job, curifyFailures),
  );
  const pairedPending = [
    ...pendingGptJobs.map((job) => ({
      ...job,
      out: path.posix.join("gpt-direct", job.out),
    })),
    ...pendingCurifyJobs.map((job) => ({
      ...job,
      out: path.posix.join("curify", job.out),
    })),
  ];
  writeJsonl(paths.pairedPending, pairedPending);
  const manifest = {
    schema_version: 1,
    run_id: runId,
    stage,
    prepared_at: new Date().toISOString(),
    record_count: records.length,
    record_ids_sha256: sha256(records.map((record) => record.id).join("\n")),
    image_model: DEFAULT_IMAGE_MODEL,
    generation_config: {
      size: "auto",
      quality: "medium",
      output_format: "jpeg",
      output_compression: 90,
      same_image_backend_for_both_systems: true,
    },
    gpt_direct: {
      total_jobs: gptJobs.length,
      completed_jobs:
        gptJobs.length - pendingGptJobs.length - terminalGptJobs.length,
      terminal_failed_jobs: terminalGptJobs.length,
      pending_jobs: pendingGptJobs.length,
      input: path.relative(ROOT, paths.gptPending),
      output_dir: path.relative(ROOT, paths.gptOut),
    },
    curify: {
      plan_completed: plans.filter((row) => row.status === "completed").length,
      plan_abstained: plans.filter((row) => row.status === "abstained").length,
      plan_failed: plans.filter((row) => row.status === "failed").length,
      total_jobs: curifyJobs.length,
      completed_jobs:
        curifyJobs.length - pendingCurifyJobs.length - terminalCurifyJobs.length,
      terminal_failed_jobs: terminalCurifyJobs.length,
      pending_jobs: pendingCurifyJobs.length,
      omissions,
      input: path.relative(ROOT, paths.curifyPending),
      output_dir: path.relative(ROOT, paths.curifyOut),
    },
    paired_generation: {
      pending_jobs: pairedPending.length,
      inventory: path.relative(ROOT, paths.pairedPending),
      render_inputs: [
        path.relative(ROOT, paths.gptPending),
        path.relative(ROOT, paths.curifyPending),
      ],
    },
  };
  writeJson(paths.manifest, manifest);
  console.log(JSON.stringify({ ...manifest, paths }, null, 2));
  return { manifest, paths };
}

function finalize(options) {
  const stage = options.stage;
  if (!stage) throw new Error("finalize requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const paths = runPaths(runId, stage);
  const previous = readJson(paths.manifest);
  const gptFailures = terminalFailureMap(paths.gptTerminalFailures);
  const curifyFailures = terminalFailureMap(paths.curifyTerminalFailures);
  const gptResults = readJsonl(paths.gptInput).map((job) =>
    jobResult(job, paths.gptOut, gptFailures),
  );
  const curifyResults = readJsonl(paths.curifyInput).map((job) =>
    jobResult(job, paths.curifyOut, curifyFailures),
  );
  writeJsonl(path.join(paths.stageDir, "gpt-direct-results.jsonl"), gptResults);
  writeJsonl(path.join(paths.stageDir, "curify-results.jsonl"), curifyResults);
  const summarize = (rows) => ({
    total: rows.length,
    completed: rows.filter((row) => row.status === "completed").length,
    failed: rows.filter((row) => row.status === "failed").length,
    pending: rows.filter((row) => row.status === "pending").length,
    bytes: rows.reduce((total, row) => total + row.bytes, 0),
  });
  const galleryPath = path.join(paths.stageDir, "gallery.html");
  fs.writeFileSync(
    galleryPath,
    renderGalleryHtml({
      stage,
      records: readJsonl(paths.records),
      gptResults,
      curifyResults,
      omissions: previous.curify.omissions,
    }),
  );
  const manifest = {
    ...previous,
    finalized_at: new Date().toISOString(),
    gpt_direct: { ...previous.gpt_direct, ...summarize(gptResults) },
    curify: { ...previous.curify, ...summarize(curifyResults) },
    execution_logs: {
      gpt_direct: summarizeImagegenLog(
        path.join(paths.stageDir, "gpt-direct-imagegen.log"),
      ),
      curify: summarizeImagegenLog(
        path.join(paths.stageDir, "curify-imagegen.log"),
      ),
    },
    gallery: path.relative(ROOT, galleryPath),
  };
  manifest.blocking_error = Object.values(manifest.execution_logs).some(
    (entry) => entry?.last_run?.billing_hard_limit_reached > 0,
  )
    ? "billing_hard_limit_reached"
    : null;
  writeJson(paths.manifest, manifest);
  console.log(JSON.stringify(manifest, null, 2));
  return manifest;
}

function markTerminal(options) {
  const stage = options.stage;
  if (!stage) throw new Error("mark-terminal requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const paths = runPaths(runId, stage);
  const system = options.system ?? "paired";
  const reason = options.reason ?? "moderation_blocked_after_retry";
  const targets = {
    "gpt-direct": {
      input: paths.gptInput,
      outDir: paths.gptOut,
      ledger: paths.gptTerminalFailures,
    },
    curify: {
      input: paths.curifyInput,
      outDir: paths.curifyOut,
      ledger: paths.curifyTerminalFailures,
    },
  };
  const systems = system === "paired" ? ["gpt-direct", "curify"] : [system];
  if (systems.some((name) => !targets[name])) {
    throw new Error(`Unknown terminal-failure system: ${system}`);
  }
  const summary = {};
  for (const name of systems) {
    const target = targets[name];
    const jobs = readJsonl(target.input);
    const existing = terminalFailureMap(target.ledger);
    const missing = jobs.filter((job) => {
      const filePath = path.join(resolveRoot(target.outDir), job.out);
      return !fs.existsSync(filePath) || fs.statSync(filePath).size === 0;
    });
    for (const job of missing) {
      existing.set(job.out, {
        schema_version: 1,
        run_id: runId,
        stage,
        system: name,
        query_id: job.vir_query_id,
        direction: job.vir_direction,
        out: job.out,
        prompt_sha256: sha256(job.prompt),
        status: "terminal_failed",
        reason,
        marked_at: new Date().toISOString(),
      });
    }
    writeJsonl(
      target.ledger,
      [...existing.values()].sort((a, b) => a.out.localeCompare(b.out)),
    );
    summary[name] = {
      marked: missing.length,
      ledger: path.relative(ROOT, target.ledger),
    };
  }
  console.log(JSON.stringify(summary, null, 2));
  return summary;
}

async function render(options) {
  const stage = options.stage;
  if (!stage) throw new Error("render requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const paths = runPaths(runId, stage);
  const system = options.system ?? "paired";
  const targets = {
    "gpt-direct": {
      input: paths.gptPending,
      outDir: paths.gptOut,
    },
    curify: {
      input: paths.curifyPending,
      outDir: paths.curifyOut,
    },
  };
  const systems = system === "paired" ? ["gpt-direct", "curify"] : [system];
  if (systems.some((name) => !targets[name])) {
    throw new Error(`Unknown render system: ${system}`);
  }

  const envFile = resolveRoot(
    options.env_file ?? "../../curify-frontend/.env.local",
  );
  if (!process.env.OPENAI_API_KEY && fs.existsSync(envFile)) {
    process.loadEnvFile(envFile);
  }
  if (!process.env.OPENAI_API_KEY && !options.dry_run) {
    throw new Error(`OPENAI_API_KEY is missing (checked ${envFile})`);
  }

  const python = options.python ?? process.env.VIR_IMAGEGEN_PYTHON ?? "python3";
  const imageCli = resolveRoot(
    options.image_cli ??
      path.join(
        os.homedir(),
        ".codex/skills/.system/imagegen/scripts/image_gen.py",
      ),
  );
  const results = [];
  for (const name of systems) {
    const target = targets[name];
    if (!fs.existsSync(target.input)) {
      throw new Error(`Missing prepared input: ${target.input}`);
    }
    const pendingCount = readJsonl(target.input).length;
    if (!pendingCount) {
      console.log(`No pending ${name} image jobs for ${stage}.`);
      results.push({ system: name, pendingCount: 0, exitCode: 0 });
      continue;
    }
    const args = [
      imageCli,
      "generate-batch",
      "--input",
      target.input,
      "--out-dir",
      target.outDir,
      "--concurrency",
      String(options.concurrency ?? 4),
      "--max-attempts",
      String(options.max_attempts ?? 3),
      "--no-augment",
    ];
    if (options.dry_run) args.push("--dry-run");
    const logPath = path.join(paths.stageDir, `${name}-imagegen.log`);
    const log = fs.createWriteStream(logPath, { flags: "a" });
    log.write(
      `\n[${new Date().toISOString()}] pending=${pendingCount} concurrency=${options.concurrency ?? 4}\n`,
    );
    console.log(
      `Rendering ${pendingCount} ${name} jobs for ${stage}; log=${path.relative(ROOT, logPath)}`,
    );
    const result = await new Promise((resolve, reject) => {
      const child = spawn(python, args, {
        cwd: ROOT,
        env: process.env,
        stdio: ["ignore", "pipe", "pipe"],
      });
      let blockingError = null;
      const forward = (stream, destination) => {
        stream.on("data", (chunk) => {
          destination.write(chunk);
          log.write(chunk);
          if (
            !blockingError &&
            chunk.toString().includes("billing_hard_limit_reached")
          ) {
            blockingError = "billing_hard_limit_reached";
            const notice =
              "Billing hard limit detected; terminating the batch to prevent repeated rejected calls.\n";
            process.stderr.write(notice);
            log.write(notice);
            child.kill("SIGTERM");
          }
        });
      };
      forward(child.stdout, process.stdout);
      forward(child.stderr, process.stderr);
      child.once("error", (error) => {
        log.end(`\nspawn_error=${error.message}\n`);
        reject(error);
      });
      child.once("close", (code, signal) => {
        const exitCode = code ?? 1;
        log.end(`\nexit_code=${exitCode} signal=${signal ?? "none"}\n`);
        resolve({
          system: name,
          pendingCount,
          exitCode,
          signal,
          blockingError,
          logPath,
        });
      });
    });
    results.push(result);
    if (result.blockingError) break;
  }
  const failed = results.filter((result) => result.exitCode !== 0);
  if (failed.length) {
    throw new Error(
      `${failed.map((result) => result.system).join(", ")} image batch failed partially; completed files are preserved. Re-run prepare to emit only missing jobs.`,
    );
  }
  return results;
}

function help() {
  console.log(`VIR v2 paired image task builder

Usage:
  node scripts/vir-image-tasks.cjs prepare --stage anchors [--plan-concurrency 4] [--run-id ${DEFAULT_RUN_ID}]
  node scripts/vir-image-tasks.cjs render --stage anchors [--system paired] [--python /path/to/python]
  node scripts/vir-image-tasks.cjs mark-terminal --stage anchors [--system paired] [--reason moderation_blocked_after_retry]
  node scripts/vir-image-tasks.cjs finalize --stage anchors [--run-id ${DEFAULT_RUN_ID}]

Stages: anchors | exploration | core | challenge-gap

prepare calls the local Curify generation-plan API, then writes two JSONL files
for the standard imagegen CLI. Re-running prepare preserves completed plans and
emits only missing image jobs in *-pending.jsonl.`);
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  if (command === "prepare") await prepare(options);
  else if (command === "render") await render(options);
  else if (command === "mark-terminal") markTerminal(options);
  else if (command === "finalize") finalize(options);
  else help();
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack ?? error.message ?? error);
    process.exitCode = 1;
  });
}

module.exports = {
  buildCurifyJobs,
  buildGptJobs,
  fillPrompt,
  gptPrompt,
  jobResult,
  markTerminal,
  outputName,
  parseArgs,
  pendingJobs,
  render,
  renderGalleryHtml,
  stageRecords,
  summarizeImagegenLog,
};
