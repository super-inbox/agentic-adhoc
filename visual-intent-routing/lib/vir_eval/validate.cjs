"use strict";

const fs = require("fs");
const path = require("path");
const {
  hashObject,
  loadJson,
  normalizeQuery,
  readJsonl,
  resolveRoot,
  sha256,
  writeJson,
  writeJsonl,
} = require("./common.cjs");
const { CharacterNgramSimilarity } = require("./similarity.cjs");
const { validateRecord } = require("./schema.cjs");

function csvCell(value) {
  const text =
    value === null || value === undefined
      ? ""
      : typeof value === "string"
        ? value
        : JSON.stringify(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeCsv(filePath, headers, rows) {
  const absolute = resolveRoot(filePath);
  fs.mkdirSync(path.dirname(absolute), { recursive: true });
  const lines = [
    headers.map(csvCell).join(","),
    ...rows.map((row) => headers.map((header) => csvCell(row[header])).join(",")),
  ];
  fs.writeFileSync(absolute, `${lines.join("\n")}\n`);
}

function languageSignals(query) {
  const han = (query.match(/\p{Script=Han}/gu) ?? []).length;
  const latin = (query.match(/[A-Za-z]/g) ?? []).length;
  return { han, latin };
}

function languageConsistency(record) {
  const { han, latin } = languageSignals(record.query);
  if (record.language === "zh" && han === 0) {
    return "zh label has no Han characters";
  }
  if (record.language === "en" && latin === 0) {
    return "en label has no Latin letters";
  }
  if (record.language === "mixed" && (han === 0 || latin === 0)) {
    return "mixed label requires both Han and Latin text";
  }
  return null;
}

function goldSignature(record) {
  return JSON.stringify({
    mode: record.gold.target_mode,
    targets: [...record.gold.targets].sort(),
    acceptable: (record.gold.acceptable_target_sets ?? [])
      .map((set) => [...set].sort())
      .sort(),
    abstain: record.gold.must_abstain,
    exploration: record.gold.exploration ?? null,
  });
}

function distribution(records, key) {
  const counts = {};
  for (const record of records) {
    const values =
      key === "target"
        ? record.gold.targets.length
          ? record.gold.targets
          : ["__none__"]
        : key === "transformation_type"
          ? record.transformation_types
          : [record[key]];
    for (const value of values) counts[value] = (counts[value] ?? 0) + 1;
  }
  return counts;
}

function findNearDuplicates(records, threshold, similarity) {
  const collisions = [];
  for (let left = 0; left < records.length; left += 1) {
    for (let right = left + 1; right < records.length; right += 1) {
      const a = records[left];
      const b = records[right];
      if (normalizeQuery(a.query) === normalizeQuery(b.query)) continue;
      const score = similarity.similarity(a.query, b.query);
      if (score >= threshold) {
        collisions.push({
          left_id: a.id,
          right_id: b.id,
          similarity: Number(score.toFixed(4)),
          same_semantic_cluster:
            a.semantic_cluster_id === b.semantic_cluster_id,
        });
      }
    }
  }
  return collisions;
}

function fullCatalogEntries(capabilityKb) {
  return (capabilityKb.templates ?? []).map((entry) => ({
    template_id: entry.template_id,
    text: [
      entry.title,
      entry.category,
      entry.description,
      ...(entry.param_names ?? []),
      ...(entry.template_topics ?? []),
      ...(entry.sample_param_values ?? []),
      ...(entry.inspiration_tags ?? []),
      ...(entry.inspiration_topics ?? []),
    ]
      .filter(Boolean)
      .join(" "),
  }));
}

function contentGapCollisions(records, capabilityKb, similarity, threshold) {
  const catalog = fullCatalogEntries(capabilityKb);
  return records
    .filter((record) => record.gold.target_mode === "none")
    .map((record) => {
      const top = similarity
        .closest(record.query, catalog, (entry) => entry.text)
        .slice(0, 3)
        .map(({ entry, similarity: score }) => ({
          template_id: entry.template_id,
          similarity: Number(score.toFixed(4)),
        }));
      return {
        record_id: record.id,
        query: record.query,
        top_competing_templates: top,
        warning: (top[0]?.similarity ?? 0) >= threshold,
      };
    });
}

function balanceWarnings(core, config) {
  const warnings = [];
  const languageCounts = distribution(core, "language");
  const difficultyCounts = distribution(core, "difficulty");
  const total = core.length || 1;
  for (const [language, expected] of Object.entries(
    config.expansion.languages,
  )) {
    const actual = (languageCounts[language] ?? 0) / total;
    if (Math.abs(actual - expected) > 0.08) {
      warnings.push(
        `language ${language}: ${(actual * 100).toFixed(1)}% vs ${(expected * 100).toFixed(1)}%`,
      );
    }
  }
  for (const [difficulty, expected] of Object.entries(
    config.expansion.difficulties,
  )) {
    const actual = (difficultyCounts[difficulty] ?? 0) / total;
    if (Math.abs(actual - expected) > 0.08) {
      warnings.push(
        `difficulty ${difficulty}: ${(actual * 100).toFixed(1)}% vs ${(expected * 100).toFixed(1)}%`,
      );
    }
  }
  const byTarget = distribution(core, "target");
  const values = Object.values(byTarget);
  if (values.length && Math.max(...values) - Math.min(...values) > 1) {
    warnings.push("target distribution differs by more than one record");
  }
  return warnings;
}

function reviewRow(record, issues, contentCollision) {
  return {
    id: record.id,
    query: record.query,
    language: record.language,
    difficulty: record.difficulty,
    partition: record.partition,
    challenge_type: record.challenge_type,
    source_seed_id: record.source_seed_id,
    semantic_cluster_id: record.semantic_cluster_id,
    transformation_types: record.transformation_types,
    ontology: record.ontology,
    target_mode: record.gold.target_mode,
    targets: record.gold.targets,
    acceptable_target_sets: record.gold.acceptable_target_sets,
    exploration: record.gold.exploration ?? null,
    validation_status: record.validation.status,
    deterministic_issues: issues,
    catalog_collision: contentCollision ?? null,
    reviewer_decision: "",
    reviewer_notes: "",
  };
}

function renderReviewMarkdown(rows, summary) {
  const lines = [
    "# VIR v2 manual review queue",
    "",
    `Generated records requiring review: **${rows.length}**.`,
    "",
    `Status counts: ${Object.entries(summary.status_counts)
      .map(([key, value]) => `${key}=${value}`)
      .join(", ")}.`,
    "",
    "Auto-accepted means deterministic checks passed; it does not mean a human approved the label.",
    "",
    "| ID | Query | Partition | Mode | Proposed target(s) | Reason | Decision |",
    "|---|---|---|---|---|---|---|",
  ];
  for (const row of rows.slice(0, 500)) {
    const query = row.query.replace(/\|/g, "\\|");
    const reason = [
      ...(row.deterministic_issues ?? []),
      row.catalog_collision?.warning
        ? `catalog collision: ${row.catalog_collision.top_competing_templates[0]?.template_id}`
        : "",
    ]
      .filter(Boolean)
      .join("; ")
      .replace(/\|/g, "\\|");
    lines.push(
      `| ${row.id} | ${query} | ${row.partition} | ${row.target_mode} | ${row.targets.join("<br>") || "ABSTAIN"} | ${reason || "human capability check required"} | ☐ |`,
    );
  }
  return `${lines.join("\n")}\n`;
}

function renderReviewHtml(rows, summary) {
  const escape = (value) =>
    String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  const body = rows
    .map(
      (row) => `<tr>
<td><input type="checkbox"></td>
<td><code>${escape(row.id)}</code></td>
<td>${escape(row.query)}</td>
<td>${escape(row.language)} / ${escape(row.difficulty)}</td>
<td>${escape(row.partition)}${row.challenge_type ? ` / ${escape(row.challenge_type)}` : ""}</td>
<td>${escape(row.targets.join(", ") || "ABSTAIN")}</td>
<td>${escape(row.deterministic_issues.join("; ") || "Manual capability check")}</td>
</tr>`,
    )
    .join("\n");
  return `<!doctype html>
<html lang="en"><meta charset="utf-8"><title>VIR v2 review queue</title>
<style>body{font:14px system-ui;margin:24px;color:#17202a}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd1d1;padding:7px;vertical-align:top}th{position:sticky;top:0;background:#f4f6f7}tr:nth-child(even){background:#fafafa}code{font-size:12px}</style>
<h1>VIR v2 review queue</h1>
<p>${rows.length} records require human review. Auto-accepted records are not human-approved Gold.</p>
<table><thead><tr><th>Done</th><th>ID</th><th>Query</th><th>Language / difficulty</th><th>Partition</th><th>Proposed target</th><th>Reason</th></tr></thead><tbody>${body}</tbody></table>
</html>`;
}

function validateDataset({
  records,
  registry,
  capabilityKb,
  gapAudit = null,
  config,
  writeOutputs = true,
}) {
  const similarity = new CharacterNgramSimilarity();
  const recordIssues = new Map(records.map((record) => [record.id, []]));
  const schemaErrors = [];
  const ids = new Map();
  const exactQueries = new Map();
  const normalizedQueries = new Map();
  const leakedTemplateIds = [];
  const languageWarnings = [];
  const contradictoryAnnotations = [];
  const explorationTaxonomyConflicts = [];

  for (const record of records) {
    const schema = validateRecord(record, registry);
    if (!schema.valid) {
      schemaErrors.push({ id: record.id, errors: schema.errors });
      recordIssues.get(record.id).push(...schema.errors);
    }
    ids.set(record.id, [...(ids.get(record.id) ?? []), record.id]);
    exactQueries.set(record.query, [
      ...(exactQueries.get(record.query) ?? []),
      record.id,
    ]);
    const normalized = normalizeQuery(record.query);
    normalizedQueries.set(normalized, [
      ...(normalizedQueries.get(normalized) ?? []),
      record.id,
    ]);
    if (/template-[a-z0-9-]+/i.test(record.query)) {
      leakedTemplateIds.push(record.id);
      recordIssues.get(record.id).push("query leaks internal template ID");
    }
    const languageWarning = languageConsistency(record);
    if (languageWarning) {
      languageWarnings.push({ id: record.id, warning: languageWarning });
      recordIssues.get(record.id).push(languageWarning);
    }
    if (record.gold?.target_mode === "exploration") {
      for (const target of record.gold.targets ?? []) {
        const taxonomy = registry.get(target)?.style_taxonomy;
        const expectedStyle = taxonomy?.primary_visual_style_family;
        const expectedLayout = taxonomy?.primary_layout_family;
        const actualStyle =
          record.gold.exploration?.target_style_families?.[target];
        const actualLayout =
          record.gold.exploration?.target_layout_families?.[target];
        if (
          actualStyle !== expectedStyle ||
          actualLayout !== expectedLayout
        ) {
          const conflict = {
            id: record.id,
            target,
            expected_style: expectedStyle ?? null,
            actual_style: actualStyle ?? null,
            expected_layout: expectedLayout ?? null,
            actual_layout: actualLayout ?? null,
          };
          explorationTaxonomyConflicts.push(conflict);
          recordIssues
            .get(record.id)
            .push(`exploration taxonomy mismatch for ${target}`);
        }
      }
    }
  }

  const duplicateIds = [...ids.entries()]
    .filter(([, values]) => values.length > 1)
    .map(([id]) => id);
  const exactDuplicates = [...exactQueries.entries()]
    .filter(([, values]) => values.length > 1)
    .map(([query, recordIds]) => ({ query, record_ids: recordIds }));
  const normalizedDuplicates = [...normalizedQueries.entries()]
    .filter(([, values]) => values.length > 1)
    .map(([query, recordIds]) => ({ query, record_ids: recordIds }));
  for (const duplicate of exactDuplicates) {
    for (const id of duplicate.record_ids) {
      recordIssues.get(id).push("exact duplicate query");
    }
  }
  for (const duplicate of normalizedDuplicates) {
    const duplicateRecords = duplicate.record_ids.map((id) =>
      records.find((record) => record.id === id),
    );
    if (new Set(duplicateRecords.map((record) => record.query)).size > 1) {
      for (const id of duplicate.record_ids) {
        recordIssues.get(id).push("normalized duplicate query");
      }
    }
    const signatures = new Set(
      duplicateRecords.map(goldSignature),
    );
    if (signatures.size > 1) {
      contradictoryAnnotations.push(duplicate);
      for (const id of duplicate.record_ids) {
        recordIssues.get(id).push("contradictory annotation for normalized query");
      }
    }
  }

  const nearDuplicates = findNearDuplicates(
    records,
    config.validation.near_duplicate_threshold,
    similarity,
  );
  for (const duplicate of nearDuplicates) {
    if (!duplicate.same_semantic_cluster) {
      recordIssues
        .get(duplicate.left_id)
        .push(`near duplicate outside cluster: ${duplicate.right_id}`);
      recordIssues
        .get(duplicate.right_id)
        .push(`near duplicate outside cluster: ${duplicate.left_id}`);
    }
  }

  const gapCollisions = contentGapCollisions(
    records,
    capabilityKb,
    similarity,
    config.validation.content_gap_collision_threshold,
  );
  const gapById = new Map(
    gapCollisions.map((collision) => [collision.record_id, collision]),
  );
  const auditedGapSubjects = new Set(
    (gapAudit?.capability_checks ?? []).map((check) => check.subject_event),
  );
  const unauditedGapRecords = records
    .filter(
      (record) =>
        record.gold.target_mode === "none" &&
        gapAudit &&
        !auditedGapSubjects.has(record.ontology.subject_event),
    )
    .map((record) => record.id);
  for (const id of unauditedGapRecords) {
    recordIssues
      .get(id)
      .push("content-gap subject missing from full-catalog audit");
  }
  for (const collision of gapCollisions) {
    if (collision.warning) {
      recordIssues
        .get(collision.record_id)
        .push("content-gap query has catalog capability similarity");
    }
  }

  for (const record of records) {
    const issues = recordIssues.get(record.id);
    const fatal =
      schemaErrors.some((error) => error.id === record.id) ||
      duplicateIds.includes(record.id) ||
      issues.some((issue) =>
        /leaks internal|exact duplicate|normalized duplicate|contradictory|exploration taxonomy mismatch/.test(
          issue,
        ),
      );
    if (fatal) {
      record.validation.status = "rejected";
      record.validation.target_consistency = false;
    } else if (
      record.partition === "core" &&
      record.difficulty !== "high" &&
      !issues.length &&
      config.validation.auto_accept_clean_core
    ) {
      record.validation.status = "auto_accepted";
      record.validation.target_consistency = true;
    } else {
      record.validation.status = "needs_review";
      record.validation.target_consistency = null;
    }
    record.validation.rationale = issues.length
      ? issues.join("; ")
      : record.validation.status === "auto_accepted"
        ? "Passed deterministic schema, capability-ID, language, and collision checks."
        : "Requires independent human capability review.";
  }

  const statuses = {};
  for (const record of records) {
    statuses[record.validation.status] =
      (statuses[record.validation.status] ?? 0) + 1;
  }
  const core = records.filter((record) => record.partition === "core");
  const summary = {
    benchmark_version: "vir-v2",
    valid:
      schemaErrors.length === 0 &&
      duplicateIds.length === 0 &&
      exactDuplicates.length === 0 &&
      normalizedDuplicates.length === 0 &&
      contradictoryAnnotations.length === 0 &&
      explorationTaxonomyConflicts.length === 0 &&
      leakedTemplateIds.length === 0,
    record_count: records.length,
    status_counts: statuses,
    schema_errors: schemaErrors,
    duplicate_ids: duplicateIds,
    exact_duplicates: exactDuplicates,
    normalized_duplicates: normalizedDuplicates,
    near_duplicates: nearDuplicates,
    language_warnings: languageWarnings,
    leaked_template_ids: leakedTemplateIds,
    contradictory_annotations: contradictoryAnnotations,
    exploration_taxonomy_conflicts: explorationTaxonomyConflicts,
    content_gap_collisions: gapCollisions.filter(
      (collision) => collision.warning,
    ),
    full_catalog_gap_audit: gapAudit
      ? {
          audit_version: gapAudit.audit_version,
          source_catalog_sha256:
            gapAudit.source_evidence?.catalog_sha256 ?? null,
          source_template_count:
            gapAudit.source_evidence?.template_count ?? null,
          audited_subject_count: auditedGapSubjects.size,
          unaudited_record_ids: unauditedGapRecords,
        }
      : null,
    balance_warnings: balanceWarnings(core, config),
    distributions: {
      partition: distribution(records, "partition"),
      target: distribution(records, "target"),
      language: distribution(records, "language"),
      difficulty: distribution(records, "difficulty"),
      core_target: distribution(core, "target"),
      core_language: distribution(core, "language"),
      core_difficulty: distribution(core, "difficulty"),
      transformation_type: distribution(records, "transformation_type"),
      validation_status: statuses,
    },
    similarity_layer: similarity.name,
    configuration_hash: hashObject(config.validation),
  };
  const reviewRows = records
    .filter((record) => record.validation.status === "needs_review")
    .map((record) =>
      reviewRow(record, recordIssues.get(record.id), gapById.get(record.id)),
    );

  if (writeOutputs) {
    const groups = {
      core: records.filter((record) => record.partition === "core"),
      content_gap: records.filter(
        (record) => record.partition === "content_gap",
      ),
      challenge: records.filter((record) => record.partition === "challenge"),
      exploration: records.filter(
        (record) => record.partition === "exploration",
      ),
    };
    for (const [name, rows] of Object.entries(groups)) {
      writeJsonl(path.join(config.paths.validated_dir, `${name}.jsonl`), rows);
    }
    writeJson(
      path.join(config.paths.manifest_dir, "dataset_validation.json"),
      summary,
    );
    writeJsonl(
      path.join(config.paths.review_dir, "review_queue.jsonl"),
      reviewRows,
    );
    writeCsv(
      path.join(config.paths.review_dir, "review_queue.csv"),
      [
        "id",
        "query",
        "language",
        "difficulty",
        "partition",
        "challenge_type",
        "source_seed_id",
        "semantic_cluster_id",
        "transformation_types",
        "ontology",
        "target_mode",
        "targets",
        "acceptable_target_sets",
        "exploration",
        "validation_status",
        "deterministic_issues",
        "catalog_collision",
        "reviewer_decision",
        "reviewer_notes",
      ],
      reviewRows,
    );
    const markdown = renderReviewMarkdown(reviewRows, summary);
    const html = renderReviewHtml(reviewRows, summary);
    const reviewDir = resolveRoot(config.paths.review_dir);
    fs.mkdirSync(reviewDir, { recursive: true });
    fs.writeFileSync(path.join(reviewDir, "review_report.md"), markdown);
    fs.writeFileSync(path.join(reviewDir, "review_report.html"), html);
  }
  return { records, summary, reviewRows };
}

async function validateWithLlm({
  record,
  registry,
  config,
  model = config.expansion.model,
}) {
  const promptPath = resolveRoot("benchmarks/vir_v2/prompts/query_validator.md");
  const prompt = fs.readFileSync(promptPath, "utf8");
  const payload = `${prompt}\n\nRegistry:\n${JSON.stringify(
    registry.document,
  )}\n\nRecord:\n${JSON.stringify(record)}`;
  const promptHash = sha256(payload);
  const cachePath = resolveRoot(
    path.join(config.paths.cache_dir, `validator-${record.id}.json`),
  );
  if (fs.existsSync(cachePath)) {
    const cached = JSON.parse(fs.readFileSync(cachePath, "utf8"));
    if (cached.prompt_hash === promptHash) return cached;
  }
  if (!process.env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY is required for optional LLM validation");
  }
  const OpenAI = require("openai");
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  let raw = "";
  let parsed;
  let attempts = 0;
  let lastError;
  for (
    attempts = 1;
    attempts <= config.expansion.max_retries;
    attempts += 1
  ) {
    try {
      const response = await client.chat.completions.create({
        model,
        temperature: 0,
        seed: config.random_seed,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: payload },
          { role: "user", content: "Validate this record." },
        ],
      });
      raw = response.choices?.[0]?.message?.content ?? "";
      parsed = JSON.parse(raw);
      break;
    } catch (error) {
      lastError = error;
    }
  }
  if (!parsed) throw lastError;
  const output = {
    model,
    prompt_version: config.validation.validator_prompt_version,
    prompt_hash: promptHash,
    raw_output: raw,
    parsed,
    attempts,
  };
  writeJson(cachePath, output);
  return output;
}

module.exports = {
  balanceWarnings,
  contentGapCollisions,
  distribution,
  findNearDuplicates,
  languageConsistency,
  renderReviewHtml,
  renderReviewMarkdown,
  validateDataset,
  validateWithLlm,
  writeCsv,
};
