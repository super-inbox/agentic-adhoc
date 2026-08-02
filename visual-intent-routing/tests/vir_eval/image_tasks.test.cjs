"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

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
