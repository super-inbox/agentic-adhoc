"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const http = require("node:http");

const {
  buildCurifyJobs,
  buildGptJobs,
  fillPrompt,
  jobResult,
  pendingJobs,
  renderGalleryHtml,
  stageRecords,
  summarizeImagegenLog,
} = require("../../scripts/vir-image-tasks.cjs");

const {
  MODEL: GEMINI_MODEL,
  buildGeminiJobs,
  findGeminiOutput,
  pendingGeminiJobs,
  productionSlug,
  renderGeminiJobs,
} = require("../../scripts/vir-gemini-production.cjs");

test("paired image stages preserve the requested execution counts", () => {
  assert.equal(stageRecords("anchors").length, 16);
  assert.equal(stageRecords("exploration").length, 30);
  assert.equal(stageRecords("core").length, 450);
  assert.equal(stageRecords("challenge-gap").length, 200);

  assert.equal(buildGptJobs(stageRecords("anchors"), "anchors").length, 16);
  assert.equal(
    buildGptJobs(stageRecords("exploration"), "exploration").length,
    90,
  );
});

test("Curify jobs use ranked template plans and filled prompts", () => {
  const records = [
    {
      id: "vir-v2-test",
      query: "a quiet reading corner",
      language: "en",
      partition: "core",
    },
  ];
  const plans = [
    {
      query_id: "vir-v2-test",
      status: "completed",
      plan: {
        source: "template_match",
        directions: [
          {
            template_id: "template-test",
            params: { topic: "quiet reading" },
            confidence: 0.9,
            reason: "fixture",
          },
        ],
      },
    },
  ];
  const templates = [
    {
      id: "template-test",
      locales: { en: { base_prompt: "Create a poster about {topic}." } },
    },
  ];

  const { jobs, omissions } = buildCurifyJobs(
    records,
    plans,
    templates,
    "core",
  );
  assert.equal(jobs.length, 1);
  assert.equal(jobs[0].prompt, "Create a poster about quiet reading.");
  assert.match(jobs[0].out, /template-test\.jpeg$/);
  assert.deepEqual(omissions, []);
});

test("unfilled optional prompt fields remain explicit for auditability", () => {
  assert.equal(fillPrompt("{topic} for {audience}", { topic: "plants" }), "plants for {audience}");
});

test("paired gallery shows completed and pending outputs without scoring visuals", () => {
  const html = renderGalleryHtml({
    stage: "anchors",
    records: [
      {
        id: "vir-gallery-test",
        query: "plants <and> facts",
        language: "en",
        partition: "core",
        difficulty: "low",
      },
    ],
    gptResults: [
      {
        vir_query_id: "vir-gallery-test",
        vir_direction: 1,
        status: "completed",
        local_path: "reports/run/gpt-direct/image.jpeg",
      },
    ],
    curifyResults: [
      {
        vir_query_id: "vir-gallery-test",
        vir_direction: 1,
        status: "pending",
        local_path: null,
        vir_metadata: { template_id: "template-test" },
      },
    ],
    omissions: [],
  });
  assert.match(html, /gpt-direct\/image\.jpeg/);
  assert.match(html, /Pending \/ failed/);
  assert.match(html, /plants &lt;and&gt; facts/);
  assert.match(html, /Human inspection only/);
});

test("terminal failures are excluded from resume input and remain auditable", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "vir-images-"));
  const job = { prompt: "blocked prompt", out: "blocked.jpeg" };
  const crypto = require("node:crypto");
  const failures = new Map([
    [
      job.out,
      {
        out: job.out,
        prompt_sha256: crypto.createHash("sha256").update(job.prompt).digest("hex"),
        reason: "moderation_blocked_after_retry",
        marked_at: "2026-08-02T00:00:00.000Z",
      },
    ],
  ]);

  assert.deepEqual(pendingJobs([job], directory, failures), []);
  assert.equal(jobResult(job, directory, failures).status, "failed");
  assert.equal(
    jobResult(job, directory, failures).failure_reason,
    "moderation_blocked_after_retry",
  );
});

test("image log summary distinguishes historical billing from the latest run", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "vir-log-"));
  const logPath = path.join(directory, "imagegen.log");
  fs.writeFileSync(
    logPath,
    "[2026-08-01T00:00:00.000Z] pending=2 concurrency=1\n" +
      "billing_hard_limit_reached\nexit_code=1 signal=none\n\n" +
      "[2026-08-02T00:00:00.000Z] pending=1 concurrency=1\n" +
      "moderation_blocked\nexit_code=1 signal=none\n",
  );

  const summary = summarizeImagegenLog(logPath);
  assert.equal(summary.billing_hard_limit_reached, 1);
  assert.equal(summary.last_run.billing_hard_limit_reached, 0);
  assert.equal(summary.last_run.moderation_blocked, 1);
});

test("production Gemini jobs preserve Curify template parameters and use stable slugs", () => {
  const curifyJobs = [
    {
      prompt: "Create a plant science card.",
      vir_query_id: "vir-v2-example",
      vir_direction: 1,
      vir_metadata: {
        source_query: "植物知识卡",
        stage: "core",
        partition: "core",
        language: "zh",
        template_id: "template-species-science",
        params: { subject: "植物" },
        confidence: 0.91,
        reason: "fixture",
        plan_source: "template_match",
      },
    },
  ];
  const first = buildGeminiJobs(curifyJobs, "fixture-run", "core")[0];
  const second = buildGeminiJobs(curifyJobs, "fixture-run", "core")[0];

  assert.equal(first.model, GEMINI_MODEL);
  assert.equal(first.template_id, "template-species-science");
  assert.deepEqual(first.params, { subject: "植物" });
  assert.equal(first.locale, "zh");
  assert.equal(first.slug, second.slug);
  assert.equal(
    first.slug,
    productionSlug(
      "fixture-run",
      "core",
      "vir-v2-example",
      1,
      "template-species-science",
    ),
  );
});

test("Gemini production renderer checkpoints an image and resumes without a network call", async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "vir-gemini-"));
  const outDir = path.join(directory, "images");
  const resultPath = path.join(directory, "results.jsonl");
  const eventPath = path.join(directory, "events.jsonl");
  const prompt = "Create a fixture poster.";
  const job = {
    schema_version: 1,
    query_id: "vir-v2-fixture",
    query: "fixture",
    stage: "anchors",
    partition: "core",
    language: "en",
    direction: 1,
    template_id: "template-fixture",
    params: { topic: "fixture" },
    locale: "en",
    slug: "vir-gemini-fixture",
    expected_prompt: prompt,
    expected_prompt_sha256: "fixture-hash",
    model: GEMINI_MODEL,
    endpoint: "/api/generate-image",
  };
  const png = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 0]);
  let postCount = 0;
  const server = http.createServer((request, response) => {
    if (request.method === "POST") {
      postCount += 1;
      request.resume();
      response.setHeader("Content-Type", "application/json");
      response.end(
        JSON.stringify({
          url: `/api/generate-image/${job.slug}.png`,
          prompt,
          bytes: png.length,
        }),
      );
      return;
    }
    response.setHeader("Content-Type", "image/png");
    response.end(png);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;
  try {
    const first = await renderGeminiJobs({
      jobs: [job],
      outDir,
      resultPath,
      eventPath,
      baseUrl,
      concurrency: 1,
      maxAttempts: 1,
    });
    assert.equal(first.completed, 1);
    assert.equal(postCount, 1);
    assert.ok(findGeminiOutput(job, outDir));
    assert.deepEqual(pendingGeminiJobs([job], outDir), []);

    const resumed = await renderGeminiJobs({
      jobs: [job],
      outDir,
      resultPath,
      eventPath,
      baseUrl,
      concurrency: 1,
      maxAttempts: 1,
    });
    assert.equal(resumed.requested, 0);
    assert.equal(postCount, 1);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
