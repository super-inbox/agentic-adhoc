"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "../..");

function resolveRoot(value) {
  return path.isAbsolute(value) ? value : path.resolve(ROOT, value);
}

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(resolveRoot(filePath), "utf8"));
}

function loadConfig(filePath) {
  // JSON is a strict subset of YAML 1.2. Keeping the committed default in this
  // subset avoids adding a parser dependency to the standalone benchmark.
  const absolute = resolveRoot(filePath);
  const text = fs.readFileSync(absolute, "utf8");
  try {
    return { ...JSON.parse(text), _config_path: absolute };
  } catch (error) {
    throw new Error(
      `Config ${absolute} must use JSON-compatible YAML: ${error.message}`,
    );
  }
}

function ensureDir(dirPath) {
  fs.mkdirSync(resolveRoot(dirPath), { recursive: true });
}

function writeJson(filePath, value) {
  const absolute = resolveRoot(filePath);
  fs.mkdirSync(path.dirname(absolute), { recursive: true });
  fs.writeFileSync(absolute, `${JSON.stringify(value, null, 2)}\n`);
}

function readJsonl(filePath) {
  const absolute = resolveRoot(filePath);
  if (!fs.existsSync(absolute)) return [];
  return fs
    .readFileSync(absolute, "utf8")
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line, index) => {
      try {
        return JSON.parse(line);
      } catch (error) {
        throw new Error(
          `Invalid JSONL in ${absolute}:${index + 1}: ${error.message}`,
        );
      }
    });
}

function writeJsonl(filePath, rows) {
  const absolute = resolveRoot(filePath);
  fs.mkdirSync(path.dirname(absolute), { recursive: true });
  const body = rows.map((row) => JSON.stringify(row)).join("\n");
  fs.writeFileSync(absolute, body ? `${body}\n` : "");
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function sha256File(filePath) {
  return sha256(fs.readFileSync(resolveRoot(filePath)));
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function hashObject(value) {
  return sha256(stableStringify(value));
}

function normalizeQuery(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[’‘]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function slug(value) {
  const cleaned = normalizeQuery(value)
    .replace(/[^\x00-\x7F]+/g, "")
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "");
  return cleaned || sha256(String(value)).slice(0, 10);
}

function mulberry32(seed) {
  let value = seed >>> 0;
  return function random() {
    value += 0x6d2b79f5;
    let t = value;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle(values, seed) {
  const output = [...values];
  const random = mulberry32(seed);
  for (let index = output.length - 1; index > 0; index -= 1) {
    const other = Math.floor(random() * (index + 1));
    [output[index], output[other]] = [output[other], output[index]];
  }
  return output;
}

function quantile(values, q) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return sorted[lower];
  return (
    sorted[lower] +
    (sorted[upper] - sorted[lower]) * (position - lower)
  );
}

function mean(values) {
  return values.length
    ? values.reduce((total, value) => total + value, 0) / values.length
    : null;
}

function nowIso() {
  return new Date().toISOString();
}

module.exports = {
  ROOT,
  ensureDir,
  hashObject,
  loadConfig,
  loadJson,
  mean,
  mulberry32,
  normalizeQuery,
  nowIso,
  quantile,
  readJsonl,
  resolveRoot,
  sha256,
  sha256File,
  shuffle,
  slug,
  stableStringify,
  writeJson,
  writeJsonl,
};
