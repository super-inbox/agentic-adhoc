"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  buildCurifyJobs,
  buildGptJobs,
  fillPrompt,
  renderGalleryHtml,
  stageRecords,
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
