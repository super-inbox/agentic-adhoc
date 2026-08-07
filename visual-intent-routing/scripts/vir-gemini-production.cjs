#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const {
  buildCurifyJobs,
  stageRecords,
} = require("./vir-image-tasks.cjs");
const {
  queryFolderNames,
  queryImageName,
  queryImageStem,
  systemImageName,
} = require("./vir-image-names.cjs");

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_RUN_ID = "2026-08-03-production-gemini";
const DEFAULT_PLAN_SOURCE_RUN = DEFAULT_RUN_ID;
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

function productionSlug(runId, stage, queryId, direction, templateId, query = null) {
  return queryImageStem(query ?? queryId, queryId, direction);
}

function runPaths(runId, stage) {
  const stageDir = resolveRoot(`reports/vir_v2/images/${runId}/${stage}`);
  const byQueryDir = path.join(stageDir, "by-query");
  return {
    stageDir,
    byQueryDir,
    records: path.join(stageDir, "records.jsonl"),
    plans: path.join(stageDir, "curify-plans.jsonl"),
    input: path.join(stageDir, "curify-gemini-input.jsonl"),
    pending: path.join(stageDir, "curify-gemini-pending.jsonl"),
    results: path.join(stageDir, "curify-gemini-results.jsonl"),
    events: path.join(stageDir, "curify-gemini-events.jsonl"),
    outDir: byQueryDir,
    legacyCurifyOut: path.join(stageDir, "curify-gemini"),
    gptResults: path.join(stageDir, "gpt-direct-results.jsonl"),
    gptInput: path.join(stageDir, "gpt-direct-input.jsonl"),
    gptPending: path.join(stageDir, "gpt-direct-pending.jsonl"),
    gptTerminal: path.join(stageDir, "gpt-direct-terminal-failures.jsonl"),
    gptOut: byQueryDir,
    legacyGptOut: path.join(stageDir, "gpt-direct"),
    filenameMigration: path.join(stageDir, "query-filename-migration.json"),
    folderMigration: path.join(stageDir, "query-folder-migration.json"),
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
  const folderRecords = new Map(curifyJobs.map((job) => [
    job.vir_query_id,
    { id: job.vir_query_id, query: job.vir_metadata.source_query },
  ]));
  const folderByQueryId = queryFolderNames([...folderRecords.values()]);
  return curifyJobs.map((job) => {
    const metadata = job.vir_metadata;
    const slug = productionSlug(
      runId,
      stage,
      job.vir_query_id,
      job.vir_direction,
      metadata.template_id,
      metadata.source_query,
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
      query_directory: folderByQueryId.get(job.vir_query_id),
      local_basename: systemImageName(
        "curify-gemini",
        job.vir_direction,
        "jpg",
      ).replace(/\.jpg$/, ""),
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
    const candidate = path.join(
      absolute,
      job.query_directory ?? "",
      `${job.local_basename ?? job.slug}.${extension}`,
    );
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
      const finalPath = path.join(
        absoluteOutDir,
        job.query_directory ?? "",
        `${job.local_basename ?? job.slug}.${extension}`,
      );
      fs.mkdirSync(path.dirname(finalPath), { recursive: true });
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

function normalizeIntegratedGptResults(rows, outDir) {
  const absoluteOutDir = resolveRoot(outDir);
  return rows.map((row) => {
    const outputName = row.out ?? (row.local_path ? path.basename(row.local_path) : null);
    const output = outputName ? path.join(absoluteOutDir, outputName) : null;
    if (!output || !fs.existsSync(output) || fs.statSync(output).size === 0) {
      if (row.status === "failed") return row;
      return {
        ...row,
        status: "pending",
        local_path: null,
        bytes: 0,
        sha256: null,
      };
    }
    const stats = fs.statSync(output);
    return {
      ...row,
      status: "completed",
      local_path: path.relative(ROOT, output),
      bytes: stats.size,
      sha256: sha256File(output),
    };
  });
}

function imageIdentity(row) {
  return {
    queryId: row.vir_query_id ?? row.query_id,
    direction: row.vir_direction ?? row.direction,
  };
}

function queryForImage(row, recordById) {
  const { queryId } = imageIdentity(row);
  const query = recordById.get(queryId)?.query ??
    row.query ??
    row.vir_metadata?.source_query;
  if (!queryId || directionForImage(row) == null || !query) {
    throw new Error(`Cannot derive query filename identity: ${JSON.stringify(row)}`);
  }
  return query;
}

function directionForImage(row) {
  return row.vir_direction ?? row.direction;
}

function listImages(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory)
    .filter((name) => /\.(?:jpe?g|png|webp)$/i.test(name))
    .map((name) => path.join(directory, name));
}

function completedRenamePlan({ system, rows, outDir, recordById }) {
  return rows
    .filter((row) => row.status === "completed")
    .map((row) => {
      const { queryId, direction } = imageIdentity(row);
      const query = queryForImage(row, recordById);
      const oldName = row.local_path
        ? path.basename(row.local_path)
        : system === "gpt-direct"
          ? path.basename(row.out)
          : null;
      if (!oldName) throw new Error(`Completed ${system} row has no filename: ${queryId}`);
      const extension = path.extname(oldName).slice(1);
      const newName = queryImageName(query, queryId, direction, extension);
      const source = path.join(outDir, oldName);
      const destination = path.join(outDir, newName);
      return {
        system,
        query_id: queryId,
        query,
        direction,
        from: path.relative(ROOT, source),
        to: path.relative(ROOT, destination),
        source,
        destination,
        bytes: row.bytes ?? null,
        sha256: row.sha256 ?? null,
      };
    });
}

function preflightRenamePlan(plan, outputDirectories) {
  const destinations = new Set();
  for (const entry of plan) {
    const collisionKey = entry.destination.normalize("NFKC").toLowerCase();
    if (destinations.has(collisionKey)) {
      throw new Error(`Query filename collision: ${entry.destination}`);
    }
    destinations.add(collisionKey);
    if (entry.source === entry.destination) continue;
    if (!fs.existsSync(entry.source)) {
      if (fs.existsSync(entry.destination) &&
          (!entry.sha256 || sha256File(entry.destination) === entry.sha256)) {
        continue;
      }
      throw new Error(`Missing source image: ${entry.source}`);
    }
    if (fs.existsSync(entry.destination)) {
      throw new Error(`Refusing to overwrite query image: ${entry.destination}`);
    }
  }
  const plannedSources = new Set(plan.map((entry) => entry.source));
  const plannedDestinations = new Set(plan.map((entry) => entry.destination));
  for (const directory of outputDirectories) {
    for (const image of listImages(directory)) {
      if (!plannedSources.has(image) && !plannedDestinations.has(image)) {
        throw new Error(`Unindexed image blocks filename migration: ${image}`);
      }
    }
  }
}

function updateGptFilenameRow(row, recordById, outDir) {
  const { queryId, direction } = imageIdentity(row);
  if (!queryId || direction == null) return row;
  const query = queryForImage(row, recordById);
  const extension = path.extname(row.out ?? row.local_path ?? "image.jpeg").slice(1) || "jpeg";
  const out = queryImageName(query, queryId, direction, extension);
  const updated = { ...row, out };
  if (row.local_path) updated.local_path = path.relative(ROOT, path.join(outDir, out));
  return updated;
}

function updateCurifyFilenameRow(row, recordById, outDir) {
  const { queryId, direction } = imageIdentity(row);
  if (!queryId || direction == null) return row;
  const query = queryForImage(row, recordById);
  const slug = queryImageStem(query, queryId, direction);
  const updated = { ...row, slug };
  if (row.local_path) {
    const extension = path.extname(row.local_path).slice(1);
    updated.local_path = path.relative(ROOT, path.join(outDir, `${slug}.${extension}`));
  }
  return updated;
}

function rewriteJsonlRows(filePath, transform) {
  if (!fs.existsSync(filePath)) return 0;
  const rows = readJsonl(filePath).map(transform);
  writeJsonl(filePath, rows);
  return rows.length;
}

function renameQueryFiles(options) {
  const stage = options.stage;
  if (!stage) throw new Error("rename-query-files requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const paths = runPaths(runId, stage);
  const records = readJsonl(paths.records);
  const recordById = new Map(records.map((record) => [record.id, record]));
  if (!records.length) throw new Error(`Missing stage records: ${paths.records}`);

  const gptRows = readJsonl(paths.gptResults);
  const curifyRows = readJsonl(paths.results);
  const plan = [
    ...completedRenamePlan({
      system: "gpt-direct",
      rows: gptRows,
      outDir: paths.gptOut,
      recordById,
    }),
    ...completedRenamePlan({
      system: "curify-gemini",
      rows: curifyRows,
      outDir: paths.outDir,
      recordById,
    }),
  ];
  preflightRenamePlan(plan, [paths.gptOut, paths.outDir]);

  let renamed = 0;
  for (const entry of plan) {
    if (entry.source !== entry.destination && fs.existsSync(entry.source)) {
      fs.renameSync(entry.source, entry.destination);
      renamed += 1;
    }
    if (!fs.existsSync(entry.destination)) {
      throw new Error(`Renamed image is missing: ${entry.destination}`);
    }
    const digest = sha256File(entry.destination);
    if (entry.sha256 && digest !== entry.sha256) {
      throw new Error(`SHA256 changed while renaming: ${entry.destination}`);
    }
    entry.sha256 = digest;
    entry.bytes = fs.statSync(entry.destination).size;
    delete entry.source;
    delete entry.destination;
  }

  const gptTransform = (row) => updateGptFilenameRow(row, recordById, paths.gptOut);
  const curifyTransform = (row) => updateCurifyFilenameRow(row, recordById, paths.outDir);
  const rewritten = {
    gpt_input: rewriteJsonlRows(paths.gptInput, gptTransform),
    gpt_pending: rewriteJsonlRows(paths.gptPending, gptTransform),
    gpt_results: rewriteJsonlRows(paths.gptResults, gptTransform),
    gpt_terminal_failures: rewriteJsonlRows(paths.gptTerminal, gptTransform),
    curify_input: rewriteJsonlRows(paths.input, curifyTransform),
    curify_pending: rewriteJsonlRows(paths.pending, curifyTransform),
    curify_results: rewriteJsonlRows(paths.results, curifyTransform),
  };
  const migration = {
    schema_version: 1,
    naming_policy_version: "query-filename-v1",
    run_id: runId,
    stage,
    renamed_at: new Date().toISOString(),
    format: "<normalized-query>--<query-id>--d<direction>.<extension>",
    completed_images: plan.length,
    renamed_files: renamed,
    metadata_rows_rewritten: rewritten,
    entries: plan,
  };
  writeJson(paths.filenameMigration, migration);
  finalize(options);
  console.log(JSON.stringify({ stage, renamed_files: renamed, completed_images: plan.length }, null, 2));
  return migration;
}

function groupedRenamePlan({ system, rows, byQueryDir, recordById, folderById }) {
  return rows
    .filter((row) => row.status === "completed")
    .map((row) => {
      const { queryId, direction } = imageIdentity(row);
      const query = queryForImage(row, recordById);
      if (!row.local_path) throw new Error(`Completed ${system} row has no local_path: ${queryId}`);
      const source = resolveRoot(row.local_path);
      const extension = path.extname(source).slice(1);
      const folder = folderById.get(queryId);
      const filename = systemImageName(system, direction, extension);
      const destination = path.join(byQueryDir, folder, filename);
      return {
        system,
        query_id: queryId,
        query,
        query_folder: folder,
        direction,
        from: path.relative(ROOT, source),
        to: path.relative(ROOT, destination),
        source,
        destination,
        bytes: row.bytes ?? null,
        sha256: row.sha256 ?? null,
      };
    });
}

function updateGroupedGptRow(row, recordById, folderById, byQueryDir) {
  const { queryId, direction } = imageIdentity(row);
  if (!queryId || direction == null) return row;
  queryForImage(row, recordById);
  const extension = path.extname(row.out ?? row.local_path ?? "image.jpeg").slice(1) || "jpeg";
  const out = path.posix.join(
    folderById.get(queryId),
    systemImageName("gpt-direct", direction, extension),
  );
  const updated = { ...row, out };
  if (row.local_path) updated.local_path = path.relative(ROOT, path.join(byQueryDir, out));
  return updated;
}

function updateGroupedCurifyRow(row, recordById, folderById, byQueryDir) {
  const { queryId, direction } = imageIdentity(row);
  if (!queryId || direction == null) return row;
  queryForImage(row, recordById);
  const queryDirectory = folderById.get(queryId);
  const updated = {
    ...row,
    query_directory: queryDirectory,
    local_basename: systemImageName("curify-gemini", direction, "jpg").replace(/\.jpg$/, ""),
  };
  if (row.local_path) {
    const extension = path.extname(row.local_path).slice(1);
    const filename = systemImageName("curify-gemini", direction, extension);
    updated.local_path = path.relative(
      ROOT,
      path.join(byQueryDir, queryDirectory, filename),
    );
  }
  return updated;
}

function writeQueryManifests({ paths, records, folderById, omissions }) {
  const gptById = new Map();
  for (const row of readJsonl(paths.gptResults)) {
    const values = gptById.get(row.vir_query_id) ?? [];
    values.push(row);
    gptById.set(row.vir_query_id, values);
  }
  const curifyById = new Map();
  for (const row of readJsonl(paths.results)) {
    const values = curifyById.get(row.query_id) ?? [];
    values.push(row);
    curifyById.set(row.query_id, values);
  }
  const omissionById = new Map(omissions.map((row) => [row.query_id, row]));
  let written = 0;
  for (const record of records) {
    const gptRows = gptById.get(record.id) ?? [];
    const curifyRows = curifyById.get(record.id) ?? [];
    if (![...gptRows, ...curifyRows].some((row) => row.status === "completed")) continue;
    const folder = path.join(paths.byQueryDir, folderById.get(record.id));
    fs.mkdirSync(folder, { recursive: true });
    const summarize = (rows, system) => rows.map((row) => ({
      system,
      direction: row.vir_direction ?? row.direction,
      status: row.status,
      local_path: row.local_path ?? null,
      template_id: row.template_id ?? null,
      model: row.model ?? null,
      bytes: row.bytes ?? 0,
      sha256: row.sha256 ?? null,
    }));
    writeJson(path.join(folder, "query-manifest.json"), {
      schema_version: 1,
      query_id: record.id,
      query: record.query,
      language: record.language,
      partition: record.partition,
      difficulty: record.difficulty,
      stage: record.stage ?? null,
      query_folder: path.relative(paths.stageDir, folder),
      images: [
        ...summarize(gptRows, "gpt-direct"),
        ...summarize(curifyRows, "curify-gemini"),
      ],
      curify_omission: omissionById.get(record.id) ?? null,
    });
    written += 1;
  }
  return written;
}

function groupByQuery(options) {
  const stage = options.stage;
  if (!stage) throw new Error("group-by-query requires --stage");
  const runId = options.run_id ?? DEFAULT_RUN_ID;
  const paths = runPaths(runId, stage);
  const records = readJsonl(paths.records);
  if (!records.length) throw new Error(`Missing stage records: ${paths.records}`);
  const recordById = new Map(records.map((record) => [record.id, record]));
  const folderById = queryFolderNames(records);
  const gptRows = readJsonl(paths.gptResults);
  const curifyRows = readJsonl(paths.results);
  const plan = [
    ...groupedRenamePlan({
      system: "gpt-direct",
      rows: gptRows,
      byQueryDir: paths.byQueryDir,
      recordById,
      folderById,
    }),
    ...groupedRenamePlan({
      system: "curify-gemini",
      rows: curifyRows,
      byQueryDir: paths.byQueryDir,
      recordById,
      folderById,
    }),
  ];
  preflightRenamePlan(plan, [paths.legacyGptOut, paths.legacyCurifyOut]);

  let moved = 0;
  for (const entry of plan) {
    if (entry.source !== entry.destination && fs.existsSync(entry.source)) {
      fs.mkdirSync(path.dirname(entry.destination), { recursive: true });
      fs.renameSync(entry.source, entry.destination);
      moved += 1;
    }
    if (!fs.existsSync(entry.destination)) {
      throw new Error(`Grouped image is missing: ${entry.destination}`);
    }
    const digest = sha256File(entry.destination);
    if (entry.sha256 && digest !== entry.sha256) {
      throw new Error(`SHA256 changed while grouping: ${entry.destination}`);
    }
    entry.sha256 = digest;
    entry.bytes = fs.statSync(entry.destination).size;
    delete entry.source;
    delete entry.destination;
  }

  const gptTransform = (row) =>
    updateGroupedGptRow(row, recordById, folderById, paths.byQueryDir);
  const curifyTransform = (row) =>
    updateGroupedCurifyRow(row, recordById, folderById, paths.byQueryDir);
  const rewritten = {
    gpt_input: rewriteJsonlRows(paths.gptInput, gptTransform),
    gpt_pending: rewriteJsonlRows(paths.gptPending, gptTransform),
    gpt_results: rewriteJsonlRows(paths.gptResults, gptTransform),
    gpt_terminal_failures: rewriteJsonlRows(paths.gptTerminal, gptTransform),
    curify_input: rewriteJsonlRows(paths.input, curifyTransform),
    curify_pending: rewriteJsonlRows(paths.pending, curifyTransform),
    curify_results: rewriteJsonlRows(paths.results, curifyTransform),
  };
  for (const directory of [paths.legacyGptOut, paths.legacyCurifyOut]) {
    if (fs.existsSync(directory) && fs.readdirSync(directory).length === 0) {
      fs.rmdirSync(directory);
    }
  }
  const migration = {
    schema_version: 1,
    layout_version: "query-folder-v1",
    run_id: runId,
    stage,
    grouped_at: new Date().toISOString(),
    format: "by-query/<normalized-query>/<system>--d<direction>.<extension>",
    completed_images: plan.length,
    moved_files: moved,
    metadata_rows_rewritten: rewritten,
    entries: plan,
  };
  writeJson(paths.folderMigration, migration);
  const updated = finalize(options);
  migration.query_manifests = writeQueryManifests({
    paths,
    records,
    folderById,
    omissions: updated.image_jobs.omissions ?? [],
  });
  writeJson(paths.folderMigration, migration);
  console.log(JSON.stringify({
    stage,
    moved_files: moved,
    completed_images: plan.length,
    query_folders: migration.query_manifests,
  }, null, 2));
  return migration;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function productionGallery({
  stage,
  stageDir = null,
  records,
  results,
  gptResults = [],
  omissions,
}) {
  const groupByQuery = (rows, idKey) => {
    const grouped = new Map();
    for (const row of rows) {
      const values = grouped.get(row[idKey]) ?? [];
      values.push(row);
      grouped.set(row[idKey], values);
    }
    return grouped;
  };
  const curifyByQuery = groupByQuery(results, "query_id");
  const gptByQuery = groupByQuery(gptResults, "vir_query_id");
  const omissionByQuery = new Map(omissions.map((row) => [row.query_id, row]));
  const renderRows = (rows, system) => rows.length
    ? rows.map((row) => {
        const isGpt = system === "gpt-direct";
        const direction = isGpt ? row.vir_direction : row.direction;
        const template = isGpt ? null : row.template_id;
        const src = row.local_path
          ? stageDir
            ? path.relative(stageDir, resolveRoot(row.local_path)).split(path.sep).join("/")
            : `${system}/${path.basename(row.local_path)}`
          : null;
        const caption = [
          template,
          `direction ${direction}`,
          row.status,
        ].filter(Boolean).join(" · ");
        return `<figure>${src ? `<img loading="lazy" src="${escapeHtml(src)}" alt="${escapeHtml(caption)}">` : '<div class="placeholder">Pending / failed</div>'}<figcaption>${escapeHtml(caption)}</figcaption></figure>`;
      }).join("")
    : '<p class="missing">No image task.</p>';
  const cards = records.map((record) => {
    const curifyRows = curifyByQuery.get(record.id) ?? [];
    const gptRows = gptByQuery.get(record.id) ?? [];
    const omission = omissionByQuery.get(record.id);
    return `<article><code>${escapeHtml(record.id)}</code><h2>${escapeHtml(record.query)}</h2><p>${escapeHtml(record.language)} · ${escapeHtml(record.partition)} · ${escapeHtml(record.difficulty)}</p>${omission ? `<p class="notice">${escapeHtml(omission.status)}: ${escapeHtml(omission.reason)}</p>` : ""}<div class="systems"><section><h3>GPT-direct · gpt-image-2</h3><div class="images">${renderRows(gptRows, "gpt-direct")}</div></section><section><h3>Curify · ${MODEL}</h3><div class="images">${renderRows(curifyRows, "curify-gemini")}</div></section></div></article>`;
  }).join("\n");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VIR v2 ${escapeHtml(stage)} production comparison</title><style>body{font-family:ui-sans-serif,system-ui;margin:0;background:#f5f5f2;color:#171714}main{max-width:1500px;margin:auto;padding:32px}article{background:#fff;border:1px solid #ddd;border-radius:14px;padding:20px;margin:22px 0}h2{margin:8px 0;font-size:1.25rem}p,figcaption{color:#666}.systems{display:grid;grid-template-columns:1fr 1fr;gap:20px}.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}figure{margin:0}img,.placeholder{width:100%;aspect-ratio:4/3;object-fit:contain;background:#eee;border-radius:8px}.placeholder{display:grid;place-items:center}.notice{padding:10px;background:#fff3cd;border-radius:8px}@media(max-width:800px){.systems{grid-template-columns:1fr}}</style></head><body><main><h1>VIR v2 production comparison — ${escapeHtml(stage)}</h1><p>GPT-direct uses gpt-image-2. Curify uses routing/template prompts and ${MODEL}. Image backends are intentionally not controlled; routing Gold metrics remain separate.</p>${cards}</main></body></html>`;
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
    image_naming: {
      policy_version: "query-folder-v1",
      format: "by-query/<normalized-query>/<system>--d<direction>.<extension>",
      migration_manifest: fs.existsSync(paths.folderMigration)
        ? path.relative(ROOT, paths.folderMigration)
        : null,
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
  const gptResults = normalizeIntegratedGptResults(
    readJsonl(paths.gptResults),
    paths.gptOut,
  );
  writeJsonl(paths.results, results);
  if (fs.existsSync(paths.gptResults)) writeJsonl(paths.gptResults, gptResults);
  const pending = results.filter((row) => row.status === "pending");
  writeJsonl(paths.pending, pending);
  fs.writeFileSync(
    paths.gallery,
    productionGallery({
      stage,
      stageDir: paths.stageDir,
      records: readJsonl(paths.records),
      results,
      gptResults,
      omissions: manifest.image_jobs.omissions ?? [],
    }),
  );
  const completed = results.filter((row) => row.status === "completed");
  const failed = results.filter((row) => row.status === "failed");
  const gptCompleted = gptResults.filter((row) => row.status === "completed");
  const gptFailed = gptResults.filter((row) => row.status === "failed");
  const gptPending = gptResults.filter((row) => row.status === "pending");
  const curifyQueryIds = new Set(completed.map((row) => row.query_id));
  const gptQueryIds = new Set(gptCompleted.map((row) => row.vir_query_id));
  const queryUnion = new Set([...curifyQueryIds, ...gptQueryIds]);
  const queryIntersection = new Set(
    [...curifyQueryIds].filter((id) => gptQueryIds.has(id)),
  );
  const gptDirectionKeys = new Set(
    gptCompleted.map((row) => `${row.vir_query_id}|${row.vir_direction}`),
  );
  const matchedImagePairs = completed.filter((row) =>
    gptDirectionKeys.has(`${row.query_id}|${row.direction}`),
  ).length;
  const curifyLatencies = completed
    .map((row) => row.latency_ms)
    .filter((value) => Number.isFinite(value));
  const gptLatencies = gptCompleted
    .map((row) => row.latency_ms)
    .filter((value) => Number.isFinite(value));
  const originalPlanRunId = manifest.plan_source.original_run_id ??
    (manifest.plan_source.run_id === runId ? null : manifest.plan_source.run_id);
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
    plan_source: {
      ...manifest.plan_source,
      run_id: runId,
      path: path.relative(ROOT, paths.plans),
      original_run_id: originalPlanRunId,
      integrated: true,
    },
    gpt_direct: {
      image_model: "gpt-image-2",
      total: gptResults.length,
      completed: gptCompleted.length,
      failed: gptFailed.length,
      pending: gptPending.length,
      unique_queries: gptQueryIds.size,
      bytes: gptCompleted.reduce((sum, row) => sum + row.bytes, 0),
      results: path.relative(ROOT, paths.gptResults),
      output_dir: path.relative(ROOT, paths.gptOut),
      migrated_from_run: "2026-08-01-full",
    },
    combined: {
      completed_images: completed.length + gptCompleted.length,
      unique_queries: queryUnion.size,
      query_folders: queryUnion.size,
      queries_covered_by_both: queryIntersection.size,
      matched_image_pairs: matchedImagePairs,
    },
    comparison_reference: {
      integrated: true,
      directory: path.relative(ROOT, paths.stageDir),
      note: "End-to-end production comparison; image backends are intentionally not controlled.",
    },
    image_naming: {
      policy_version: "query-folder-v1",
      format: "by-query/<normalized-query>/<system>--d<direction>.<extension>",
      migration_manifest: fs.existsSync(paths.folderMigration)
        ? path.relative(ROOT, paths.folderMigration)
        : null,
    },
    system_metrics: {
      curify_gemini: {
        latency_mean_ms: curifyLatencies.length
          ? curifyLatencies.reduce((sum, value) => sum + value, 0) / curifyLatencies.length
          : null,
        error_rate: results.length ? failed.length / results.length : 0,
      },
      gpt_direct: {
        latency_mean_ms: gptLatencies.length
          ? gptLatencies.reduce((sum, value) => sum + value, 0) / gptLatencies.length
          : null,
        error_rate: gptResults.length ? gptFailed.length / gptResults.length : 0,
      },
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
  node scripts/vir-gemini-production.cjs rename-query-files --stage anchors
  node scripts/vir-gemini-production.cjs group-by-query --stage anchors
  node scripts/vir-gemini-production.cjs all --stage anchors [--limit 1]

Stages: anchors | exploration | core | challenge-gap

This track intentionally follows the production Curify pipeline:
Curify route/template prompt -> ${MODEL}. GPT-direct gpt-image-2 results live
beside Curify outputs in the same stage directory. Controlled Curify artifacts
are not part of this production comparison.`);
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  if (command === "prepare") await prepare(options);
  else if (command === "render") await render(options);
  else if (command === "finalize") finalize(options);
  else if (command === "rename-query-files") renameQueryFiles(options);
  else if (command === "group-by-query") groupByQuery(options);
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
  groupByQuery,
  parseArgs,
  pendingGeminiJobs,
  normalizeIntegratedGptResults,
  productionGallery,
  productionSlug,
  renameQueryFiles,
  renderGeminiJobs,
  validateImagePayload,
};
