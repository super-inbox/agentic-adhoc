#!/usr/bin/env node

/*
 * Paid, single-trial canary runner for the Curify frontend branch
 * jwang/vercel@275f7d0a. It remaps the existing production Curify
 * localStorage session to the local Next.js origin in memory; credentials are
 * never written into the run artifacts.
 */

const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");

const CANDIDATE = "curify-web-jwang-vercel@275f7d0a";
const DEFAULT_BASE_URL = "http://localhost:3100";
const DEFAULT_TIMEOUT_MS = 15 * 60 * 1000;
const SYSTEM_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const INTERESTING_PATHS = [
  "/api/design-agent/",
  "/images/upload",
  "/nano-templates/generate",
  "/nano-freeform/generate",
  "/projects/",
];

const RUN_DIR = __dirname;
const EVAL_DIR = path.resolve(RUN_DIR, "../../..");
const AUTH_STATE = path.resolve(
  RUN_DIR,
  "../../.auth/curify-web-storage-state.json",
);
const DATASET_PATH = path.join(
  EVAL_DIR,
  "braintrust_eval/results/design-agent-bench-v0.1-multimodal-pilot.dataset.jsonl",
);

function portableAssetPath(assetPath) {
  if (fs.existsSync(assetPath)) return assetPath;
  const marker = `${path.sep}eval${path.sep}assets${path.sep}`;
  const markerIndex = assetPath.lastIndexOf(marker);
  if (markerIndex < 0) return assetPath;
  return path.join(EVAL_DIR, "assets", assetPath.slice(markerIndex + marker.length));
}

function loadBenchmarkCases() {
  const rows = fs
    .readFileSync(DATASET_PATH, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
  return Object.fromEntries(
    rows.map((row) => [
      row.input.task_id,
      {
        id: row.input.task_id,
        kind: "benchmark-single-turn",
        brief: row.input.brief,
        assets: row.input.assets.map((asset) => portableAssetPath(asset.path)),
        assetRoles: row.input.assets.map((asset) => asset.role),
        expectedSteps: 1,
        workflowDomain: null,
        category: row.metadata.category,
        capabilityId: row.metadata.capability_id,
      },
    ]),
  );
}

const CASES = loadBenchmarkCases();

function parseArgs(argv) {
  const args = {
    baseUrl: process.env.CURIFY_CANARY_BASE_URL || DEFAULT_BASE_URL,
    timeoutMs: Number(process.env.CURIFY_CANARY_TIMEOUT_MS || DEFAULT_TIMEOUT_MS),
    allowPaid: false,
    probe: false,
    allBenchmark: false,
    ids: [],
  };
  for (let i = 0; i < argv.length; i += 1) {
    const value = argv[i];
    if (value === "--allow-paid-generation") args.allowPaid = true;
    else if (value === "--probe") args.probe = true;
    else if (value === "--all-benchmark") args.allBenchmark = true;
    else if (value === "--base-url") args.baseUrl = argv[++i];
    else if (value === "--timeout-ms") args.timeoutMs = Number(argv[++i]);
    else if (value === "--case") args.ids.push(argv[++i]);
    else throw new Error(`Unknown argument: ${value}`);
  }
  if (args.allBenchmark && args.ids.length) {
    throw new Error("Use either --all-benchmark or one or more --case values, not both");
  }
  if (args.allBenchmark) args.ids = Object.keys(CASES).sort();
  if (!args.probe && args.ids.length === 0) {
    throw new Error("Select --all-benchmark, at least one --case, or use --probe");
  }
  if (!args.probe && !args.allowPaid) {
    throw new Error(
      "Paid generation is disabled. Pass --allow-paid-generation after confirming the Curify credit budget.",
    );
  }
  for (const id of args.ids) {
    if (!CASES[id]) throw new Error(`Unknown case: ${id}`);
  }
  return args;
}

function isoFileTimestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function interestingUrl(url) {
  try {
    const parsed = new URL(url);
    return INTERESTING_PATHS.some((needle) => parsed.pathname.includes(needle));
  } catch {
    return false;
  }
}

function sanitizedPath(url) {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

function durableArtifactUrl(url) {
  if (!url) return url;
  try {
    const parsed = new URL(url);
    parsed.search = "";
    parsed.hash = "";
    return `${parsed.origin}${parsed.pathname}`.replace(
      /images\/uploads\/\d+\//g,
      "images/uploads/[user]/",
    );
  } catch {
    return String(url).split("?")[0];
  }
}

function contentTypeExtension(contentType) {
  if (/png/i.test(contentType || "")) return ".png";
  if (/webp/i.test(contentType || "")) return ".webp";
  if (/jpe?g/i.test(contentType || "")) return ".jpg";
  return ".bin";
}

async function remappedStorageState(baseUrl) {
  const raw = JSON.parse(await fsp.readFile(AUTH_STATE, "utf8"));
  const source = (raw.origins || []).find((entry) =>
    (entry.localStorage || []).some((item) => item.name === "access_token"),
  );
  if (!source) throw new Error("Saved Curify session has no access_token origin");
  const allowed = new Set(["access_token", "refresh_token", "curifyUser"]);
  const localStorage = source.localStorage.filter((item) => allowed.has(item.name));
  const names = new Set(localStorage.map((item) => item.name));
  if (!names.has("access_token") || !names.has("curifyUser")) {
    throw new Error("Saved Curify session is incomplete");
  }
  return {
    cookies: [],
    origins: [{ origin: new URL(baseUrl).origin, localStorage }],
  };
}

async function terminalStates(page, plan, timeoutMs) {
  const expected = Array.isArray(plan?.steps) ? plan.steps.length : 0;
  await page.waitForFunction(
    ({ expectedCount }) => {
      const cards = [...document.querySelectorAll("ol > li")];
      if (!cards.length || (expectedCount && cards.length !== expectedCount)) return false;
      const terminal = new Set(["done", "blocked", "failed"]);
      return cards.every((card) =>
        [...card.querySelectorAll("span")].some((span) =>
          terminal.has((span.textContent || "").trim().toLowerCase()),
        ),
      );
    },
    { expectedCount: expected },
    { timeout: timeoutMs },
  );

  const cards = page.locator("ol > li");
  const states = [];
  for (let index = 0; index < (await cards.count()); index += 1) {
    const card = cards.nth(index);
    const text = await card.innerText();
    const badges = (await card.locator("span").allInnerTexts()).map((item) =>
      item.trim().toLowerCase(),
    );
    const status = ["done", "blocked", "failed"].find((item) => badges.includes(item));
    const images = card.locator("img");
    const resultUrl = (await images.count()) ? await images.last().getAttribute("src") : null;
    const verifyMatch = text.match(/verify:\s*(passed|failed)\s*[—-]\s*(.+)/i);
    const step = plan?.steps?.[index] || {};
    states.push({
      n: step.n || index + 1,
      tool_id: step.tool_id || null,
      template_id: step.template_id || null,
      label: step.label || null,
      status: status || "unknown",
      result_url: resultUrl,
      verify: verifyMatch
        ? {
            ok: verifyMatch[1].toLowerCase() === "passed",
            note: verifyMatch[2].trim(),
          }
        : null,
      visible_text: text,
    });
  }
  return states;
}

async function downloadArtifacts(context, states, caseDir) {
  const artifacts = [];
  let outputIndex = 0;
  for (const state of states) {
    if (!state.result_url) continue;
    outputIndex += 1;
    const response = await context.request.get(state.result_url, { timeout: 120_000 });
    const contentType = response.headers()["content-type"] || "application/octet-stream";
    const extension = contentTypeExtension(contentType);
    const filename = `output-${String(outputIndex).padStart(2, "0")}-step-${state.n}${extension}`;
    const destination = path.join(caseDir, filename);
    const body = await response.body();
    await fsp.writeFile(destination, body);
    artifacts.push({
      step: state.n,
      filename,
      byte_size: body.length,
      content_type: contentType,
      http_status: response.status(),
    });
  }
  return artifacts;
}

async function runProbe(browser, args, storageState) {
  const context = await browser.newContext({
    storageState,
    viewport: { width: 1440, height: 1200 },
  });
  const page = await context.newPage();
  await page.goto(`${args.baseUrl}/design-agent`, {
    waitUntil: "domcontentloaded",
    timeout: 90_000,
  });
  await page.getByRole("heading", { name: "Design Agent" }).waitFor();
  try {
    await page.locator('input[type="file"]').waitFor({ state: "attached", timeout: 15_000 });
  } catch {
    // Report the mounted surface below rather than failing without diagnostics.
  }
  const auth = await page.evaluate(() => ({
    hasAccessToken: Boolean(localStorage.getItem("access_token")),
    hasUser: Boolean(localStorage.getItem("curifyUser")),
  }));
  const uploaderCount = await page.locator('input[type="file"]').count();
  const signInGate = await page
    .getByRole("button", { name: /Sign in to upload an image/ })
    .count();
  const result = {
    candidate: CANDIDATE,
    base_url: args.baseUrl,
    auth,
    uploader_mounted: uploaderCount > 0,
    sign_in_gate_visible: signInGate > 0,
    checked_at: new Date().toISOString(),
  };
  await context.close();
  return result;
}

async function runCase(browser, args, storageState, testCase) {
  const runStartedAt = new Date();
  const caseDir = path.join(RUN_DIR, "runs", testCase.id, isoFileTimestamp());
  await fsp.mkdir(caseDir, { recursive: true });

  const context = await browser.newContext({
    storageState,
    viewport: { width: 1440, height: 1200 },
    acceptDownloads: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(Math.min(args.timeoutMs, 60_000));

  const network = [];
  const trajectory = [];
  const consoleErrors = [];
  const requestStarted = new WeakMap();
  let plan = null;
  let clickStartedAt = null;
  let error = null;
  let states = [];
  let artifacts = [];

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text().slice(0, 500));
  });
  page.on("request", (request) => {
    if (!interestingUrl(request.url())) return;
    requestStarted.set(request, Date.now());
    if (sanitizedPath(request.url()) === "/api/design-agent/trajectory") {
      try {
        const body = request.postDataJSON();
        for (const event of body?.events || []) trajectory.push(event);
      } catch {
        // A malformed trace body should not interrupt the product run.
      }
    }
  });
  page.on("response", (response) => {
    if (!interestingUrl(response.url())) return;
    const request = response.request();
    network.push({
      method: request.method(),
      path: sanitizedPath(response.url()),
      status: response.status(),
      latency_ms: requestStarted.has(request) ? Date.now() - requestStarted.get(request) : null,
    });
  });

  try {
    const suffix = testCase.workflowDomain
      ? `/design-agent?workflow=${encodeURIComponent(testCase.workflowDomain)}`
      : "/design-agent";
    await page.goto(`${args.baseUrl}${suffix}`, {
      waitUntil: "domcontentloaded",
      timeout: 90_000,
    });
    await page.getByRole("heading", { name: "Design Agent" }).waitFor();

    const authenticated = await page.evaluate(
      () => Boolean(localStorage.getItem("access_token") && localStorage.getItem("curifyUser")),
    );
    if (!authenticated) throw new Error("Saved Curify session did not mount on the local origin");

    const input = page.locator('input[type="file"]');
    await input.waitFor({ state: "attached", timeout: 20_000 });
    const uploadPromise = page.waitForResponse(
      (response) => sanitizedPath(response.url()).includes("/images/upload"),
      { timeout: 90_000 },
    );
    await input.setInputFiles(testCase.assets[0]);
    const uploadResponse = await uploadPromise;
    if (!uploadResponse.ok()) {
      throw new Error(`Reference upload failed (${uploadResponse.status()})`);
    }
    await page.locator('img[alt="Reference"]').waitFor({ state: "visible" });

    await page
      .getByPlaceholder("e.g. a modern coffee shop for young professionals")
      .fill(testCase.brief);

    for (const field of testCase.supplementalFields || []) {
      await page.getByPlaceholder(field.placeholder).fill(field.value);
    }

    const runButton = testCase.workflowDomain
      ? page.getByRole("button", { name: /Run 5 steps/ })
      : page.getByRole("button", { name: /Run agent/ });
    await runButton.waitFor({ state: "visible" });
    if (!(await runButton.isEnabled())) throw new Error("Run button is disabled");

    const planPromise = page.waitForResponse(
      (response) =>
        sanitizedPath(response.url()) === "/api/design-agent/plan" &&
        response.request().method() === "POST",
      { timeout: 90_000 },
    );
    clickStartedAt = Date.now();
    await runButton.click();
    const planResponse = await planPromise;
    if (!planResponse.ok()) {
      throw new Error(`Plan endpoint failed (${planResponse.status()})`);
    }
    plan = await planResponse.json();

    states = await terminalStates(page, plan, args.timeoutMs);
    await page.waitForTimeout(2_000);
    artifacts = await downloadArtifacts(context, states, caseDir);
  } catch (caught) {
    error = `${caught?.name || "Error"}: ${caught?.message || String(caught)}`;
  }

  try {
    await page.screenshot({ path: path.join(caseDir, "final-page.png"), fullPage: true });
  } catch {
    // Preserve the primary error if screenshot capture also fails.
  }

  const runFinishedAt = new Date();
  const uploaded = [path.basename(testCase.assets[0])];
  const omitted = testCase.assets.slice(1).map((asset) => path.basename(asset));
  const result = {
    schema_version: "curify-canary-v1",
    candidate: CANDIDATE,
    frontend_branch: "jwang/vercel",
    frontend_commit: "275f7d0a111b8fe0c4c5a5409c548932d003cb9f",
    base_url: args.baseUrl,
    task_id: testCase.id,
    task_kind: testCase.kind,
    category: testCase.category || null,
    capability_id: testCase.capabilityId || null,
    brief: testCase.brief,
    workflow_domain: testCase.workflowDomain,
    supplemental_fields: (testCase.supplementalFields || []).map((field) => ({
      placeholder: String(field.placeholder),
      value: field.value,
    })),
    started_at: runStartedAt.toISOString(),
    finished_at: runFinishedAt.toISOString(),
    latency_ms: clickStartedAt ? runFinishedAt.getTime() - clickStartedAt : null,
    paid_trial_count: clickStartedAt ? 1 : 0,
    estimated_credits_spent: clickStartedAt
      ? (plan?.steps || []).filter((step) => !step.blocked).length * 10
      : 0,
    input_capacity: 1,
    uploaded_assets: uploaded,
    uploaded_asset_roles: (testCase.assetRoles || []).slice(0, 1),
    omitted_assets: omitted,
    omitted_asset_roles: (testCase.assetRoles || []).slice(1),
    exact_input_preserved: omitted.length === 0,
    plan,
    states: states.map((state) => ({
      ...state,
      result_url: durableArtifactUrl(state.result_url),
    })),
    artifacts,
    trajectory,
    network,
    console_errors: consoleErrors,
    error,
    outcome: error
      ? "error"
      : states.every((state) => state.status === "done")
        ? "completed"
        : states.some((state) => state.status === "done")
          ? "partial"
          : "failed",
  };

  await fsp.writeFile(
    path.join(caseDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  await context.close();
  return { caseDir, result };
}

async function appendIndex(result) {
  await fsp.appendFile(
    path.join(RUN_DIR, "run-index.jsonl"),
    `${JSON.stringify(result)}\n`,
    "utf8",
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!fs.existsSync(AUTH_STATE)) throw new Error(`Auth state not found: ${AUTH_STATE}`);
  const storageState = await remappedStorageState(args.baseUrl);
  const executablePath = process.env.CURIFY_CANARY_BROWSER_PATH ||
    (fs.existsSync(SYSTEM_CHROME) ? SYSTEM_CHROME : undefined);
  const browser = await chromium.launch({
    headless: true,
    executablePath,
    // The production API allows the deployed Curify origin, not localhost.
    // This isolated browser flag lets the local branch exercise the same API
    // without changing backend CORS policy or product code.
    args: ["--disable-web-security"],
  });
  try {
    if (args.probe) {
      const result = await runProbe(browser, args, storageState);
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
      if (!result.auth.hasAccessToken || !result.auth.hasUser || !result.uploader_mounted) {
        process.exitCode = 2;
      }
      return;
    }

    for (const id of args.ids) {
      process.stdout.write(`Running ${id} once against ${CANDIDATE}...\n`);
      const { caseDir, result } = await runCase(browser, args, storageState, CASES[id]);
      await appendIndex(result);
      process.stdout.write(
        `${id}: ${result.outcome}; ${result.artifacts.length} artifact(s); ` +
          `${result.latency_ms ?? "n/a"} ms; ${caseDir}\n`,
      );
      if (result.error) process.stdout.write(`${result.error}\n`);
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
