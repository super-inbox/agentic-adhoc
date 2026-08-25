#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EXPERIMENT_DIR = path.resolve(HERE, "..");
const EVAL_DIR = path.resolve(EXPERIMENT_DIR, "../..");
const BRIEF_DIR = path.join(EVAL_DIR, "brief_bank");
const EPISODES_PATH = path.join(BRIEF_DIR, "briefs.v0.2.jsonl");
const QUERIES_PATH = path.join(BRIEF_DIR, "initial_queries.v0.2.jsonl");
const RUN_INDEX = path.join(EXPERIMENT_DIR, "run-index.jsonl");
const CANDIDATE = {
  agent_name: "codex-cli",
  model: process.env.CODEX_V02_MODEL || "gpt-5.6-sol",
  reasoning_effort: process.env.CODEX_V02_REASONING_EFFORT || "max",
  service_tier: process.env.CODEX_V02_SERVICE_TIER || "default",
  session_mode: "persisted-thread-resume",
};

function parseArgs(argv) {
  const args = { condition: null, publicRun: null, privateRun: null, workdir: null, fromTurn: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--condition") args.condition = argv[++index];
    else if (value === "--public-run") args.publicRun = argv[++index];
    else if (value === "--private-run") args.privateRun = argv[++index];
    else if (value === "--workdir") args.workdir = argv[++index];
    else if (value === "--from-turn") args.fromTurn = Number(argv[++index]);
    else throw new Error(`Unknown argument: ${value}`);
  }
  for (const key of ["condition", "publicRun", "privateRun", "workdir"]) {
    if (!args[key]) throw new Error(`Missing --${key.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)}`);
  }
  if (!Number.isInteger(args.fromTurn) || args.fromTurn < 0) {
    throw new Error("--from-turn must be a non-negative integer");
  }
  args.publicRun = path.resolve(args.publicRun);
  args.privateRun = path.resolve(args.privateRun);
  args.workdir = path.resolve(args.workdir);
  return args;
}

function loadJsonl(filename) {
  return fs
    .readFileSync(filename, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function sanitizeString(value, workdir) {
  if (typeof value !== "string") return value;
  return value
    .split(workdir)
    .join("<WORKDIR>")
    .replace(/\/Users\/[^/]+\/\.cache\/codex-runtimes/g, "<CODEX_RUNTIME_CACHE>")
    .replace(/\/Users\/[^/]+\/\.codex/g, "<CODEX_HOME>")
    .replace(/\/(?:private\/)?var\/folders\/[^\s"']+\/codex-v02-[A-Za-z0-9]+/g, "<WORKDIR>");
}

function sanitizeValue(value, workdir) {
  if (typeof value === "string") return sanitizeString(value, workdir);
  if (Array.isArray(value)) return value.map((item) => sanitizeValue(item, workdir));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, sanitizeValue(item, workdir)]),
    );
  }
  return value;
}

async function parseRawTrace(filename, workdir, turnIndex, logicalSessionId, attempt) {
  const normalized = [];
  const summary = {
    event_count: 0,
    command_count: 0,
    tool_count: 0,
    image_activity_count: 0,
    runtime_error_count: 0,
    thread_id: null,
    usage: null,
    completed: false,
  };
  const raw = await fsp.readFile(filename, "utf8");
  for (const line of raw.split(/\r?\n/).filter(Boolean)) {
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      continue;
    }
    summary.event_count += 1;
    const common = {
      turn_index: turnIndex,
      logical_session_id: logicalSessionId,
      operational_attempt: attempt,
    };
    if (event.type === "error") {
      summary.runtime_error_count += 1;
      normalized.push({
        type: "codex.runtime_error",
        ...common,
        message: sanitizeString(event.message || "", workdir),
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
      summary.completed = true;
      summary.usage = event.usage || null;
      normalized.push({ type: "codex.turn_completed", ...common, usage: event.usage || null });
      continue;
    }
    if (event.type === "turn.failed") {
      summary.runtime_error_count += 1;
      normalized.push({
        type: "codex.turn_failed",
        ...common,
        error: sanitizeValue(event.error || null, workdir),
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
          text: sanitizeString(item.text || "", workdir),
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
        command: sanitizeString(item.command || "", workdir),
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

function manifestThroughTurn(entries, turnIndex) {
  return entries.filter((entry) => {
    const match = entry.filename.match(/^v(\d+)\//);
    return !match || Number(match[1]) <= turnIndex;
  });
}

function combineTraceSummaries(attempts) {
  const lastCompleted = [...attempts].reverse().find((item) => item.summary.completed);
  return {
    event_count: attempts.reduce((total, item) => total + item.summary.event_count, 0),
    command_count: attempts.reduce((total, item) => total + item.summary.command_count, 0),
    tool_count: attempts.reduce((total, item) => total + item.summary.tool_count, 0),
    image_activity_count: attempts.reduce(
      (total, item) => total + item.summary.image_activity_count,
      0,
    ),
    runtime_error_count: attempts.reduce(
      (total, item) => total + item.summary.runtime_error_count,
      0,
    ),
    thread_id: lastCompleted?.summary.thread_id || attempts.at(-1)?.summary.thread_id || null,
    usage: lastCompleted?.summary.usage || null,
  };
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
    const usage = turn.trace_summary?.usage;
    if (!usage) continue;
    observed = true;
    for (const key of Object.keys(totals)) totals[key] += Number(usage[key] || 0);
  }
  return observed ? totals : null;
}

function attemptSort(left, right) {
  const retry = (value) => Number(value.match(/-retry-(\d+)\.raw\.jsonl$/)?.[1] || 0);
  return retry(left) - retry(right);
}

async function recoveredTurn({ args, turnIndex, logicalSessionId, allArtifacts }) {
  const prefix = `turn-${String(turnIndex).padStart(2, "0")}`;
  const rawNames = (await fsp.readdir(args.privateRun))
    .filter((name) => new RegExp(`^${prefix}(?:-retry-\\d+)?\\.raw\\.jsonl$`).test(name))
    .sort(attemptSort);
  if (!rawNames.length) throw new Error(`No private trace found for ${prefix}`);

  const attempts = [];
  const normalized = [];
  for (let index = 0; index < rawNames.length; index += 1) {
    const rawName = rawNames[index];
    const absolute = path.join(args.privateRun, rawName);
    const parsed = await parseRawTrace(
      absolute,
      args.workdir,
      turnIndex,
      logicalSessionId,
      index + 1,
    );
    const stat = await fsp.stat(absolute);
    const stem = rawName.replace(/\.raw\.jsonl$/, "");
    const attempt = {
      attempt: index + 1,
      raw_trace_file: rawName,
      completed: parsed.summary.completed,
      started_at: stat.birthtime.toISOString(),
      finished_at: stat.mtime.toISOString(),
      latency_ms: Math.max(0, stat.mtimeMs - stat.birthtimeMs),
      trace_summary: parsed.summary,
      final_response_file: `${stem}.final-response.txt`,
      stderr_file: `${stem}.stderr.log`,
    };
    attempts.push({ ...attempt, summary: parsed.summary, stem });
    normalized.push(...parsed.normalized);
  }
  const completed = [...attempts].reverse().find((item) => item.completed);
  if (!completed) throw new Error(`${prefix} has no completed operational attempt`);

  const publicTurnDir = path.join(args.publicRun, "turns", prefix);
  await fsp.mkdir(publicTurnDir, { recursive: true });
  const finalResponsePath = path.join(args.workdir, completed.final_response_file);
  if (!fs.existsSync(finalResponsePath)) throw new Error(`Missing final response: ${finalResponsePath}`);
  await fsp.writeFile(
    path.join(publicTurnDir, "final-response.txt"),
    sanitizeString(await fsp.readFile(finalResponsePath, "utf8"), args.workdir),
    "utf8",
  );
  const stderrBlocks = [];
  for (const attempt of attempts) {
    const stderrPath = path.join(args.privateRun, attempt.stderr_file);
    const text = fs.existsSync(stderrPath) ? await fsp.readFile(stderrPath, "utf8") : "";
    stderrBlocks.push(
      `operational_attempt=${attempt.attempt}; completed=${attempt.completed}\n${sanitizeString(text, args.workdir)}`,
    );
  }
  await fsp.writeFile(path.join(publicTurnDir, "stderr.log"), `${stderrBlocks.join("\n\n")}\n`, "utf8");
  await fsp.writeFile(
    path.join(publicTurnDir, "trajectory.jsonl"),
    normalized.length ? `${normalized.map((event) => JSON.stringify(event)).join("\n")}\n` : "",
    "utf8",
  );
  const combinedSummary = combineTraceSummaries(attempts);
  const result = {
    turn_index: turnIndex,
    logical_session_id: logicalSessionId,
    started_at: attempts[0].started_at,
    finished_at: completed.finished_at,
    latency_ms: attempts.reduce((total, item) => total + item.latency_ms, 0),
    exit_code: 0,
    signal: null,
    timed_out: false,
    error: null,
    trace_summary: combinedSummary,
    artifact_manifest_after_turn: manifestThroughTurn(allArtifacts, turnIndex),
    artifact_manifest_source: "reconstructed_after_operational_recovery",
    operational_attempts: attempts.map(({ summary: _summary, stem: _stem, ...item }) => item),
  };
  await fsp.writeFile(
    path.join(publicTurnDir, "turn-result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  return { result, normalized, threadId: combinedSummary.thread_id };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const queries = loadJsonl(QUERIES_PATH);
  const episodes = Object.fromEntries(loadJsonl(EPISODES_PATH).map((row) => [row.id, row]));
  const query = queries.find((row) => row.id === args.condition);
  if (!query) throw new Error(`Unknown condition: ${args.condition}`);
  const episode = episodes[query.base_brief_id];
  if (!episode) throw new Error(`Missing episode: ${query.base_brief_id}`);
  const intendedTurns = 1 + episode.feedback.length;
  if (args.fromTurn >= intendedTurns) throw new Error("--from-turn is outside the episode");
  for (const directory of [args.publicRun, args.privateRun, args.workdir]) {
    if (!fs.existsSync(directory)) throw new Error(`Missing directory: ${directory}`);
  }
  const outputsDir = path.join(args.workdir, "outputs");
  const allArtifacts = await outputManifest(outputsDir);
  const allNormalized = [];
  const turnResults = [];
  let threadId = null;

  for (let index = 0; index < args.fromTurn; index += 1) {
    const publicTurnDir = path.join(args.publicRun, "turns", `turn-${String(index).padStart(2, "0")}`);
    const turnResult = JSON.parse(await fsp.readFile(path.join(publicTurnDir, "turn-result.json"), "utf8"));
    turnResults.push(turnResult);
    const trace = await fsp.readFile(path.join(publicTurnDir, "trajectory.jsonl"), "utf8");
    allNormalized.push(...trace.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line)));
    threadId = turnResult.trace_summary?.thread_id || threadId;
  }

  const logicalSessions = ["session-01", ...episode.feedback.map((item) => item.session_id)];
  for (let index = args.fromTurn; index < intendedTurns; index += 1) {
    const turn = await recoveredTurn({
      args,
      turnIndex: index,
      logicalSessionId: logicalSessions[index],
      allArtifacts,
    });
    turnResults.push(turn.result);
    allNormalized.push(...turn.normalized);
    threadId = turn.threadId || threadId;
  }

  const publicOutputs = path.join(args.publicRun, "outputs");
  await fsp.cp(outputsDir, publicOutputs, { recursive: true, force: true });
  const copiedArtifacts = await outputManifest(publicOutputs);
  if (JSON.stringify(copiedArtifacts) !== JSON.stringify(allArtifacts)) {
    throw new Error("Public output copy failed manifest verification");
  }
  await fsp.writeFile(
    path.join(args.publicRun, "trajectory.jsonl"),
    `${allNormalized.map((event) => JSON.stringify(event)).join("\n")}\n`,
    "utf8",
  );
  const inputManifest = JSON.parse(await fsp.readFile(path.join(args.publicRun, "input-manifest.json"), "utf8"));
  const artifactNames = new Set(allArtifacts.map((item) => path.basename(item.filename)));
  const requiredCandidateArtifacts = query.required_structured_artifacts.filter(
    (name) => name !== "trajectory.jsonl",
  );
  const artifactContract = Object.fromEntries(
    requiredCandidateArtifacts.map((name) => [name, artifactNames.has(name)]),
  );
  artifactContract["trajectory.jsonl"] = allNormalized.length > 0;
  const cli = spawnSync(process.env.CODEX_BIN || "codex", ["--version"], { encoding: "utf8" });
  if (cli.status !== 0) throw new Error(cli.stderr || "Unable to read Codex CLI version");
  const result = {
    schema_version: "codex-design-agent-v02-run-v1",
    candidate: CANDIDATE,
    cli_version: cli.stdout.trim(),
    run_mode: "full-episode",
    query_id: query.id,
    base_brief_id: query.base_brief_id,
    context_condition: query.context_condition,
    category: query.category,
    capability_level: query.capability_level,
    capability_tags: query.capability_tags,
    future_feedback_visible_at_turn_0: false,
    started_at: turnResults[0].started_at,
    finished_at: turnResults.at(-1).finished_at,
    latency_ms: turnResults.reduce((total, turn) => total + Number(turn.latency_ms || 0), 0),
    intended_turns: intendedTurns,
    completed_turns: intendedTurns,
    logical_sessions: [...new Set(logicalSessions)],
    codex_thread_id: threadId,
    input_assets: inputManifest,
    input_context_ids: query.input_context.map((item) => item.id),
    required_candidate_artifacts: query.required_structured_artifacts,
    artifact_contract: artifactContract,
    artifacts: allArtifacts,
    turn_results: turnResults,
    usage: aggregateUsage(turnResults),
    operational_recovery: {
      from_turn: args.fromTurn,
      counted_client_turns: intendedTurns,
      extra_client_feedback_turns: 0,
      retry_added_design_requirements: false,
      note: "Interrupted execution attempts are retained and labeled; only completed attempts satisfy a benchmark turn.",
    },
    outcome: "completed",
  };
  await fsp.writeFile(path.join(args.publicRun, "result.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");
  await fsp.appendFile(
    RUN_INDEX,
    `${JSON.stringify({ ...result, run_path: path.relative(EXPERIMENT_DIR, args.publicRun) })}\n`,
  );
  process.stdout.write(
    `${query.id}: completed; turns=${intendedTurns}/${intendedTurns}; artifacts=${allArtifacts.length}; ` +
      `recovered_from_turn=${args.fromTurn}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
