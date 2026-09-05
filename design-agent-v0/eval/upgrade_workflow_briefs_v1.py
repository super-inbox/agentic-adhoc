#!/usr/bin/env python3
"""Add the missing intent axis to the frozen 11 workflow briefs.

This is deliberately a mechanical metadata upgrade. It does not change the
case-study-derived step sequence or pretend that the source supplies a full
execution contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_PATH = HERE / "briefs.jsonl"

SECONDARY_BY_ID = {
    "BRF-BRAND-01": [],
    "BRF-BRAND-02": [],
    "BRF-BRAND-03": ["adapt"],
    "BRF-ECOM-01": ["adapt"],
    "BRF-ECOM-03": ["adapt"],
    "BRF-EDU-01": ["adapt"],
    "BRF-EDU-02": ["adapt"],
    "BRF-MERCH-01": ["adapt", "export"],
    "BRF-MERCH-02": ["adapt", "export"],
    "BRF-PACK-01": ["export"],
    "BRF-PACK-02": ["export"],
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()

    rows = read_jsonl(args.path)
    ids = {row["id"] for row in rows}
    if len(rows) != 11 or ids != set(SECONDARY_BY_ID):
        raise SystemExit(f"refusing unexpected workflow source: rows={len(rows)} ids={sorted(ids)}")

    for row in rows:
        row["primary_intent"] = "generate"
        row["secondary_intents"] = SECONDARY_BY_ID[row["id"]]

    temporary = args.path.with_suffix(args.path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(args.path)
    print(f"updated {len(rows)} workflow briefs: primary_intent=11/11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
