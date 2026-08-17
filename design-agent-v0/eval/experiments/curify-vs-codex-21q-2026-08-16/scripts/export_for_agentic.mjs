#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BRAINTRUST_EVAL = path.resolve(HERE, "../..");
const DATASET = path.join(
  BRAINTRUST_EVAL,
  "results/design-agent-bench-v0.1-multimodal-pilot.dataset.jsonl",
);
const CURIFY_RUNS = path.resolve(HERE, "../curify-jwang-vercel-275f7d0a/runs");
const CODEX_RUNS = path.resolve(HERE, "../codex-v0.2/runs");

function destination(argv) {
  const index = argv.indexOf("--destination");
  if (index < 0 || !argv[index + 1]) {
    throw new Error("Usage: export_for_agentic.mjs --destination <experiment-directory>");
  }
  return path.resolve(argv[index + 1]);
}

function latestRun(root, taskId) {
  const taskRoot = path.join(root, taskId);
  const names = fs
    .readdirSync(taskRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((name) => fs.existsSync(path.join(taskRoot, name, "result.json")))
    .sort()
    .reverse();
  if (!names.length) throw new Error(`No result found for ${taskId} under ${root}`);
  const runDir = path.join(taskRoot, names[0]);
  return {
    runDir,
    result: JSON.parse(fs.readFileSync(path.join(runDir, "result.json"), "utf8")),
  };
}

function copyFile(source, target) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
}

function sanitizedText(source, runDir) {
  let value = fs.readFileSync(source, "utf8");
  const candidates = new Set([runDir]);
  try {
    candidates.add(fs.realpathSync(runDir));
  } catch {
    // The archived run directory still exists even if its original temp path does not.
  }
  for (const candidate of candidates) value = value.split(candidate).join("<WORKDIR>");
  value = value
    .replace(/\/Users\/[^/]+\/\.cache\/codex-runtimes/g, "<CODEX_RUNTIME_CACHE>")
    .replace(/\/Users\/[^/]+\/\.codex/g, "<CODEX_HOME>")
    .replace(
      /\/(?:private\/)?var\/folders\/[^\s"']+\/codex-design-benchmark-[A-Za-z0-9]+/g,
      "<WORKDIR>",
    );
  return value;
}

function writeSanitized(source, target, runDir) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, sanitizedText(source, runDir), "utf8");
}

function renderPdf(source, destinationStem) {
  fs.mkdirSync(path.dirname(destinationStem), { recursive: true });
  execFileSync("pdftoppm", [
    "-f",
    "1",
    "-singlefile",
    "-png",
    "-r",
    "150",
    source,
    destinationStem,
  ]);
  return `${destinationStem}.png`;
}

function main() {
  const target = destination(process.argv.slice(2));
  const candidateRoot = path.join(target, "candidates");
  if (fs.existsSync(candidateRoot)) {
    throw new Error(`Refusing to overwrite existing candidate export: ${candidateRoot}`);
  }
  fs.mkdirSync(candidateRoot, { recursive: true });
  const rows = fs
    .readFileSync(DATASET, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line))
    .sort((left, right) => left.input.task_id.localeCompare(right.input.task_id));

  const curifyRecords = [];
  const codexRecords = [];
  const derivedRenders = [];
  for (const row of rows) {
    const taskId = row.input.task_id;

    const curify = latestRun(CURIFY_RUNS, taskId);
    const curifyOutputs = [];
    for (const artifact of curify.result.artifacts || []) {
      const source = path.join(curify.runDir, artifact.filename);
      const relative = path.join("candidates", "curify", "outputs", taskId, artifact.filename);
      copyFile(source, path.join(target, relative));
      curifyOutputs.push(relative);
    }
    curifyRecords.push({
      task_id: taskId,
      outcome: curify.result.outcome,
      output_paths: curifyOutputs,
      latency_ms: curify.result.latency_ms,
      uploaded_asset_roles: curify.result.uploaded_asset_roles || [],
      omitted_asset_roles: curify.result.omitted_asset_roles || [],
      estimated_credits: curify.result.estimated_credits_spent,
    });

    const codex = latestRun(CODEX_RUNS, taskId);
    const codexTarget = path.join(target, "candidates", "codex", "runs", taskId);
    const outputPaths = [];
    for (const artifact of codex.result.artifacts || []) {
      const source = path.join(codex.runDir, "outputs", artifact.filename);
      const relative = path.join("candidates", "codex", "runs", taskId, "outputs", artifact.filename);
      copyFile(source, path.join(target, relative));
      outputPaths.push(relative);
      if (path.extname(source).toLowerCase() === ".pdf") {
        const renderStem = path.join(
          target,
          "candidates",
          "codex",
          "derived-renders",
          taskId,
          path.basename(artifact.filename, ".pdf"),
        );
        const renderPath = renderPdf(source, renderStem);
        derivedRenders.push({
          task_id: taskId,
          source_output_path: relative,
          render_path: path.relative(target, renderPath),
          provenance: "evaluator-derived first-page render; not a candidate artifact",
        });
      }
    }
    for (const filename of ["trace.jsonl", "final-response.txt"]) {
      const source = path.join(codex.runDir, filename);
      if (fs.existsSync(source)) writeSanitized(source, path.join(codexTarget, filename), codex.runDir);
    }
    copyFile(path.join(codex.runDir, "result.json"), path.join(codexTarget, "result.json"));
    codexRecords.push({
      task_id: taskId,
      outcome: codex.result.outcome,
      output_paths: outputPaths,
      trajectory_path: path.join("candidates", "codex", "runs", taskId, "trace.jsonl"),
      final_response_path: fs.existsSync(path.join(codex.runDir, "final-response.txt"))
        ? path.join("candidates", "codex", "runs", taskId, "final-response.txt")
        : null,
      latency_ms: codex.result.latency_ms,
      loaded_asset_roles: codex.result.uploaded_asset_roles || [],
      trace_summary: codex.result.trace_summary || {},
    });
  }

  const writeJsonl = (filename, records) => {
    fs.writeFileSync(
      path.join(target, filename),
      `${records.map((record) => JSON.stringify(record)).join("\n")}\n`,
      "utf8",
    );
  };
  writeJsonl("curify-output-paths.jsonl", curifyRecords);
  writeJsonl("codex-output-and-trajectory-paths.jsonl", codexRecords);
  writeJsonl("codex-derived-renders.jsonl", derivedRenders);
  process.stdout.write(
    `Exported ${curifyRecords.length} Curify and ${codexRecords.length} Codex cases to ${target}\n`,
  );
}

main();
