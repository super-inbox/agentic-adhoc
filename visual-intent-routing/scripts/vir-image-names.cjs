"use strict";

function truncateUtf8(value, maxBytes) {
  let output = "";
  let bytes = 0;
  for (const character of String(value)) {
    const size = Buffer.byteLength(character, "utf8");
    if (bytes + size > maxBytes) break;
    output += character;
    bytes += size;
  }
  return output;
}

function querySlug(query, maxBytes = 72) {
  const normalized = String(query ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return truncateUtf8(normalized || "query", maxBytes).replace(/-+$/g, "") || "query";
}

function identifierSlug(queryId) {
  return String(queryId ?? "record")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "") || "record";
}

function directionSlug(direction) {
  const numeric = Number(direction);
  if (Number.isInteger(numeric) && numeric > 0) {
    return String(numeric).padStart(2, "0");
  }
  const fallback = identifierSlug(direction);
  if (fallback === "record") throw new Error(`Invalid image direction: ${direction}`);
  return fallback;
}

function queryImageStem(query, queryId, direction) {
  return `${querySlug(query)}--${identifierSlug(queryId)}--d${directionSlug(direction)}`;
}

function queryImageName(query, queryId, direction, extension = "jpeg") {
  const normalizedExtension = String(extension).toLowerCase().replace(/^\.+/, "");
  if (!/^(?:jpe?g|png|webp)$/.test(normalizedExtension)) {
    throw new Error(`Unsupported image extension: ${extension}`);
  }
  return `${queryImageStem(query, queryId, direction)}.${normalizedExtension}`;
}

function queryFolderNames(records, maxBytes = 120) {
  const baseNames = records.map((record) => ({
    id: record.id,
    base: querySlug(record.query, maxBytes),
  }));
  const counts = new Map();
  for (const item of baseNames) {
    const key = item.base.normalize("NFKC").toLowerCase();
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return new Map(baseNames.map((item) => {
    const key = item.base.normalize("NFKC").toLowerCase();
    const name = counts.get(key) === 1
      ? item.base
      : `${item.base}--${identifierSlug(item.id)}`;
    return [item.id, name];
  }));
}

function systemImageName(system, direction, extension) {
  if (!new Set(["gpt-direct", "curify-gemini"]).has(system)) {
    throw new Error(`Unsupported image system: ${system}`);
  }
  const normalizedExtension = String(extension).toLowerCase().replace(/^\.+/, "");
  if (!/^(?:jpe?g|png|webp)$/.test(normalizedExtension)) {
    throw new Error(`Unsupported image extension: ${extension}`);
  }
  return `${system}--d${directionSlug(direction)}.${normalizedExtension}`;
}

module.exports = {
  queryImageName,
  queryImageStem,
  queryFolderNames,
  querySlug,
  systemImageName,
  truncateUtf8,
};
