#!/usr/bin/env python3
"""Materialize manually selected public 99designs contest samples.

This script does not discover or crawl contest pages. It only downloads the
public 500x500 preview URLs recorded in selected-contests-v0.1.json after
manual page inspection, then writes one self-contained sample directory per
contest.
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


def attachment_id(url: str) -> str:
    match = re.search(r"/(attachment_\d+)(?:[/?#]|$)", url)
    if not match:
        raise ValueError(f"No attachment id in URL: {url}")
    return match.group(1)


def contest_id(url: str) -> str:
    match = re.search(r"-(\d+)(?:[/?#]|$)", url)
    if not match:
        raise ValueError(f"No contest id in URL: {url}")
    return match.group(1)


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

    extension_by_format = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
    }
    extension = extension_by_format.get(image_format or "")
    if extension is None:
        raise ValueError(f"Unsupported image format {image_format!r}: {url}")
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f"Unexpected content type {content_type!r}: {url}")
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
    designer: str,
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
        "designer": designer,
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
    brief = seed["brief"]
    winner = assets[0]
    contest = dict(seed["contest"])
    contest["public_candidate_preview_count"] = len(assets) - 1
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
            "availability": brief["availability"],
            "about_us": brief.get("about_us"),
            "vision_public_excerpt": brief.get("vision_public_excerpt"),
            "other_notes": brief.get("other_notes"),
            "referenced_input_assets": {
                "mentioned_in_brief": brief.get(
                    "referenced_attachment_mentioned", False
                ),
                "publicly_visible_or_downloadable": False,
                "local_files": [],
            },
            "missing_fields": [
                "complete vision text where the public excerpt contains ellipses",
                "exact dimensions where omitted",
                "referenced input attachments",
            ],
        },
        "deliverables_listed_on_page": {
            "formats": ["PNG", "JPG", "AI", "PSD", "EPS", "PDF", "XD"],
            "publicly_downloadable": False,
            "note": (
                "These are delivery formats advertised to the contest client, "
                "not public source-file downloads."
            ),
        },
        "selection": {
            **seed["selection"],
            "winner_entry_id": winner["entry_id"],
        },
        "assets": assets,
        "evaluation_semantics": {
            "usable_as": [
                "brief-to-winner retrieval reference",
                "contest-level winner-vs-visible-candidate preference case",
                "visual ranking or pairwise comparison fixture",
                "cross-contest consistency fixture for the same client and product",
            ],
            "do_not_assume": [
                "non-winner previews are low-quality negatives",
                "the public candidates are finalists",
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
        "a partial public Brief, one Winner preview, and the non-winning previews",
        "displayed on the public page (capped at four during capture).",
        "",
        "## Metadata",
        "",
        f"- entries: {contest['entry_count']}",
        f"- designers: {contest['designer_count']}",
        f"- public candidate previews saved: {contest['public_candidate_preview_count']}",
        f"- winner: {record['selection']['winner_designer']}",
        "",
        "## Files",
        "",
        "| File | Role | Designer |",
        "|---|---|---|",
    ]
    for asset in record["assets"]:
        lines.append(
            f"| `{asset['local_file']}` | {asset['role']} | {asset['designer']} |"
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
            "Referenced input attachments, complete omitted Brief text, private",
            "feedback, and editable deliverables are unavailable. Model-training and",
            "redistribution permission have not been established; see the `rights`",
            "object in the contest JSON.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    seeds = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    if len(seeds) != 9:
        raise ValueError(f"Expected 9 selected contests, found {len(seeds)}")

    seen_folders: set[str] = set()
    summary: list[dict[str, Any]] = []
    for seed in seeds:
        folder_name = seed["folder_name"]
        if not folder_name or folder_name in seen_folders:
            raise ValueError(f"Invalid or duplicate folder name: {folder_name!r}")
        if "/" in folder_name or "\\" in folder_name:
            raise ValueError(f"Unsafe folder name: {folder_name!r}")
        seen_folders.add(folder_name)

        folder = ROOT / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        assets = [
            make_asset(
                folder,
                seed["winner"],
                role="winner",
                selected=True,
                designer=seed["selection"]["winner_designer"],
            )
        ]
        for candidate in seed["candidates"]:
            assets.append(
                make_asset(
                    folder,
                    candidate,
                    role="non_winner_public_preview",
                    selected=False,
                    designer=candidate["designer"],
                )
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
