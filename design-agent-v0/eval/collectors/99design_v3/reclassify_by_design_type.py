#!/usr/bin/env python3
"""Reclassify the 99design_v2 snapshot by design type.

The source tree is read-only. Contest records and their referenced preview
images are copied into a two-level ``design type / subtype`` hierarchy while
preserving Brief, selection, asset, evaluation and rights metadata.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parent / "99design_v2"
TAXONOMY_VERSION = "design-type-taxonomy-v0.1"
GENERATED_AT = "2026-09-01"

# Original ``contest.category`` -> (v3 design type, human-readable subtype).
CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "logo_design": ("Brand Design", "Logo Design"),
    "logo_brand_guide": ("Brand Design", "Logo & Brand Guide"),
    "brand_launch_pack": ("Brand Design", "Brand Launch Pack"),
    "logo_brand_identity_pack": (
        "Brand Design",
        "Logo & Brand Identity Pack",
    ),
    "banner_ad": ("Banner Design", "Banner Ad"),
    "web_page_design": ("Web & App Design", "Web Page Design"),
    "app_design": ("Web & App Design", "App Design"),
    "icon_button": ("Web & App Design", "Icon or Button"),
    "product_packaging": (
        "Packaging & Label Design",
        "Product Packaging",
    ),
    "product_label": ("Packaging & Label Design", "Product Label"),
    "postcard_flyer_or_print": (
        "Print & Editorial Design",
        "Postcard, Flyer or Print",
    ),
    "magazine_cover": ("Print & Editorial Design", "Magazine Cover"),
    "other_book_or_magazine": (
        "Print & Editorial Design",
        "Other Book or Magazine",
    ),
    "card_or_invitation": (
        "Print & Editorial Design",
        "Card or Invitation",
    ),
    "illustration_or_graphics": (
        "Art & Illustration Design",
        "Illustration or Graphics",
    ),
    "character_or_mascot": (
        "Art & Illustration Design",
        "Character or Mascot",
    ),
    "other_art_or_illustration": (
        "Art & Illustration Design",
        "Other Art or Illustration",
    ),
    "merchandise": ("Merchandise Design", "Merchandise"),
    "sticker": ("Merchandise Design", "Sticker"),
    "signage": ("Environmental & Signage Design", "Signage"),
    "car_truck_or_van_wrap": (
        "Environmental & Signage Design",
        "Car, Truck or Van Wrap",
    ),
}

DESIGN_TYPE_ORDER = [
    "Brand Design",
    "Banner Design",
    "Web & App Design",
    "Packaging & Label Design",
    "Print & Editorial Design",
    "Art & Illustration Design",
    "Merchandise Design",
    "Environmental & Signage Design",
]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_component(value: str) -> str:
    """Keep a readable title while avoiding path separators/control chars."""

    value = value.replace("/", " - ").replace("\\", " - ")
    value = re.sub(r"[\x00-\x1f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip().rstrip(".")
    if not value or value in {".", ".."}:
        raise ValueError(f"Unsafe empty path component from {value!r}")
    return value


def source_records() -> list[Path]:
    records = sorted(SOURCE_ROOT.rglob("contest-*.json"))
    if not records:
        raise RuntimeError(f"No contest records found under {SOURCE_ROOT}")
    return records


def read_record(path: Path) -> dict[str, Any]:
    record = json.loads(path.read_text(encoding="utf-8"))
    required = ["source", "contest", "assets", "rights"]
    missing = [key for key in required if key not in record]
    if missing:
        raise ValueError(f"{path}: missing fields {missing}")
    return record


def verify_source_asset(record_path: Path, asset: dict[str, Any]) -> Path:
    path = record_path.parent / asset["local_file"]
    payload = path.read_bytes()
    if len(payload) != asset["byte_size"]:
        raise ValueError(f"Byte-size mismatch: {path}")
    if sha256_bytes(payload) != asset["sha256"]:
        raise ValueError(f"SHA256 mismatch: {path}")
    return path


def copy_if_changed(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        source_payload = source.read_bytes()
        if destination.read_bytes() == source_payload:
            return
    shutil.copy2(source, destination)


def contest_readme(
    record: dict[str, Any],
    design_type: str,
    subtype: str,
    source_record: str,
) -> str:
    contest = record["contest"]
    lines = [
        f"# {contest['title']}",
        "",
        f"- design type: {design_type}",
        f"- subtype: {subtype}",
        f"- original category: {contest['category']}",
        f"- contest ID: {record['source']['contest_id']}",
        f"- source page: <{record['source']['url']}>",
        f"- v2 source record: `{source_record}`",
        "",
        "## Assets",
        "",
        "| File | Role | Designer |",
        "|---|---|---|",
    ]
    for asset in record["assets"]:
        designer = str(asset.get("designer") or "unknown").replace("|", "\\|")
        lines.append(
            f"| `{asset['local_file']}` | {asset['role']} | {designer} |"
        )
    lines.extend(
        [
            "",
            "Images are unchanged public preview renditions copied from v2.",
            "The Winner/non-winner meaning and all known gaps remain exactly as",
            "documented in the contest JSON.",
            "",
            "## Rights",
            "",
            "Public visibility is not a training or redistribution license.",
            "See the unchanged `rights` object in the contest JSON.",
            "",
        ]
    )
    return "\n".join(lines)


def build_plan() -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_destinations: set[Path] = set()
    encountered_categories: set[str] = set()

    for record_path in source_records():
        record = read_record(record_path)
        contest = record["contest"]
        category = contest.get("category")
        if category not in CATEGORY_MAP:
            raise ValueError(f"Unmapped category {category!r}: {record_path}")
        encountered_categories.add(category)

        contest_id = str(record["source"]["contest_id"])
        if contest_id in seen_ids:
            raise ValueError(f"Duplicate contest ID {contest_id}")
        seen_ids.add(contest_id)

        design_type, subtype = CATEGORY_MAP[category]
        folder_name = safe_component(str(contest["title"]))
        destination = ROOT / design_type / subtype / folder_name
        if destination in seen_destinations:
            folder_name = safe_component(f"{contest['title']} [{contest_id}]")
            destination = ROOT / design_type / subtype / folder_name
        if destination in seen_destinations:
            raise ValueError(f"Destination collision: {destination}")
        seen_destinations.add(destination)

        source_record = str(record_path.relative_to(SOURCE_ROOT))
        source_record_payload = record_path.read_bytes()
        for asset in record["assets"]:
            verify_source_asset(record_path, asset)

        plan.append(
            {
                "record": record,
                "source_record_path": record_path,
                "source_record": source_record,
                "source_record_sha256": sha256_bytes(source_record_payload),
                "design_type": design_type,
                "subtype": subtype,
                "folder_name": folder_name,
                "destination": destination,
            }
        )

    if encountered_categories != set(CATEGORY_MAP):
        unused = sorted(set(CATEGORY_MAP) - encountered_categories)
        raise ValueError(f"Taxonomy contains unused categories: {unused}")
    return plan


def write_outputs(plan: list[dict[str, Any]]) -> None:
    type_rank = {name: index for index, name in enumerate(DESIGN_TYPE_ORDER)}
    plan.sort(
        key=lambda item: (
            type_rank[item["design_type"]],
            item["subtype"].casefold(),
            item["record"]["contest"]["title"].casefold(),
        )
    )

    index_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    type_assets: Counter[str] = Counter()
    subtype_counts: Counter[tuple[str, str]] = Counter()
    subtype_assets: Counter[tuple[str, str]] = Counter()
    type_categories: defaultdict[str, set[str]] = defaultdict(set)

    for item in plan:
        record = item["record"]
        destination: Path = item["destination"]
        destination.mkdir(parents=True, exist_ok=True)

        for asset in record["assets"]:
            source_image = item["source_record_path"].parent / asset["local_file"]
            copy_if_changed(source_image, destination / asset["local_file"])

        destination_record = destination / f"contest-{record['source']['contest_id']}.json"
        v3_record = copy.deepcopy(record)
        v3_record["classification_v3"] = {
            "schema_version": TAXONOMY_VERSION,
            "design_type": item["design_type"],
            "subtype": item["subtype"],
            "original_category": record["contest"]["category"],
            "source_record": item["source_record"],
            "source_record_sha256": item["source_record_sha256"],
        }
        destination_record.write_text(
            json.dumps(v3_record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (destination / "README.md").write_text(
            contest_readme(
                record,
                item["design_type"],
                item["subtype"],
                item["source_record"],
            ),
            encoding="utf-8",
        )

        relative_record = str(destination_record.relative_to(ROOT))
        asset_count = len(record["assets"])
        row = {
            "sample_id": record.get("sample_id"),
            "contest_id": str(record["source"]["contest_id"]),
            "title": record["contest"]["title"],
            "design_type": item["design_type"],
            "subtype": item["subtype"],
            "original_category": record["contest"]["category"],
            "asset_count": asset_count,
            "winner_entry_id": record.get("selection", {}).get(
                "winner_entry_id"
            ),
            "destination_record": relative_record,
            "source_record": item["source_record"],
        }
        index_rows.append(row)
        summary_rows.append(row)
        type_counts[item["design_type"]] += 1
        type_assets[item["design_type"]] += asset_count
        subtype_key = (item["design_type"], item["subtype"])
        subtype_counts[subtype_key] += 1
        subtype_assets[subtype_key] += asset_count
        type_categories[item["design_type"]].add(
            record["contest"]["category"]
        )

    (ROOT / "index-v0.1.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in index_rows
        ),
        encoding="utf-8",
    )
    (ROOT / "reclassification-summary-v0.1.json").write_text(
        json.dumps(summary_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    taxonomy = {
        "schema_version": TAXONOMY_VERSION,
        "generated_at": GENERATED_AT,
        "source_root": "../99design_v2",
        "record_count": len(plan),
        "asset_count": sum(type_assets.values()),
        "design_types": [
            {
                "name": design_type,
                "contest_count": type_counts[design_type],
                "asset_count": type_assets[design_type],
                "original_categories": sorted(type_categories[design_type]),
                "subtypes": [
                    {
                        "name": subtype,
                        "contest_count": subtype_counts[(design_type, subtype)],
                        "asset_count": subtype_assets[(design_type, subtype)],
                    }
                    for subtype in sorted(
                        {
                            sub
                            for dtype, sub in subtype_counts
                            if dtype == design_type
                        }
                    )
                ],
            }
            for design_type in DESIGN_TYPE_ORDER
        ],
        "category_mapping": {
            category: {"design_type": value[0], "subtype": value[1]}
            for category, value in sorted(CATEGORY_MAP.items())
        },
    }
    (ROOT / "taxonomy-v0.1.json").write_text(
        json.dumps(taxonomy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (ROOT / "README.md").write_text(
        collection_readme(taxonomy), encoding="utf-8"
    )


def collection_readme(taxonomy: dict[str, Any]) -> str:
    lines = [
        "# 99designs references organized by design type — v3",
        "",
        "This is a lossless design-type reclassification of `../99design_v2`.",
        "The v2 source tree remains unchanged. Every contest keeps its Brief,",
        "Winner/non-winner semantics, source metadata and rights fields.",
        "",
        "## Structure",
        "",
        "```text",
        "99design_v3/",
        "└── <Design Type>/",
        "    └── <Subtype>/",
        "        └── <Contest Title>/",
        "            ├── contest-<id>.json",
        "            ├── README.md",
        "            └── <public preview images>",
        "```",
        "",
        "## Coverage",
        "",
        "| Design type | Contests | Images |",
        "|---|---:|---:|",
    ]
    for item in taxonomy["design_types"]:
        lines.append(
            f"| {item['name']} | {item['contest_count']} | "
            f"{item['asset_count']} |"
        )
    lines.extend(
        [
            f"| **Total** | **{taxonomy['record_count']}** | "
            f"**{taxonomy['asset_count']}** |",
            "",
            "## Files",
            "",
            "- `taxonomy-v0.1.json`: complete 21-category mapping and counts;",
            "- `index-v0.1.jsonl`: one searchable row per contest;",
            "- `reclassification-summary-v0.1.json`: readable full summary;",
            "- `reclassify_by_design_type.py`: idempotent local materializer.",
            "",
            "Each copied contest JSON adds `classification_v3`; all original",
            "fields remain intact. Image bytes and SHA256 values are unchanged.",
            "",
            "## Rights boundary",
            "",
            "This operation only changes organization. Public visibility does",
            "not establish permission for model training or redistribution.",
            "The original `rights` object remains authoritative.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    plan = build_plan()
    write_outputs(plan)
    print(
        json.dumps(
            {
                "source": str(SOURCE_ROOT),
                "destination": str(ROOT),
                "contests": len(plan),
                "images": sum(len(item["record"]["assets"]) for item in plan),
                "design_types": len(DESIGN_TYPE_ORDER),
                "subtypes": len(CATEGORY_MAP),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
