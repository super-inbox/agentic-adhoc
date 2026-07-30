"use strict";

const fs = require("fs");
const {
  hashObject,
  loadJson,
  resolveRoot,
  writeJson,
} = require("./common.cjs");
const { CharacterNgramSimilarity } = require("./similarity.cjs");

const REQUIRED_FIELDS = [
  "canonical_id",
  "aliases",
  "description",
  "supported_subject_event_types",
  "supported_information_structures",
  "expected_visual_layout_structure",
  "typical_user_goals",
  "required_inputs",
  "optional_inputs",
  "known_exclusions",
  "positive_examples",
  "negative_examples",
  "neighboring_templates",
  "evidence_paths",
  "ontology",
];

class CapabilityRegistry {
  constructor(document, catalog = []) {
    this.document = document;
    this.templates = document.templates ?? [];
    this.catalog = catalog;
    this.byCanonical = new Map();
    this.aliasToCanonical = new Map();
    for (const entry of this.templates) {
      this.byCanonical.set(entry.canonical_id, entry);
      this.aliasToCanonical.set(entry.canonical_id, entry.canonical_id);
      for (const alias of entry.aliases ?? []) {
        if (
          this.aliasToCanonical.has(alias) &&
          this.aliasToCanonical.get(alias) !== entry.canonical_id
        ) {
          throw new Error(`Registry alias collision: ${alias}`);
        }
        this.aliasToCanonical.set(alias, entry.canonical_id);
      }
    }
  }

  canonicalize(templateId) {
    return this.aliasToCanonical.get(templateId) ?? null;
  }

  get(templateId) {
    const canonical = this.canonicalize(templateId);
    return canonical ? this.byCanonical.get(canonical) : null;
  }

  has(templateId) {
    return this.canonicalize(templateId) !== null;
  }

  capabilityText(entry) {
    return [
      entry.description,
      ...(entry.supported_subject_event_types ?? []),
      ...(entry.supported_information_structures ?? []),
      ...(entry.expected_visual_layout_structure ?? []),
      ...(entry.typical_user_goals ?? []),
      ...(entry.positive_examples ?? []),
      ...(entry.generation_profile?.concepts ?? []).flatMap((concept) => [
        concept.en,
        concept.zh,
      ]),
      ...(entry.generation_profile?.artifacts_en ?? []),
      ...(entry.generation_profile?.artifacts_zh ?? []),
    ]
      .filter(Boolean)
      .join(" ");
  }

  boundaryPairs() {
    const pairs = new Map();
    for (const entry of this.templates) {
      for (const neighbor of entry.neighboring_templates ?? []) {
        const canonical = this.canonicalize(neighbor);
        if (!canonical || canonical === entry.canonical_id) continue;
        const ids = [entry.canonical_id, canonical].sort();
        pairs.set(ids.join("::"), ids);
      }
    }
    return [...pairs.values()];
  }

  semanticCollisions({ threshold = 0.24 } = {}) {
    const similarity = new CharacterNgramSimilarity();
    const rows = [];
    for (let left = 0; left < this.templates.length; left += 1) {
      for (let right = left + 1; right < this.templates.length; right += 1) {
        const a = this.templates[left];
        const b = this.templates[right];
        const score = similarity.similarity(
          this.capabilityText(a),
          this.capabilityText(b),
        );
        if (score >= threshold) {
          rows.push({
            left: a.canonical_id,
            right: b.canonical_id,
            similarity: Number(score.toFixed(4)),
            declared_neighbors:
              (a.neighboring_templates ?? []).includes(b.canonical_id) ||
              (b.neighboring_templates ?? []).includes(a.canonical_id),
          });
        }
      }
    }
    return rows.sort((a, b) => b.similarity - a.similarity);
  }
}

function loadRegistry(registryPath, catalogPath) {
  const document = loadJson(registryPath);
  const catalog = catalogPath ? loadJson(catalogPath) : [];
  return new CapabilityRegistry(document, catalog);
}

function validateRegistry(registry) {
  const errors = [];
  const warnings = [];
  const catalogById = new Map(
    registry.catalog.map((template) => [template.id, template]),
  );
  for (const entry of registry.templates) {
    for (const field of REQUIRED_FIELDS) {
      if (!(field in entry)) {
        errors.push(`${entry.canonical_id ?? "<missing-id>"}: missing ${field}`);
      }
    }
    if (!catalogById.has(entry.canonical_id)) {
      errors.push(`${entry.canonical_id}: not present in frozen catalog`);
    } else if (catalogById.get(entry.canonical_id).allow_generation !== true) {
      warnings.push(`${entry.canonical_id}: catalog does not set allow_generation`);
    }
    for (const alias of entry.aliases ?? []) {
      const catalogTarget = catalogById.get(entry.canonical_id);
      if (catalogTarget?.legacy_id !== alias) {
        warnings.push(
          `${entry.canonical_id}: alias ${alias} is not catalog legacy_id`,
        );
      }
    }
    for (const evidencePath of entry.evidence_paths ?? []) {
      const filePath = evidencePath.split("#", 1)[0];
      if (!fs.existsSync(resolveRoot(filePath))) {
        errors.push(`${entry.canonical_id}: missing evidence file ${filePath}`);
      }
    }
    if (!entry.uncertainty) {
      warnings.push(`${entry.canonical_id}: no uncertainty note`);
    }
  }
  return {
    valid: errors.length === 0,
    errors,
    warnings,
    template_count: registry.templates.length,
    alias_count: registry.aliasToCanonical.size - registry.templates.length,
    registry_hash: hashObject(registry.document),
    semantic_collisions: registry.semanticCollisions(),
  };
}

function buildRegistry(config, outputPath) {
  const registry = loadRegistry(config.paths.registry, config.paths.catalog);
  const validation = validateRegistry(registry);
  if (!validation.valid) {
    throw new Error(`Invalid registry:\n${validation.errors.join("\n")}`);
  }
  if (outputPath) writeJson(outputPath, registry.document);
  return { registry, validation };
}

module.exports = {
  CapabilityRegistry,
  buildRegistry,
  loadRegistry,
  validateRegistry,
};
