"use strict";

const { normalizeQuery } = require("./common.cjs");

class CharacterNgramSimilarity {
  constructor({ n = 3 } = {}) {
    this.n = n;
    this.name = `character-${n}gram-jaccard`;
  }

  features(value) {
    const normalized = normalizeQuery(value).replace(/\s+/g, " ");
    if (!normalized) return new Set();
    if (normalized.length <= this.n) return new Set([normalized]);
    const features = new Set();
    for (let index = 0; index <= normalized.length - this.n; index += 1) {
      features.add(normalized.slice(index, index + this.n));
    }
    for (const token of normalized.split(" ")) {
      if (token) features.add(`w:${token}`);
    }
    return features;
  }

  similarity(left, right) {
    const a = this.features(left);
    const b = this.features(right);
    if (!a.size && !b.size) return 1;
    if (!a.size || !b.size) return 0;
    let intersection = 0;
    for (const value of a) if (b.has(value)) intersection += 1;
    return intersection / (a.size + b.size - intersection);
  }

  closest(query, entries, text = (entry) => entry) {
    return entries
      .map((entry) => ({
        entry,
        similarity: this.similarity(query, text(entry)),
      }))
      .sort((a, b) => b.similarity - a.similarity);
  }
}

module.exports = { CharacterNgramSimilarity };
