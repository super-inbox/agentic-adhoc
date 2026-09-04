#!/usr/bin/env python3
"""Build a blinded 61-contest / 243-pair evaluate_rank fixture."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT_DIR = HERE.parent
EVAL_DIR = EXPERIMENT_DIR.parents[1]
SOURCE_ROOT = EVAL_DIR / "collectors" / "99design_v3"
INDEX_PATH = SOURCE_ROOT / "index-v0.1.jsonl"
DATASET_DIR = EXPERIMENT_DIR / "dataset"
CONTESTS_PATH = DATASET_DIR / "contests.jsonl"
PAIRS_PATH = DATASET_DIR / "pairs.jsonl"
MANIFEST_PATH = DATASET_DIR / "manifest.json"
PAGE_CHROME_MARKER = "It all began with a design brief."


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def strip_page_chrome(value: Any) -> tuple[str | None, bool]:
    if not isinstance(value, str) or not value.strip():
        return None, False
    if PAGE_CHROME_MARKER in value:
        return value.split(PAGE_CHROME_MARKER, 1)[0].rstrip(), True
    return value, False


def build_brief(record: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fields = [
        ("Contest title", record["contest"].get("title")),
        ("Design category", record["contest"].get("category_label")),
        ("Slogan", record["brief"].get("slogan")),
        ("About / requirements", record["brief"].get("about_us")),
        ("Vision", record["brief"].get("vision_public_excerpt")),
        ("Other notes", record["brief"].get("other_notes")),
    ]
    parts: list[str] = []
    stripped: list[str] = []
    for label, raw in fields:
        value, changed = strip_page_chrome(raw)
        if value:
            parts.append(f"{label}: {value}")
        if changed:
            stripped.append(label)
    return "\n".join(parts), {
        "source_availability": record["brief"].get("availability"),
        "page_chrome_removed_from": stripped,
        "ellipsis_preserved": "..." in "\n".join(parts) or "…" in "\n".join(parts),
        "missing_fields": record["brief"].get("missing_fields") or [],
    }


def option_order(assets: list[dict[str, Any]], case_index: int, contest_id: str) -> list[dict[str, Any]]:
    winner = next(asset for asset in assets if asset.get("selected") is True)
    losers = [asset for asset in assets if asset.get("selected") is not True]
    losers.sort(key=lambda item: sha256_bytes(f"rank-v1|{contest_id}|{item['entry_id']}".encode()))
    winner_position = case_index % len(assets)
    ordered = list(losers)
    ordered.insert(winner_position, winner)
    return ordered


def leakage_errors(case: dict[str, Any], source: dict[str, Any]) -> list[str]:
    visible = case["input"]["brief_text"].casefold()
    errors = []
    winner_id = source["selection"].get("winner_entry_id") or ""
    winner_designer = source["selection"].get("winner_designer") or ""
    if winner_id and winner_id.casefold() in visible:
        errors.append("winner entry id leaked into brief")
    if len(winner_designer.strip()) >= 3 and winner_designer.casefold() in visible:
        errors.append("winner designer leaked into brief")
    forbidden_keys = {"winner_entry_id", "winner_designer", "selected", "role", "designer"}
    input_keys = set(json.dumps(case["input"], ensure_ascii=False).casefold().split('"'))
    leaked_keys = sorted(forbidden_keys & input_keys)
    if leaked_keys:
        errors.append(f"selection keys leaked into input: {leaked_keys}")
    return errors


def main() -> int:
    index = [
        json.loads(line)
        for line in INDEX_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    contests: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    failures: list[str] = []
    for case_index, item in enumerate(index):
        record_path = SOURCE_ROOT / item["destination_record"]
        record = json.loads(record_path.read_text(encoding="utf-8"))
        assets = record["assets"]
        winner = next(asset for asset in assets if asset.get("selected") is True)
        ordered = option_order(assets, case_index, item["contest_id"])
        brief_text, sanitization = build_brief(record)
        options = []
        gold_options = []
        for offset, asset in enumerate(ordered):
            label = chr(ord("A") + offset)
            image_path = record_path.parent / asset["local_file"]
            if not image_path.exists():
                failures.append(f"missing image: {image_path}")
                continue
            actual_hash = sha256_file(image_path)
            if actual_hash != asset["sha256"]:
                failures.append(f"sha mismatch: {image_path}")
            if image_path.stat().st_size != asset["byte_size"]:
                failures.append(f"byte-size mismatch: {image_path}")
            options.append(
                {
                    "option_id": label,
                    "image_path": str(image_path.relative_to(EVAL_DIR)),
                    "sha256": actual_hash,
                    "media_type": asset["media_type"],
                    "width": asset["width"],
                    "height": asset["height"],
                }
            )
            gold_options.append(
                {
                    "option_id": label,
                    "entry_id": asset["entry_id"],
                    "selected": bool(asset.get("selected")),
                    "designer": asset.get("designer"),
                    "same_designer_as_winner": asset.get("designer") == winner.get("designer"),
                }
            )
        winner_option = next(option["option_id"] for option in gold_options if option["selected"])
        case = {
            "schema_version": "99designs-evaluate-rank-v1",
            "id": item["sample_id"],
            "input": {
                "brief_text": brief_text,
                "brief_is_incomplete_public_excerpt": True,
                "options": options,
            },
            "expected": {
                "winner_option_id": winner_option,
                "winner_entry_id": winner["entry_id"],
                "options": gold_options,
            },
            "metadata": {
                "contest_id": item["contest_id"],
                "design_type": item["design_type"],
                "subtype": item["subtype"],
                "industry": record["contest"].get("industry"),
                "client_cluster": record["contest"].get("client_display_name"),
                "exclude_simbans_slice": record["contest"].get("client_display_name") == "simbans",
                "source_record": str(record_path.relative_to(EVAL_DIR)),
                "source_record_sha256": sha256_file(record_path),
                "rights": record.get("rights"),
                "sanitization": sanitization,
            },
        }
        failures.extend(f"{case['id']}: {error}" for error in leakage_errors(case, record))
        contests.append(case)
        for gold in gold_options:
            if gold["selected"]:
                continue
            pairs.append(
                {
                    "schema_version": "99designs-winner-pair-v1",
                    "id": f"{case['id']}__{winner_option}-vs-{gold['option_id']}",
                    "contest_id": case["id"],
                    "winner_option_id": winner_option,
                    "other_option_id": gold["option_id"],
                    "same_designer": gold["same_designer_as_winner"],
                    "exclude_simbans_slice": case["metadata"]["exclude_simbans_slice"],
                    "design_type": item["design_type"],
                }
            )

    expected_counts = {
        "contests": 61,
        "options": 304,
        "pairs": 243,
        "same_designer_pairs": 37,
        "different_designer_pairs": 206,
        "non_simbans_contests": 52,
        "non_simbans_pairs": 208,
    }
    actual_counts = {
        "contests": len(contests),
        "options": sum(len(case["input"]["options"]) for case in contests),
        "pairs": len(pairs),
        "same_designer_pairs": sum(pair["same_designer"] for pair in pairs),
        "different_designer_pairs": sum(not pair["same_designer"] for pair in pairs),
        "non_simbans_contests": sum(not case["metadata"]["exclude_simbans_slice"] for case in contests),
        "non_simbans_pairs": sum(not pair["exclude_simbans_slice"] for pair in pairs),
    }
    if actual_counts != expected_counts:
        failures.append(f"count mismatch: expected={expected_counts}, actual={actual_counts}")
    winner_positions = {}
    for case in contests:
        pos = case["expected"]["winner_option_id"]
        winner_positions[pos] = winner_positions.get(pos, 0) + 1
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    CONTESTS_PATH.write_text(
        "".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in contests),
        encoding="utf-8",
    )
    PAIRS_PATH.write_text(
        "".join(json.dumps(pair, ensure_ascii=False, sort_keys=True) + "\n" for pair in pairs),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "99designs-evaluate-rank-manifest-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_index": str(INDEX_PATH.relative_to(EVAL_DIR)),
        "source_index_sha256": sha256_file(INDEX_PATH),
        "counts": actual_counts,
        "winner_position_distribution": winner_positions,
        "page_chrome_redactions": sum(
            bool(case["metadata"]["sanitization"]["page_chrome_removed_from"])
            for case in contests
        ),
        "briefs_with_ellipsis": sum(
            case["metadata"]["sanitization"]["ellipsis_preserved"] for case in contests
        ),
        "contests_sha256": sha256_file(CONTESTS_PATH),
        "pairs_sha256": sha256_file(PAIRS_PATH),
        "failures": failures,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
