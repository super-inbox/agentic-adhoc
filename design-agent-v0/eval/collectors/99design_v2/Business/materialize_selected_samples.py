#!/usr/bin/env python3
"""Materialize the manually selected Business reference samples."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parent
SELECTION_PATH = ROOT / "selected-contests-v0.1.json"
PARENT_MATERIALIZER = (
    ROOT.parent / "Travel Hotel" / "materialize_selected_samples.py"
)
COLLECTION_CATEGORY = "Business & Advertising"


def load_parent_materializer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "travel_hotel_materializer", PARENT_MATERIALIZER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {PARENT_MATERIALIZER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CAPTURED_AT = "2026-09-01"
    return module


def safe_component(value: str, label: str) -> str:
    if not value or "/" in value or "\\" in value:
        raise ValueError(f"Unsafe {label}: {value!r}")
    return value


def main() -> None:
    base = load_parent_materializer()
    seeds = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    if len(seeds) != 6:
        raise ValueError(f"Expected 6 selected contests, found {len(seeds)}")

    seen_ids: set[str] = set()
    seen_paths: set[tuple[str, str]] = set()
    summary: list[dict[str, object]] = []
    for seed in seeds:
        subcategory = safe_component(
            seed["subcategory_folder"], "subcategory folder"
        )
        folder_name = safe_component(seed["folder_name"], "contest folder")
        key = (subcategory, folder_name)
        if key in seen_paths:
            raise ValueError(f"Duplicate folder path: {key!r}")
        seen_paths.add(key)

        if seed["contest"].get("winner_count") != 1:
            raise ValueError(f"Expected one Winner: {folder_name!r}")
        if len(seed.get("candidates", [])) != 4:
            raise ValueError(f"Expected four public candidates: {folder_name!r}")

        cid = base.contest_id(seed["source"]["url"])
        if cid in seen_ids:
            raise ValueError(f"Duplicate contest id: {cid}")
        seen_ids.add(cid)

        folder = ROOT / subcategory / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        winner_seed = seed["selection"]["winners"][0]
        assets = [base.make_asset(folder, winner_seed, "winner", True)]
        assets.extend(
            base.make_asset(
                folder, candidate, "non_winner_public_preview", False
            )
            for candidate in seed["candidates"]
        )

        record = base.make_record(seed, assets)
        record["collection_hierarchy"] = {
            "industry": "Travel & Hotel",
            "category": COLLECTION_CATEGORY,
            "subcategory": subcategory,
        }
        record_path = folder / f"contest-{cid}.json"
        record_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (folder / "README.md").write_text(
            base.make_readme(record), encoding="utf-8"
        )
        summary.append(
            {
                "subcategory": subcategory,
                "folder": folder_name,
                "contest_id": cid,
                "asset_count": len(assets),
                "record": str(record_path.relative_to(ROOT)),
            }
        )

    (ROOT / "materialization-summary-v0.1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
