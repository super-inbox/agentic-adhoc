#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import fsp from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EXPERIMENT_DIR = path.resolve(HERE, "..");
const EVAL_DIR = path.resolve(EXPERIMENT_DIR, "../..");
const BRIEF_DIR = path.join(EVAL_DIR, "brief_bank");
const EPISODES_PATH = path.join(BRIEF_DIR, "briefs.v0.3.jsonl");
const QUERIES_PATH = path.join(BRIEF_DIR, "initial_queries.v0.3.jsonl");
const ASSET_PACKS = [
  path.join(EVAL_DIR, "assets", "reference-pack-v0.2"),
  path.join(EVAL_DIR, "assets", "brief-bank-v0.3"),
];
const RUNS_DIR = path.join(EXPERIMENT_DIR, "runs");
const PRIVATE_DIR = path.join(EXPERIMENT_DIR, ".private");
const RUN_INDEX = path.join(EXPERIMENT_DIR, "run-index.jsonl");
const DEFAULT_TIMEOUT_MS = 45 * 60 * 1000;
const MODEL_PROVIDER = {
  id: "openai-http",
  name: "OpenAI HTTPS",
  base_url: process.env.CODEX_V03_BASE_URL || "https://chatgpt.com/backend-api/codex",
  requires_openai_auth: true,
  supports_websockets: false,
  wire_api: "responses",
};
const CANDIDATE = {
  agent_name: "codex-cli",
  model: process.env.CODEX_V03_MODEL || "gpt-5.6-sol",
  reasoning_effort: process.env.CODEX_V03_REASONING_EFFORT || "max",
  service_tier: process.env.CODEX_V03_SERVICE_TIER || "default",
  model_provider: MODEL_PROVIDER.id,
  transport: "responses-https",
  session_mode: "persisted-thread-resume",
};

function parseArgs(argv) {
  const args = {
    all: false,
    cases: [],
    conditions: [],
    mode: "full-episode",
    allowModelUsage: false,
    dryRun: false,
    skipCompleted: false,
    maxCases: Number.POSITIVE_INFINITY,
    timeoutMs: Number(process.env.CODEX_V03_TIMEOUT_MS || DEFAULT_TIMEOUT_MS),
    workers: Number(process.env.CODEX_V03_WORKERS || 1),
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--all") args.all = true;
    else if (value === "--case") args.cases.push(argv[++index]);
    else if (value === "--condition") args.conditions.push(argv[++index]);
    else if (value === "--initial-only") args.mode = "initial-only";
    else if (value === "--full-episode") args.mode = "full-episode";
    else if (value === "--allow-model-usage") args.allowModelUsage = true;
    else if (value === "--dry-run") args.dryRun = true;
    else if (value === "--skip-completed") args.skipCompleted = true;
    else if (value === "--max-cases") args.maxCases = Number(argv[++index]);
    else if (value === "--timeout-ms") args.timeoutMs = Number(argv[++index]);
    else if (value === "--workers") args.workers = Number(argv[++index]);
    else throw new Error(`Unknown argument: ${value}`);
  }
  const selectionModes = Number(args.all) + Number(args.cases.length > 0) + Number(args.conditions.length > 0);
  if (selectionModes !== 1) {
    throw new Error("Select exactly one of --all, one or more --case, or one or more --condition");
  }
  if (!args.allowModelUsage && !args.dryRun) {
    throw new Error(
      "Model execution is disabled. Pass --allow-model-usage after confirming the selected scope.",
    );
  }
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs <= 0) {
    throw new Error("--timeout-ms must be a positive number");
  }
  if (!(Number.isInteger(args.maxCases) && args.maxCases > 0) && args.maxCases !== Number.POSITIVE_INFINITY) {
    throw new Error("--max-cases must be a positive integer");
  }
  if (!(Number.isInteger(args.workers) && args.workers > 0 && args.workers <= 4)) {
    throw new Error("--workers must be an integer from 1 to 4");
  }
  return args;
}

function loadJsonl(filename) {
  return fs
    .readFileSync(filename, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function safeName(value) {
  return String(value)
    .normalize("NFKD")
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

function isoFileTimestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function cliVersion(codexBin) {
  const result = spawnSync(codexBin, ["--version"], { encoding: "utf8" });
  if (result.status !== 0) throw new Error(result.stderr || "Unable to read Codex CLI version");
  return result.stdout.trim();
}

function loadDataset() {
  const episodes = Object.fromEntries(loadJsonl(EPISODES_PATH).map((row) => [row.id, row]));
  const queries = loadJsonl(QUERIES_PATH);
  const assets = {};
  for (const assetRoot of ASSET_PACKS) {
    const manifest = path.join(assetRoot, "manifest.jsonl");
    for (const row of loadJsonl(manifest)) {
      if (assets[row.asset_id]) throw new Error(`Duplicate asset_id across packs: ${row.asset_id}`);
      assets[row.asset_id] = { ...row, asset_root: assetRoot };
    }
  }
  return { episodes, queries, assets };
}

function selectQueries(args, queries) {
  let selected;
  if (args.all) selected = queries;
  else if (args.cases.length) {
    const requested = new Set(args.cases);
    selected = queries.filter((row) => requested.has(row.base_brief_id));
    for (const id of requested) {
      if (!selected.some((row) => row.base_brief_id === id)) throw new Error(`Unknown base case: ${id}`);
    }
  } else {
    const requested = new Set(args.conditions);
    selected = queries.filter((row) => requested.has(row.id));
    for (const id of requested) {
      if (!selected.some((row) => row.id === id)) throw new Error(`Unknown condition: ${id}`);
    }
  }
  return [...selected].sort((left, right) => left.id.localeCompare(right.id)).slice(0, args.maxCases);
}

function conditionRoot(query) {
  return path.join(RUNS_DIR, safeName(query.base_brief_id), safeName(query.context_condition));
}

function latestCompleted(query, mode) {
  const root = conditionRoot(query);
  if (!fs.existsSync(root)) return null;
  const names = fs
    .readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort()
    .reverse();
  for (const name of names) {
    const resultPath = path.join(root, name, "result.json");
    if (!fs.existsSync(resultPath)) continue;
    const result = JSON.parse(fs.readFileSync(resultPath, "utf8"));
    if (
      result.outcome === "completed" &&
      result.run_mode === mode &&
      result.primary_eligible !== false
    ) {
      return resultPath;
    }
  }
  return null;
}

function resolveAsset(assetId, assets) {
  const asset = assets[assetId];
  if (!asset) throw new Error(`Unknown asset: ${assetId}`);
  const filename = path.resolve(asset.asset_root, asset.path);
  if (!filename.startsWith(`${path.resolve(asset.asset_root)}${path.sep}`)) {
    throw new Error(`Asset escapes reference root: ${assetId}`);
  }
  if (!fs.existsSync(filename)) throw new Error(`Asset is missing: ${filename}`);
  const data = fs.readFileSync(filename);
  if (sha256(data) !== asset.sha256) throw new Error(`Asset hash mismatch: ${assetId}`);
  const { asset_root: _assetRoot, ...publicAsset } = asset;
  return { ...publicAsset, filename, data };
}

async function copyInputs(query, assets, workDir) {
  const copied = [];
  for (const item of query.input_context) {
    if (!item.asset_id) continue;
    const asset = resolveAsset(item.asset_id, assets);
    const extension = path.extname(asset.filename) || ".png";
    const localName = `${String(copied.length + 1).padStart(2, "0")}-${safeName(item.role)}${extension}`;
    const destination = path.join(workDir, "inputs", localName);
    await fsp.writeFile(destination, asset.data);
    const projected = query.input_assets.find((entry) => entry.input_id === item.id);
    copied.push({
      input_id: item.id,
      asset_id: item.asset_id,
      role: item.role,
      reference_role: projected?.reference_role || "unspecified",
      identity_policy: projected?.identity_policy || "unspecified",
      filename: localName,
      path: destination,
      source_path: path.relative(path.resolve(EVAL_DIR, ".."), asset.filename),
      byte_size: asset.data.length,
      sha256: asset.sha256,
    });
  }
  return copied;
}

function visibleReferenceContracts(episode, query) {
  const allowed = new Set(query.input_context.map((item) => item.id));
  return episode.reference_contract.filter((item) => allowed.has(item.input_id));
}

function listBlock(title, values) {
  if (!values?.length) return `${title}: none`;
  return `${title}:\n${values.map((value) => `- ${value}`).join("\n")}`;
}

function initialPrompt(query, episode, copiedInputs) {
  const imageLegend = copiedInputs.length
    ? copiedInputs
        .map(
          (asset, index) =>
            `- Image ${index + 1} (${asset.filename}): input_id=${asset.input_id}; ` +
            `business_role=${asset.role}; reference_role=${asset.reference_role}; ` +
            `identity_policy=${asset.identity_policy}`,
        )
        .join("\n")
    : "- none";
  const textInputs = query.input_context
    .filter((item) => Object.hasOwn(item, "content"))
    .map((item) => `- ${item.id} (${item.kind}; ${item.role}): ${item.content}`);
  const referenceContracts = visibleReferenceContracts(episode, query).map(
    (item) =>
      `${item.input_id}: allowed influence = ${item.allowed_influence.join(", ")}; ` +
      `identity policy = ${item.identity_policy}`,
  );
  const preference = query.preference_memory
    ? [
        `Accepted: ${query.preference_memory.accepted_signals.join("; ")}`,
        `Rejected: ${query.preference_memory.rejected_signals.join("; ")}`,
      ]
    : [];
  const candidateArtifacts = query.required_structured_artifacts.filter(
    (name) => name !== "trajectory.jsonl",
  );
  const deliverables = episode.deliverables.map(
    (item) =>
      `${item.id}: count=${item.count}; formats=${item.formats.join("/")}; stage=${item.stage}; ` +
      `requirements=${item.requirements.join(" | ")}`,
  );
  return `You are the candidate Design Agent in a controlled v0.3 workflow evaluation.

Complete only the work justified by the current user turn. This may be a multi-turn task: do not invent future client feedback or silently choose on the client's behalf when the request asks for a decision. If an input or approval is missing, record the blocker and stop at the appropriate checkpoint instead of guessing.

Isolation and execution rules:
- Use only this prompt, attached images, files under the current working directory, and installed skill instructions required for your tools.
- Do not inspect benchmark, rubric, repository, or evaluator files outside this working directory.
- Use visual generation/editing tools when the task requires visual output; a prose-only substitute is not a completed visual deliverable.
- Save concrete candidate artifacts under ./outputs/v0 with stable descriptive filenames. Never overwrite an earlier state in later turns.
- Maintain ./outputs/project-state.json with current version, client decisions, locked items, changed items, and artifact paths.
- Produce ./outputs/v0/verification.json with checks performed, evidence paths, and unresolved blockers.
- Do not reveal private chain-of-thought. Brief observable plan/action notes are sufficient.

Context condition: ${query.context_condition}

Attached image bindings:
${imageLegend}

${listBlock("Non-image inputs", textInputs)}

${listBlock("Reference-use contract", referenceContracts)}

${listBlock("Hard constraints", episode.constraints.hard)}

${listBlock("Soft preferences", episode.constraints.soft)}

${listBlock("Must avoid", episode.constraints.negative)}

${listBlock("Expected deliverables", deliverables)}

${listBlock("Prior project preference memory", preference)}

${listBlock("Required candidate-side structured artifacts", candidateArtifacts)}
The evaluator captures the authoritative observable trajectory externally; do not manufacture a chain-of-thought log.

User request:
${query.query}`;
}

function feedbackPrompt(turn, previousLogicalSession) {
  const sessionBoundary = turn.session_id !== previousLogicalSession;
  return `${sessionBoundary ? "This is a later client session. Resume the same project from the conversation and saved project state.\n\n" : ""}Client feedback:
${turn.message}

Apply only the requested delta. Preserve previously approved or unrelated areas. Do not use hidden assumptions. Save the new state under ./outputs/${turn.expected_version}, keep all earlier version folders unchanged, update ./outputs/project-state.json, and write ./outputs/${turn.expected_version}/verification.json. Briefly list the new or changed output paths.`;
}

function sanitizeString(value, workDir) {
  if (typeof value !== "string") return value;
  return value
    .split(workDir)
    .join("<WORKDIR>")
    .replace(/\/Users\/[^/]+\/\.cache\/codex-runtimes/g, "<CODEX_RUNTIME_CACHE>")
    .replace(/\/Users\/[^/]+\/\.codex/g, "<CODEX_HOME>")
    .replace(/\/(?:private\/)?var\/folders\/[^\s"']+\/codex-v03-[A-Za-z0-9]+/g, "<WORKDIR>");
}

function sanitizeValue(value, workDir) {
  if (typeof value === "string") return sanitizeString(value, workDir);
  if (Array.isArray(value)) return value.map((item) => sanitizeValue(item, workDir));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, sanitizeValue(item, workDir)]),
    );
  }
  return value;
}

async function parseTrace(rawTracePath, workDir, turnIndex, logicalSessionId) {
  const normalized = [];
  const summary = {
    event_count: 0,
    command_count: 0,
    tool_count: 0,
    image_activity_count: 0,
    runtime_error_count: 0,
    runtime_error_messages: [],
    thread_id: null,
    usage: null,
  };
  let raw = "";
  try {
    raw = await fsp.readFile(rawTracePath, "utf8");
  } catch {
    return { normalized, summary };
  }
  for (const line of raw.split(/\r?\n/).filter(Boolean)) {
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      continue;
    }
    summary.event_count += 1;
    const common = { turn_index: turnIndex, logical_session_id: logicalSessionId };
    if (event.type === "error") {
      summary.runtime_error_count += 1;
      if (summary.runtime_error_messages.length < 10) {
        summary.runtime_error_messages.push(sanitizeString(event.message || "", workDir));
      }
      normalized.push({
        type: "codex.runtime_error",
        ...common,
        message: sanitizeString(event.message || "", workDir),
      });
      continue;
    }
    if (event.type === "thread.started") {
      summary.thread_id = event.thread_id || null;
      normalized.push({ type: "codex.thread_started", ...common, thread_id: summary.thread_id });
      continue;
    }
    if (event.type === "turn.started") {
      normalized.push({ type: "codex.turn_started", ...common });
      continue;
    }
    if (event.type === "turn.completed") {
      summary.usage = event.usage || null;
      normalized.push({ type: "codex.turn_completed", ...common, usage: event.usage || null });
      continue;
    }
    if (event.type === "turn.failed") {
      summary.runtime_error_count += 1;
      const failedMessage = event.error?.message || JSON.stringify(event.error || "");
      if (summary.runtime_error_messages.length < 10) {
        summary.runtime_error_messages.push(sanitizeString(failedMessage, workDir));
      }
      normalized.push({
        type: "codex.turn_failed",
        ...common,
        error: sanitizeValue(event.error || null, workDir),
      });
      continue;
    }
    const item = event.item || {};
    if (item.type === "reasoning") continue;
    if (item.type === "agent_message") {
      if (event.type === "item.completed") {
        normalized.push({
          type: "codex.agent_message",
          ...common,
          text: sanitizeString(item.text || "", workDir),
        });
      }
      continue;
    }
    if (item.type === "command_execution") {
      if (event.type === "item.completed") summary.command_count += 1;
      if (/image_gen|generated_images|imagegen/i.test(`${item.command || ""} ${item.aggregated_output || ""}`)) {
        if (event.type === "item.completed") summary.image_activity_count += 1;
      }
      normalized.push({
        type: "codex.command",
        ...common,
        phase: event.type,
        command: sanitizeString(item.command || "", workDir),
        status: item.status ?? null,
        exit_code: item.exit_code ?? null,
      });
      continue;
    }
    if (event.type === "item.completed" || event.type === "item.started") {
      if (event.type === "item.completed") summary.tool_count += 1;
      normalized.push({
        type: "codex.tool_item",
        ...common,
        phase: event.type,
        item_type: item.type || "unknown",
        item_id: item.id || null,
        status: item.status ?? null,
      });
    }
  }
  return { normalized, summary };
}

async function outputManifest(outputsDir) {
  const entries = [];
  if (!fs.existsSync(outputsDir)) return entries;
  async function walk(directory) {
    for (const entry of await fsp.readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) await walk(absolute);
      else if (entry.isFile()) {
        const data = await fsp.readFile(absolute);
        entries.push({
          filename: path.relative(outputsDir, absolute),
          byte_size: data.length,
          sha256: sha256(data),
        });
      }
    }
  }
  await walk(outputsDir);
  return entries.sort((left, right) => left.filename.localeCompare(right.filename));
}

async function checkpointOutputs(workDir, publicTrialDir, turnIndex, artifacts) {
  const outputsDir = path.join(workDir, "outputs");
  const checkpointDir = path.join(publicTrialDir, "partial-outputs");
  if (fs.existsSync(outputsDir)) {
    await fsp.cp(outputsDir, checkpointDir, { recursive: true, force: true });
  }
  await fsp.writeFile(
    path.join(publicTrialDir, "partial-result.json"),
    `${JSON.stringify(
      {
        schema_version: "codex-design-agent-v03-partial-v1",
        last_archived_turn: turnIndex,
        artifact_count: artifacts.length,
        artifacts,
        updated_at: new Date().toISOString(),
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
}

async function runProcess(command, argv, options) {
  return new Promise((resolve) => {
    const child = spawn(command, argv, options);
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
    }, options.timeoutMs);
    child.on("error", (error) => {
      clearTimeout(timer);
      resolve({ exitCode: null, signal: null, timedOut, error: `${error.name}: ${error.message}` });
    });
    child.on("exit", (exitCode, signal) => {
      clearTimeout(timer);
      resolve({ exitCode, signal, timedOut, error: null });
    });
  });
}

function initialCliArgs(workDir, copiedInputs, finalResponsePath) {
  const argv = [
    "exec",
    "--skip-git-repo-check",
    "-C",
    workDir,
    "-s",
    "workspace-write",
    "-m",
    CANDIDATE.model,
    ...providerCliArgs(),
    "-c",
    `model_reasoning_effort=\"${CANDIDATE.reasoning_effort}\"`,
    "-c",
    `service_tier=\"${CANDIDATE.service_tier}\"`,
    "--json",
    "-o",
    finalResponsePath,
  ];
  for (const input of copiedInputs) argv.push("-i", input.path);
  return argv;
}

function providerCliArgs() {
  return [
    "-c",
    `model_provider="${MODEL_PROVIDER.id}"`,
    "-c",
    `model_providers.${MODEL_PROVIDER.id}.name="${MODEL_PROVIDER.name}"`,
    "-c",
    `model_providers.${MODEL_PROVIDER.id}.base_url="${MODEL_PROVIDER.base_url}"`,
    "-c",
    `model_providers.${MODEL_PROVIDER.id}.requires_openai_auth=${MODEL_PROVIDER.requires_openai_auth}`,
    "-c",
    `model_providers.${MODEL_PROVIDER.id}.supports_websockets=${MODEL_PROVIDER.supports_websockets}`,
    "-c",
    `model_providers.${MODEL_PROVIDER.id}.wire_api="${MODEL_PROVIDER.wire_api}"`,
  ];
}

function resumeCliArgs(threadId, finalResponsePath) {
  return [
    "exec",
    "resume",
    "--skip-git-repo-check",
    "-m",
    CANDIDATE.model,
    ...providerCliArgs(),
    "-c",
    `model_reasoning_effort=\"${CANDIDATE.reasoning_effort}\"`,
    "-c",
    `service_tier=\"${CANDIDATE.service_tier}\"`,
    "--json",
    "-o",
    finalResponsePath,
    threadId,
  ];
}

async function runTurn({
  codexBin,
  workDir,
  privateTrialDir,
  publicTrialDir,
  copiedInputs,
  prompt,
  threadId,
  turnIndex,
  logicalSessionId,
  timeoutMs,
}) {
  const turnName = `turn-${String(turnIndex).padStart(2, "0")}`;
  const rawTracePath = path.join(privateTrialDir, `${turnName}.raw.jsonl`);
  const rawStderrPath = path.join(privateTrialDir, `${turnName}.stderr.log`);
  const finalResponsePath = path.join(workDir, `${turnName}.final-response.txt`);
  const traceFd = fs.openSync(rawTracePath, "w");
  const stderrFd = fs.openSync(rawStderrPath, "w");
  const argv = threadId
    ? resumeCliArgs(threadId, finalResponsePath)
    : initialCliArgs(workDir, copiedInputs, finalResponsePath);
  argv.push("--", prompt);

  const startedAt = new Date();
  const startedMs = Date.now();
  const processResult = await runProcess(codexBin, argv, {
    cwd: workDir,
    stdio: ["ignore", traceFd, stderrFd],
    timeoutMs,
  });
  fs.closeSync(traceFd);
  fs.closeSync(stderrFd);
  const finishedAt = new Date();
  const { normalized, summary } = await parseTrace(
    rawTracePath,
    workDir,
    turnIndex,
    logicalSessionId,
  );
  const publicTurnDir = path.join(publicTrialDir, "turns", turnName);
  await fsp.mkdir(publicTurnDir, { recursive: true });
  if (fs.existsSync(finalResponsePath)) {
    const response = sanitizeString(await fsp.readFile(finalResponsePath, "utf8"), workDir);
    await fsp.writeFile(path.join(publicTurnDir, "final-response.txt"), response, "utf8");
  }
  const stderr = sanitizeString(await fsp.readFile(rawStderrPath, "utf8"), workDir);
  await fsp.writeFile(path.join(publicTurnDir, "stderr.log"), stderr, "utf8");
  await fsp.writeFile(
    path.join(publicTurnDir, "trajectory.jsonl"),
    normalized.length ? `${normalized.map((event) => JSON.stringify(event)).join("\n")}\n` : "",
    "utf8",
  );
  const artifacts = await outputManifest(path.join(workDir, "outputs"));
  await checkpointOutputs(workDir, publicTrialDir, turnIndex, artifacts);
  const result = {
    turn_index: turnIndex,
    logical_session_id: logicalSessionId,
    started_at: startedAt.toISOString(),
    finished_at: finishedAt.toISOString(),
    latency_ms: Date.now() - startedMs,
    exit_code: processResult.exitCode,
    signal: processResult.signal,
    timed_out: processResult.timedOut,
    error: processResult.error,
    trace_summary: summary,
    artifact_manifest_after_turn: artifacts,
  };
  await fsp.writeFile(
    path.join(publicTurnDir, "turn-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  return { result, normalized, threadId: threadId || summary.thread_id };
}

function aggregateUsage(turns) {
  const totals = {
    input_tokens: 0,
    cached_input_tokens: 0,
    cache_write_input_tokens: 0,
    output_tokens: 0,
    reasoning_output_tokens: 0,
  };
  let observed = false;
  for (const turn of turns) {
    const usage = turn.trace_summary.usage;
    if (!usage) continue;
    observed = true;
    for (const key of Object.keys(totals)) totals[key] += Number(usage[key] || 0);
  }
  return observed ? totals : null;
}

function classifyFailure(outcome, turnResults, artifacts) {
  if (outcome === "completed") return null;
  if (outcome === "timeout") return "candidate_timeout";
  const messages = turnResults.flatMap(
    (turn) => turn.trace_summary?.runtime_error_messages || [],
  );
  const noCandidateActivity =
    artifacts.length === 0 &&
    turnResults.every(
      (turn) =>
        Number(turn.trace_summary?.command_count || 0) === 0 &&
        Number(turn.trace_summary?.tool_count || 0) === 0 &&
        !turn.trace_summary?.usage,
    );
  if (
    noCandidateActivity &&
    messages.some((message) =>
      /error sending request|failed to connect|stream disconnected before completion/i.test(message),
    )
  ) {
    return "infrastructure_network";
  }
  if (
    noCandidateActivity &&
    messages.some((message) => /usage limit|rate limit|quota|insufficient credit/i.test(message))
  ) {
    return "infrastructure_quota";
  }
  if (
    noCandidateActivity &&
    messages.some((message) => /unauthorized|authentication|invalid.*token|login required/i.test(message))
  ) {
    return "infrastructure_auth";
  }
  return "candidate_error";
}

async function assertNetworkReachable() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  try {
    await fetch(new URL(MODEL_PROVIDER.base_url).origin, {
      method: "HEAD",
      redirect: "manual",
      signal: controller.signal,
    });
  } catch (error) {
    throw new Error(
      `Infrastructure preflight failed for ${new URL(MODEL_PROVIDER.base_url).origin}: ` +
        `${error.name}: ${error.message}`,
    );
  } finally {
    clearTimeout(timer);
  }
}

async function runCondition(query, episode, args, assets, codexBin, version) {
  const timestamp = isoFileTimestamp();
  const publicTrialDir = path.join(conditionRoot(query), timestamp);
  const privateTrialDir = path.join(
    PRIVATE_DIR,
    safeName(query.base_brief_id),
    safeName(query.context_condition),
    timestamp,
  );
  const workDir = await fsp.mkdtemp(path.join(os.tmpdir(), "codex-v03-"));
  await fsp.mkdir(path.join(workDir, "inputs"), { recursive: true });
  await fsp.mkdir(path.join(workDir, "outputs"), { recursive: true });
  await fsp.mkdir(publicTrialDir, { recursive: true });
  await fsp.mkdir(privateTrialDir, { recursive: true });

  const copiedInputs = await copyInputs(query, assets, workDir);
  const inputManifest = copiedInputs.map(({ path: _path, ...item }) => item);
  await fsp.writeFile(
    path.join(publicTrialDir, "input-manifest.json"),
    `${JSON.stringify(inputManifest, null, 2)}\n`,
    "utf8",
  );

  const intendedFeedback = args.mode === "full-episode" ? episode.feedback : [];
  const prompts = [initialPrompt(query, episode, copiedInputs)];
  let priorSession = "session-01";
  for (const feedback of intendedFeedback) {
    prompts.push(feedbackPrompt(feedback, priorSession));
    priorSession = feedback.session_id;
  }
  const logicalSessions = ["session-01", ...intendedFeedback.map((item) => item.session_id)];
  const allNormalized = [];
  const turnResults = [];
  let threadId = null;
  const startedAt = new Date();
  const startedMs = Date.now();
  for (let index = 0; index < prompts.length; index += 1) {
    const turn = await runTurn({
      codexBin,
      workDir,
      privateTrialDir,
      publicTrialDir,
      copiedInputs,
      prompt: prompts[index],
      threadId,
      turnIndex: index,
      logicalSessionId: logicalSessions[index],
      timeoutMs: args.timeoutMs,
    });
    threadId = turn.threadId;
    allNormalized.push(...turn.normalized);
    turnResults.push(turn.result);
    process.stdout.write(
      `  ${query.id} turn ${index + 1}/${prompts.length}: exit=${turn.result.exit_code}; ` +
        `events=${turn.result.trace_summary.event_count}; artifacts=${turn.result.artifact_manifest_after_turn.length}\n`,
    );
    if (turn.result.exit_code !== 0 || !threadId) break;
  }

  const outputsDir = path.join(workDir, "outputs");
  const artifacts = await outputManifest(outputsDir);
  await fsp.cp(outputsDir, path.join(publicTrialDir, "outputs"), { recursive: true });
  await fsp.writeFile(
    path.join(publicTrialDir, "trajectory.jsonl"),
    allNormalized.length ? `${allNormalized.map((event) => JSON.stringify(event)).join("\n")}\n` : "",
    "utf8",
  );
  const artifactNames = new Set(artifacts.map((item) => path.basename(item.filename)));
  const requiredCandidateArtifacts = query.required_structured_artifacts.filter(
    (name) => name !== "trajectory.jsonl",
  );
  const artifactContract = Object.fromEntries(
    requiredCandidateArtifacts.map((name) => [name, artifactNames.has(name)]),
  );
  artifactContract["trajectory.jsonl"] = allNormalized.length > 0;
  const allTurnsCompleted =
    turnResults.length === prompts.length && turnResults.every((turn) => turn.exit_code === 0);
  const outcome =
    allTurnsCompleted && artifacts.length > 0
      ? "completed"
      : turnResults.some((turn) => turn.timed_out)
        ? "timeout"
        : turnResults.some((turn) => turn.exit_code !== 0)
          ? "error"
          : "incomplete";
  const result = {
    schema_version: "codex-design-agent-v03-run-v1",
    candidate: CANDIDATE,
    cli_version: version,
    run_mode: args.mode,
    query_id: query.id,
    base_brief_id: query.base_brief_id,
    context_condition: query.context_condition,
    category: query.category,
    capability_level: query.capability_level,
    capability_tags: query.capability_tags,
    future_feedback_visible_at_turn_0: false,
    primary_eligible: true,
    turn_timeout_ms: args.timeoutMs,
    started_at: startedAt.toISOString(),
    finished_at: new Date().toISOString(),
    latency_ms: Date.now() - startedMs,
    intended_turns: prompts.length,
    completed_turns: turnResults.filter((turn) => turn.exit_code === 0).length,
    logical_sessions: [...new Set(logicalSessions)],
    codex_thread_id: threadId,
    input_assets: inputManifest,
    input_context_ids: query.input_context.map((item) => item.id),
    required_candidate_artifacts: query.required_structured_artifacts,
    artifact_contract: artifactContract,
    artifacts,
    turn_results: turnResults,
    usage: aggregateUsage(turnResults),
    failure_class: classifyFailure(outcome, turnResults, artifacts),
    outcome,
  };
  await fsp.writeFile(
    path.join(publicTrialDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  await fsp.appendFile(RUN_INDEX, `${JSON.stringify({ ...result, run_path: path.relative(EXPERIMENT_DIR, publicTrialDir) })}\n`);
  if (outcome === "completed") {
    await fsp.rm(path.join(publicTrialDir, "partial-outputs"), { recursive: true, force: true });
    await fsp.rm(path.join(publicTrialDir, "partial-result.json"), { force: true });
    await fsp.rm(workDir, { recursive: true, force: true });
  } else {
    await fsp.writeFile(
      path.join(privateTrialDir, "recovery.json"),
      `${JSON.stringify(
        {
          workdir: workDir,
          codex_thread_id: threadId,
          completed_turns: turnResults.filter((turn) => turn.exit_code === 0).length,
          intended_turns: prompts.length,
          outcome,
        },
        null,
        2,
      )}\n`,
      "utf8",
    );
  }
  return { result, publicTrialDir };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { episodes, queries, assets } = loadDataset();
  const selected = selectQueries(args, queries);
  const codexBin = process.env.CODEX_BIN || "codex";
  const version = cliVersion(codexBin);
  if (args.dryRun) {
    const plan = selected.map((query) => {
      const episode = episodes[query.base_brief_id];
      if (!episode) throw new Error(`Missing episode: ${query.base_brief_id}`);
      for (const item of query.input_assets) resolveAsset(item.asset_id, assets);
      return {
        query_id: query.id,
        base_brief_id: query.base_brief_id,
        context_condition: query.context_condition,
        input_assets: query.input_assets.length,
        intended_turns: args.mode === "full-episode" ? 1 + episode.feedback.length : 1,
      };
    });
    process.stdout.write(
      `${JSON.stringify(
        {
          candidate: { ...CANDIDATE, cli_version: version },
          run_mode: args.mode,
          conditions: plan.length,
          intended_turns: plan.reduce((total, row) => total + row.intended_turns, 0),
          plan,
        },
        null,
        2,
      )}\n`,
    );
    return;
  }
  await fsp.mkdir(RUNS_DIR, { recursive: true });
  await fsp.mkdir(PRIVATE_DIR, { recursive: true });

  let runnable = selected;
  if (args.skipCompleted) {
    runnable = selected.filter((query) => {
      const completed = latestCompleted(query, args.mode);
      if (completed) process.stdout.write(`Skip completed ${query.id}: ${completed}\n`);
      return !completed;
    });
  }
  process.stdout.write(
    `Codex v0.3: ${runnable.length}/${selected.length} condition(s); mode=${args.mode}; ` +
      `workers=${args.workers}; model=${CANDIDATE.model}; effort=${CANDIDATE.reasoning_effort}; cli=${version}\n`,
  );
  let nextIndex = 0;
  let infrastructureFailure = false;
  async function worker(workerId) {
    while (!infrastructureFailure) {
      const index = nextIndex;
      nextIndex += 1;
      if (index >= runnable.length) return;
      const query = runnable[index];
      const episode = episodes[query.base_brief_id];
      if (!episode) throw new Error(`Missing episode: ${query.base_brief_id}`);
      await assertNetworkReachable();
      process.stdout.write(`Worker ${workerId} run ${index + 1}/${runnable.length}: ${query.id}\n`);
      const { result, publicTrialDir } = await runCondition(
        query,
        episode,
        args,
        assets,
        codexBin,
        version,
      );
      process.stdout.write(
        `${query.id}: ${result.outcome}; turns=${result.completed_turns}/${result.intended_turns}; ` +
          `artifacts=${result.artifacts.length}; ${path.relative(EXPERIMENT_DIR, publicTrialDir)}\n`,
      );
      if (result.failure_class?.startsWith("infrastructure_")) {
        infrastructureFailure = true;
        process.stderr.write(
          `Stop batch after ${query.id}: ${result.failure_class}. ` +
            "Rerun with --skip-completed after infrastructure recovers.\n",
        );
      }
    }
  }
  const workerCount = Math.min(args.workers, runnable.length || 1);
  await Promise.all(Array.from({ length: workerCount }, (_, index) => worker(index + 1)));
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
