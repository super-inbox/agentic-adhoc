#!/usr/bin/env python3
"""Validate safety and consistency invariants for a metadata-only index."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List
from urllib.parse import urlsplit


REQUIRED_FIELDS = {
    "schema_version",
    "record_id",
    "source",
    "source_url",
    "contest_id",
    "retrieved_at",
    "discovery_method",
    "evidence_status",
    "title",
    "design_category",
    "industry",
    "brief_summary",
    "entry_count",
    "designer_count",
    "winner",
    "rights",
}


def load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: record must be an object")
            value["_line_number"] = line_number
            yield value


def validate(path: Path) -> Dict[str, Any]:
    errors: List[str] = []
    ids = set()
    urls = set()
    categories: Counter[str] = Counter()
    winner_statuses: Counter[str] = Counter()
    count = 0
    for record in load_jsonl(path):
        count += 1
        line = record.pop("_line_number")
        missing = sorted(REQUIRED_FIELDS - record.keys())
        if missing:
            errors.append(f"line {line}: missing fields: {', '.join(missing)}")
        record_id = record.get("record_id")
        source_url = record.get("source_url")
        if record_id in ids:
            errors.append(f"line {line}: duplicate record_id {record_id}")
        if source_url in urls:
            errors.append(f"line {line}: duplicate source_url {source_url}")
        ids.add(record_id)
        urls.add(source_url)

        parsed = urlsplit(source_url or "")
        if parsed.scheme != "https" or parsed.netloc != "99designs.hk":
            errors.append(f"line {line}: source URL must be an https://99designs.hk URL")
        if "/contests/" not in parsed.path:
            errors.append(f"line {line}: source URL is not a contest detail URL")
        if record.get("contest_id") not in parsed.path.rsplit("-", 1)[-1]:
            errors.append(f"line {line}: contest_id does not match source URL")
        if record.get("industry") != "Art & Design":
            errors.append(f"line {line}: unexpected industry {record.get('industry')!r}")
        if record.get("discovery_method") != "search_engine_index":
            errors.append(f"line {line}: direct crawl data is not allowed in this pilot")

        winner = record.get("winner") or {}
        rights = record.get("rights") or {}
        if winner.get("image_url") is not None:
            errors.append(f"line {line}: winner image URL must not be stored")
        expected_false = (
            "full_brief_stored",
            "winner_image_url_stored",
            "winner_pixels_stored",
            "training_allowed",
            "redistribution_allowed",
        )
        if rights.get("status") != "metadata_only":
            errors.append(f"line {line}: rights.status must be metadata_only")
        for key in expected_false:
            if rights.get(key) is not False:
                errors.append(f"line {line}: rights.{key} must be false")

        categories[str(record.get("design_category"))] += 1
        winner_statuses[str(winner.get("status"))] += 1

    if count == 0:
        errors.append("dataset is empty")
    return {
        "path": str(path),
        "records": count,
        "unique_record_ids": len(ids),
        "unique_source_urls": len(urls),
        "categories": dict(sorted(categories.items())),
        "winner_statuses": dict(sorted(winner_statuses.items())),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("search-index-pilot-v0.1.jsonl"))
    args = parser.parse_args()
    try:
        result = validate(args.path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
