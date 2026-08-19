#!/usr/bin/env python3
"""Project episode briefs into query-only rows for legacy single-turn adapters.

The projection is useful for routing smoke tests. It does not evaluate L4 state,
feedback handling, checkpoint completion, or final delivery quality.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "briefs.v0.1.jsonl"


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_number}: {exc}") from exc
    return rows


def project(row: dict) -> dict:
    assets = [
        {"asset_id": item["asset_id"], "role": item["role"]}
        for item in row["inputs"]
        if item.get("availability") == "provided" and item.get("asset_id")
    ]
    return {
        "id": row["id"],
        "query": row["initial_query"],
        "language": row["language"],
        "layer": "l3_l4_brief_initial_query",
        "capability_level": row["level"],
        "category": row["category"],
        "primary_intent": row["primary_intent"],
        "secondary_intents": row["secondary_intents"],
        "has_reference": bool(assets),
        "input_assets": assets,
        "requires_feedback": bool(row["feedback"]),
        "episode_source": "brief_bank/briefs.v0.1.jsonl",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="write JSONL here; stdout when omitted")
    args = parser.parse_args()

    rendered = "\n".join(
        json.dumps(project(row), ensure_ascii=False, separators=(",", ":"))
        for row in load_rows(args.input)
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {len(rendered.splitlines())} query rows to {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
