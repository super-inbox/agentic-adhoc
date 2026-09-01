#!/usr/bin/env python3
"""Materialize manually inspected Travel & Hotel contest samples.

The script does not crawl or discover contest pages. It only downloads the
public 500x500 preview URLs already recorded in selected-contests-v0.1.json.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import ssl
import urllib.request
from pathlib import Path
from typing import Any

import certifi
from PIL import Image


ROOT = Path(__file__).resolve().parent
SELECTION_PATH = ROOT / "selected-contests-v0.1.json"
CAPTURED_AT = "2026-08-31"
USER_AGENT = "Curify manual public-preview sample builder/0.1"
TLS_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def id_from_url(url: str, pattern: str, label: str) -> str:
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"No {label} in URL: {url}")
    return match.group(1)


def attachment_id(url: str) -> str:
    return id_from_url(url, r"/(attachment_\d+)(?:[/?#]|$)", "attachment id")


def contest_id(url: str) -> str:
    return id_from_url(url, r"-(\d+)(?:[/?#]|$)", "contest id")


def download_preview(url: str) -> tuple[bytes, str, str, int, int]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(
        request, timeout=30, context=TLS_CONTEXT
    ) as response:
        payload = response.read()
        content_type = response.headers.get_content_type()

    with Image.open(io.BytesIO(payload)) as image:
        width, height = image.size
        image_format = image.format

    extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(
        image_format or ""
    )
    if extension is None:
        raise ValueError(f"Unsupported image format {image_format!r}: {url}")
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f"Unexpected content type {content_type!r}: {url}")
    if (width, height) != (500, 500):
        raise ValueError(f"Unexpected preview dimensions {(width, height)}: {url}")
    return payload, extension, content_type, width, height


def write_binary_if_changed(path: Path, payload: bytes) -> None:
    if path.exists() and path.read_bytes() == payload:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def make_asset(
    folder: Path,
    raw: dict[str, Any],
    role: str,
    selected: bool,
) -> dict[str, Any]:
    url = raw["url"]
    payload, extension, media_type, width, height = download_preview(url)
    entry_id = attachment_id(url)
    filename = entry_id + extension
    write_binary_if_changed(folder / filename, payload)
    return {
        "entry_id": entry_id,
        "role": role,
        "selected": selected,
        "designer": raw["designer"],
        "alt": raw.get("alt"),
        "local_file": filename,
        "media_type": media_type,
        "width": width,
        "height": height,
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "source_preview_url": url,
    }


def make_record(seed: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, Any]:
    source_url = seed["source"]["url"]
    cid = contest_id(source_url)
    contest = dict(seed["contest"])
    contest["public_candidate_preview_count"] = len(assets) - 1
    source_brief = seed["brief"]
    winner = assets[0]
    selection = seed["selection"]

    return {
        "schema_version": "99designs-public-contest-sample-v0.2",
        "sample_id": f"99designs-contest-{cid}",
        "captured_at": CAPTURED_AT,
        "capture_method": "manual_public_page_inspection",
        "source": {
            "platform": "99designs",
            "contest_id": cid,
            "url": source_url,
            "page_title": seed["source"].get("page_title"),
            "language": "en",
            "public_page_accessible_without_login": True,
        },
        "contest": contest,
        "brief": {
            "availability": source_brief["availability"],
            "slogan": source_brief.get("slogan"),
            "about_us": source_brief.get("about_us"),
            "vision_public_excerpt": source_brief.get(
                "vision_public_excerpt"
            ),
            "other_notes": source_brief.get("other_notes"),
            "referenced_input_assets": {
                "mentioned_in_brief": source_brief.get(
                    "referenced_attachment_mentioned", False
                ),
                "publicly_visible_or_downloadable": False,
                "local_files": [],
            },
            "missing_fields": [
                "complete public fields where the page contains ellipses",
                "referenced input attachments",
                "private comments and revision history",
            ],
        },
        "deliverables_listed_on_page": {
            "formats": seed.get("deliverable_formats", []),
            "publicly_downloadable": False,
            "note": (
                "These are delivery formats advertised to the contest client, "
                "not public source-file downloads."
            ),
        },
        "selection": {
            "winner_entry_id": winner["entry_id"],
            "winner_designer": winner["designer"],
            "winner_designer_level": selection.get("winner_designer_level"),
            "public_selection_rationale_available": selection.get(
                "public_selection_rationale_available", False
            ),
            "client_review": selection.get("client_review"),
        },
        "assets": assets,
        "evaluation_semantics": {
            "usable_as": [
                "brief-to-winner retrieval reference",
                "contest-level winner-vs-visible-candidate preference case",
                "visual ranking or pairwise comparison fixture",
                "Travel & Hotel category coverage fixture",
            ],
            "do_not_assume": [
                "non-winner previews are low-quality negatives",
                "the four public candidates are finalists",
                "the client rejected each candidate for a known reason",
                "the public excerpt is the complete original brief",
            ],
        },
        "rights": {
            "status": "permission_required",
            "training_use": "not_cleared",
            "redistribution": "not_cleared",
            "source_files": "not_available",
            "note": (
                "Public visibility does not establish permission for model "
                "training or redistribution. Keep this sample for local "
                "indexing/evaluation until rights are reviewed."
            ),
        },
    }


def make_readme(record: dict[str, Any]) -> str:
    contest = record["contest"]
    lines = [
        f"# {contest['title']}",
        "",
        f"Source: <{record['source']['url']}>",
        "",
        "This directory contains one manually inspected public contest sample:",
        "a partial public Brief, one Winner preview, and four public non-winner",
        "previews displayed on the contest page.",
        "",
        "## Metadata",
        "",
        f"- category: {contest['category_label']}",
        f"- entries: {contest['entry_count']}",
        f"- designers: {contest['designer_count']}",
        f"- winner: {record['selection']['winner_designer']}",
        "",
        "## Files",
        "",
        "| File | Role | Designer |",
        "|---|---|---|",
    ]
    for asset in record["assets"]:
        designer = asset["designer"].replace("|", "\\|")
        lines.append(
            f"| `{asset['local_file']}` | {asset['role']} | {designer} |"
        )
    lines.extend(
        [
            "",
            "All images are 500x500 public preview renditions, not original",
            "production files. A non-winner means only that the entry was not",
            "selected in this contest; it is not an objective low-quality label.",
            "",
            "## Known gaps and rights",
            "",
            "Referenced input attachments, omitted Brief text, private feedback,",
            "and editable deliverables are unavailable. Model-training and",
            "redistribution permission have not been established; see the `rights`",
            "object in the contest JSON.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    seeds = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    if len(seeds) != 10:
        raise ValueError(f"Expected 10 selected contests, found {len(seeds)}")

    seen_folders: set[str] = set()
    summary: list[dict[str, Any]] = []
    for seed in seeds:
        folder_name = seed["folder_name"]
        if not folder_name or folder_name in seen_folders:
            raise ValueError(f"Invalid or duplicate folder name: {folder_name!r}")
        if "/" in folder_name or "\\" in folder_name:
            raise ValueError(f"Unsafe folder name: {folder_name!r}")
        if seed["contest"].get("winner_count") != 1:
            raise ValueError(f"Expected one Winner: {folder_name!r}")
        if len(seed.get("candidates", [])) != 4:
            raise ValueError(f"Expected four public candidates: {folder_name!r}")
        seen_folders.add(folder_name)

        folder = ROOT / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        winner_seed = seed["selection"]["winners"][0]
        assets = [make_asset(folder, winner_seed, "winner", True)]
        assets.extend(
            make_asset(folder, candidate, "non_winner_public_preview", False)
            for candidate in seed["candidates"]
        )

        record = make_record(seed, assets)
        cid = record["source"]["contest_id"]
        record_path = folder / f"contest-{cid}.json"
        record_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (folder / "README.md").write_text(make_readme(record), encoding="utf-8")
        summary.append(
            {
                "folder": folder_name,
                "contest_id": cid,
                "category": record["contest"]["category"],
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
