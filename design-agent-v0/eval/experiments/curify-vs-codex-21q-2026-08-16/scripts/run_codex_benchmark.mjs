#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import fsp from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EVAL_DIR = path.resolve(HERE, "../../..");
const LEGACY_DATASET_PATH = path.join(
  EVAL_DIR,
  "braintrust_eval/results/design-agent-bench-v0.1-multimodal-pilot.dataset.jsonl",
);
const DATASET_PATH = fs.existsSync(LEGACY_DATASET_PATH)
  ? LEGACY_DATASET_PATH
  : path.resolve(HERE, "../dataset.jsonl");
const RUNS_DIR = path.join(HERE, "runs");
const DEFAULT_TIMEOUT_MS = 15 * 60 * 1000;
const CANDIDATE = {
  agent_name: "codex-cli",
  model: "gpt-5.6-sol",
  reasoning_effort: "max",
  service_tier: "default",
  session_mode: "ephemeral",
};

function parseArgs(argv) {
  const args = {
    ids: [],
    allBenchmark: false,
    allowModelUsage: false,
    timeoutMs: Number(process.env.CODEX_BENCH_TIMEOUT_MS || DEFAULT_TIMEOUT_MS),
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--case") args.ids.push(argv[++index]);
    else if (value === "--all-benchmark") args.allBenchmark = true;
    else if (value === "--allow-model-usage") args.allowModelUsage = true;
    else if (value === "--timeout-ms") args.timeoutMs = Number(argv[++index]);
    else throw new Error(`Unknown argument: ${value}`);
  }
  if (args.allBenchmark && args.ids.length) {
    throw new Error("Use either --all-benchmark or one or more --case values, not both");
  }
  if (!args.allBenchmark && args.ids.length === 0) {
    throw new Error("Select --all-benchmark or at least one --case");
  }
  if (!args.allowModelUsage) {
    throw new Error(
      "Model execution is disabled. Pass --allow-model-usage after confirming the batch scope.",
    );
  }
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs <= 0) {
    throw new Error("--timeout-ms must be a positive number");
  }
  return args;
}

function portableAssetPath(assetPath) {
  if (fs.existsSync(assetPath)) return assetPath;
  const marker = `${path.sep}eval${path.sep}assets${path.sep}`;
  const markerIndex = assetPath.lastIndexOf(marker);
  if (markerIndex < 0) return assetPath;
  return path.join(EVAL_DIR, "assets", assetPath.slice(markerIndex + marker.length));
}

function loadCases() {
  const rows = fs
    .readFileSync(DATASET_PATH, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
  return Object.fromEntries(
    rows.map((row) => {
      const assets = row.input.assets.map((asset) => ({
        ...asset,
        path: portableAssetPath(asset.path),
      }));
      return [row.input.task_id, { ...row, input: { ...row.input, assets } }];
    }),
  );
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
  return (result.stdout || result.stderr || "unknown").trim();
}

async function copyInputs(testCase, workDir) {
  const copied = [];
  for (let index = 0; index < testCase.input.assets.length; index += 1) {
    const asset = testCase.input.assets[index];
    const source = asset.path;
    const extension = path.extname(source) || ".png";
    const filename = `${String(index + 1).padStart(2, "0")}-${safeName(asset.role)}${extension}`;
    const destination = path.join(workDir, "inputs", filename);
    const data = await fsp.readFile(source);
    await fsp.writeFile(destination, data);
    copied.push({
      asset_id: asset.asset_id,
      role: asset.role,
      source_path: source,
      filename,
      sha256: sha256(data),
      byte_size: data.length,
      path: destination,
    });
  }
  return copied;
}

function promptFor(testCase, copiedInputs) {
  const imageLegend = copiedInputs
    .map((asset, index) => `Image ${index + 1}: ${asset.role}`)
    .join("\n");
  return `You are the candidate design agent in a single-turn evaluation.
Complete the user's request using all attached images.
Do not inspect or read project files outside the current working directory, except installed skill instructions required to use your tools.
Do not ask a follow-up question; make reasonable assumptions and complete the task in this turn.
Use the available visual generation or editing capability when the request requires it.
Save every final deliverable you produce under ./outputs using stable descriptive filenames.
In the final response, briefly list the saved output filenames.

Attached-image roles:
${imageLegend}

User request: ${testCase.input.brief}`;
}

async function summarizeTrace(tracePath) {
  const summary = {
    event_count: 0,
    command_count: 0,
    image_tool_count: 0,
    usage: null,
    thread_id: null,
  };
  let text;
  try {
    text = await fsp.readFile(tracePath, "utf8");
  } catch {
    return summary;
  }
  for (const line of text.split(/\r?\n/).filter(Boolean)) {
    try {
      const event = JSON.parse(line);
      summary.event_count += 1;
      if (event.type === "thread.started") summary.thread_id = event.thread_id || null;
      if (event.type === "turn.completed") summary.usage = event.usage || null;
      const item = event.item || {};
      if (item.type === "command_execution" && event.type === "item.completed") {
        summary.command_count += 1;
      }
      if (/image_gen|imagegen/i.test(JSON.stringify(item)) && event.type === "item.completed") {
        summary.image_tool_count += 1;
      }
    } catch {
      // Keep the raw trace even if one line is malformed.
    }
  }
  return summary;
}

async function outputManifest(outputsDir) {
  const entries = [];
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

async function runProcess(command, args, options) {
  return new Promise((resolve) => {
    const child = spawn(command, args, options);
    const timer = setTimeout(() => child.kill("SIGTERM"), options.timeoutMs);
    child.on("error", (error) => {
      clearTimeout(timer);
      resolve({ exitCode: null, signal: null, error: `${error.name}: ${error.message}` });
    });
    child.on("exit", (exitCode, signal) => {
      clearTimeout(timer);
      resolve({ exitCode, signal, error: null });
    });
  });
}

async function runCase(testCase, args, codexBin, version) {
  const taskId = testCase.input.task_id;
  const trialDir = path.join(RUNS_DIR, taskId, isoFileTimestamp());
  const workDir = await fsp.mkdtemp(path.join(os.tmpdir(), "codex-design-benchmark-"));
  await fsp.mkdir(path.join(workDir, "inputs"), { recursive: true });
  await fsp.mkdir(path.join(workDir, "outputs"), { recursive: true });
  await fsp.mkdir(trialDir, { recursive: true });

  const copiedInputs = await copyInputs(testCase, workDir);
  const prompt = promptFor(testCase, copiedInputs);
  const tracePath = path.join(workDir, "trace.jsonl");
  const stderrPath = path.join(workDir, "stderr.log");
  const finalResponsePath = path.join(workDir, "final-response.txt");
  const traceFd = fs.openSync(tracePath, "w");
  const stderrFd = fs.openSync(stderrPath, "w");
  const cliArgs = [
    "exec",
    "--ephemeral",
    "--skip-git-repo-check",
    "-C",
    workDir,
    "-s",
    "workspace-write",
    "-m",
    CANDIDATE.model,
    "-c",
    `model_reasoning_effort=\"${CANDIDATE.reasoning_effort}\"`,
    "-c",
    `service_tier=\"${CANDIDATE.service_tier}\"`,
    "--json",
    "-o",
    finalResponsePath,
  ];
  for (const input of copiedInputs) cliArgs.push("-i", input.path);
  cliArgs.push("--", prompt);

  const startedAt = new Date();
  const startedMs = Date.now();
  const processResult = await runProcess(codexBin, cliArgs, {
    cwd: workDir,
    stdio: ["ignore", traceFd, stderrFd],
    timeoutMs: args.timeoutMs,
  });
  fs.closeSync(traceFd);
  fs.closeSync(stderrFd);
  const finishedAt = new Date();
  const artifacts = await outputManifest(path.join(workDir, "outputs"));
  const traceSummary = await summarizeTrace(tracePath);
  const result = {
    schema_version: "design-agent-candidate-run-v1",
    candidate: CANDIDATE,
    cli_version: version,
    task_id: taskId,
    brief: testCase.input.brief,
    category: testCase.metadata.category,
    capability_id: testCase.metadata.capability_id,
    started_at: startedAt.toISOString(),
    finished_at: finishedAt.toISOString(),
    latency_ms: Date.now() - startedMs,
    timeout_ms: args.timeoutMs,
    exit_code: processResult.exitCode,
    signal: processResult.signal,
    error: processResult.error,
    input_capacity: copiedInputs.length,
    uploaded_assets: copiedInputs.map((asset) => asset.filename),
    uploaded_asset_roles: copiedInputs.map((asset) => asset.role),
    omitted_assets: [],
    exact_input_preserved: true,
    artifacts,
    trace_summary: traceSummary,
    outcome:
      processResult.exitCode === 0 && artifacts.length > 0
        ? "completed"
        : processResult.exitCode === 0
          ? "completed_no_saved_artifact"
          : processResult.signal
            ? "timeout_or_signal"
            : "error",
  };
  await fsp.writeFile(
    path.join(workDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  await fsp.cp(workDir, trialDir, { recursive: true });
  await fsp.rm(workDir, { recursive: true, force: true });
  await fsp.appendFile(path.join(HERE, "run-index.jsonl"), `${JSON.stringify(result)}\n`);
  return { trialDir, result };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cases = loadCases();
  const ids = args.allBenchmark ? Object.keys(cases).sort() : args.ids;
  for (const id of ids) {
    if (!cases[id]) throw new Error(`Unknown benchmark case: ${id}`);
    for (const asset of cases[id].input.assets) {
      if (!fs.existsSync(asset.path)) throw new Error(`${id}: asset not found: ${asset.path}`);
    }
  }
  const codexBin = process.env.CODEX_BIN || "codex";
  const version = cliVersion(codexBin);
  for (let index = 0; index < ids.length; index += 1) {
    const id = ids[index];
    process.stdout.write(`Codex ${index + 1}/${ids.length}: ${id}\n`);
    const { trialDir, result } = await runCase(cases[id], args, codexBin, version);
    process.stdout.write(
      `${id}: ${result.outcome}; ${result.artifacts.length} artifact(s); ` +
        `${result.latency_ms} ms; ${trialDir}\n`,
    );
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
