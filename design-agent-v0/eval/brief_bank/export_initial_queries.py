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
DEFAULT_INPUT = HERE / "briefs.v0.2.jsonl"


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


def project(
    row: dict,
    condition: dict | None = None,
    *,
    episode_source: str | None = None,
) -> dict:
    """Project one episode condition without exposing future feedback turns."""
    if row.get("schema_version") == "0.1":
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
            "episode_source": episode_source or "brief_bank/briefs.v0.1.jsonl",
        }

    conditions = row.get("context_conditions", [])
    if condition is None:
        condition = next(
            (item for item in conditions if item.get("id") == "reference_grounded"),
            conditions[0] if conditions else None,
        )
    if not isinstance(condition, dict):
        raise ValueError(f"{row.get('id')}: workflow row has no context condition")

    include_ids = set(condition["include_input_ids"])
    reference_by_input = {
        item["input_id"]: item for item in row.get("reference_contract", [])
    }
    included_inputs = [
        item
        for item in row["inputs"]
        if item["id"] in include_ids and item.get("availability") == "provided"
    ]
    assets = [
        {
            "input_id": item["id"],
            "asset_id": item["asset_id"],
            "role": item["role"],
            "reference_role": reference_by_input[item["id"]]["reference_role"],
            "identity_policy": reference_by_input[item["id"]]["identity_policy"],
        }
        for item in included_inputs
        if item.get("asset_id")
    ]
    input_context = []
    for item in included_inputs:
        projected = {"id": item["id"], "kind": item["kind"], "role": item["role"]}
        if item.get("asset_id"):
            projected["asset_id"] = item["asset_id"]
        else:
            projected["content"] = item["content"]
        input_context.append(projected)

    condition_id = condition["id"]
    return {
        "id": f"{row['id']}@{condition_id}",
        "base_brief_id": row["id"],
        "context_condition": condition_id,
        "query": condition.get("query_override", row["initial_query"]),
        "language": row["language"],
        "layer": f"l3_l4_brief_initial_query_v{row['schema_version']}",
        "capability_level": row["level"],
        "category": row["category"],
        "primary_intent": row["primary_intent"],
        "secondary_intents": row["secondary_intents"],
        "capability_tags": row["capability_tags"],
        "has_reference": bool(assets),
        "input_assets": assets,
        "input_context": input_context,
        "preference_memory": (
            row["preference_memory"] if condition["include_preference_memory"] else None
        ),
        "requires_feedback": bool(row["feedback"]),
        "feedback_turns": len(row["feedback"]),
        "human_checkpoint_count": len(row["human_checkpoints"]),
        "required_structured_artifacts": [
            item["name"] for item in row["structured_artifacts"] if item["required"]
        ],
        "episode_source": episode_source or "brief_bank/briefs.v0.2.jsonl",
    }


def project_rows(rows: list[dict], *, episode_source: str | None = None) -> list[dict]:
    projected: list[dict] = []
    for row in rows:
        if row.get("schema_version") in {"0.2", "0.3"}:
            projected.extend(
                project(row, condition, episode_source=episode_source)
                for condition in row["context_conditions"]
            )
        else:
            projected.append(project(row, episode_source=episode_source))
    return projected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="write JSONL here; stdout when omitted")
    args = parser.parse_args()

    source = f"brief_bank/{args.input.name}"
    rows = project_rows(load_rows(args.input), episode_source=source)
    rendered = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {len(rows)} query rows to {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
