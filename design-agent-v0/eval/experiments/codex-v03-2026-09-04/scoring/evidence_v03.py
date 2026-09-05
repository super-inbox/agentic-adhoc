#!/usr/bin/env python3
"""Evaluator-owned evidence helpers for Brief Bank v0.3.

Candidate-authored claims are never treated as proof. This module reads file
headers/structure, pixels, run metadata, and the original bound inputs.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageChops


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parent.parent
DESIGN_AGENT_ROOT = EVAL.parent
BRIEFS = EVAL / "brief_bank" / "briefs.v0.3.jsonl"
QUERIES = EVAL / "brief_bank" / "initial_queries.v0.3.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_runs(external_only: bool = True) -> list[tuple[Path, dict, dict, dict]]:
    briefs = {row["id"]: row for row in read_jsonl(BRIEFS)}
    queries = {row["id"]: row for row in read_jsonl(QUERIES)}
    latest: dict[str, tuple[str, Path, dict]] = {}
    for result_path in sorted((EXP / "runs").rglob("result.json")):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if result.get("outcome") != "completed" or result.get("primary_eligible") is False:
            continue
        brief_id = result.get("base_brief_id")
        if external_only and not str(brief_id).startswith(("DAB-L3-RDT-", "DAB-L4-RDT-")):
            continue
        condition = result.get("context_condition") or result_path.parent.parent.name
        condition_id = result.get("query_id") or f"{brief_id}@{condition}"
        stamp = str(result.get("started_at") or result_path.parent.name)
        if condition_id not in latest or stamp > latest[condition_id][0]:
            latest[condition_id] = (stamp, result_path.parent, result)
    selected = []
    for condition_id in sorted(latest):
        _, run, result = latest[condition_id]
        brief = briefs.get(result.get("base_brief_id"))
        query = queries.get(condition_id)
        if brief and query:
            selected.append((run, brief, result, query))
    return selected


def input_manifest(run: Path) -> list[dict]:
    try:
        return json.loads((run / "input-manifest.json").read_text(encoding="utf-8"))
    except Exception:
        return []


def input_sources(run: Path) -> list[tuple[str, Path]]:
    sources = []
    for item in input_manifest(run):
        source = item.get("source_path")
        if not source:
            continue
        path = DESIGN_AGENT_ROOT / source
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            sources.append((f"INPUT {item.get('input_id')}: {source}", path))
    return sources


def image_facts(path: Path) -> dict | None:
    try:
        with Image.open(path) as image:
            return {
                "pixel_dimensions": [image.width, image.height],
                "mode": image.mode,
                "format": image.format,
            }
    except Exception:
        return None


def _svg_facts(path: Path) -> dict:
    item = {"type": "SVG", "parseable": False}
    try:
        root = ET.parse(path).getroot()
        nodes = list(root.iter())
        image_nodes = [node for node in nodes if node.tag.endswith("image")]
        hrefs = []
        for node in image_nodes:
            href = node.attrib.get("href") or node.attrib.get("{http://www.w3.org/1999/xlink}href")
            if href:
                hrefs.append(str(href)[:160])
        item.update(
            {
                "parseable": True,
                "root_attributes": dict(root.attrib),
                "element_count": len(nodes),
                "path_count": sum(node.tag.endswith("path") for node in nodes),
                "shape_count": sum(
                    node.tag.endswith(("path", "rect", "circle", "ellipse", "polygon", "polyline", "line"))
                    for node in nodes
                ),
                "text_count": sum(node.tag.endswith("text") for node in nodes),
                "image_count": len(image_nodes),
                "embedded_raster_count": sum(href.startswith("data:image/") for href in hrefs),
                "image_hrefs": hrefs,
            }
        )
    except Exception as exc:
        item["parse_error"] = type(exc).__name__
    return item


def _pdf_facts(path: Path) -> dict:
    raw = path.read_bytes()
    item = {
        "type": "PDF",
        "header": raw[:8].decode("latin-1", errors="ignore"),
        "parseable": False,
        "bytes": len(raw),
    }
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        texts = []
        page_sizes = []
        image_counts = []
        for page in reader.pages[:12]:
            page_sizes.append([float(page.mediabox.width), float(page.mediabox.height)])
            try:
                image_counts.append(len(page.images))
            except Exception:
                image_counts.append(None)
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                pass
        item.update(
            {
                "parseable": True,
                "pages": len(reader.pages),
                "page_sizes_points": page_sizes,
                "page_image_counts": image_counts,
                "text_excerpt": "\n".join(texts)[:5000],
            }
        )
    except Exception as exc:
        item["parse_error"] = type(exc).__name__
    text = raw.decode("latin-1", errors="ignore")
    item.update(
        {
            "has_device_cmyk": "/DeviceCMYK" in text,
            "has_embedded_image_object": "/Subtype /Image" in text,
            "has_font_object": "/Type /Font" in text,
        }
    )
    return item


def _eps_facts(path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode("latin-1", errors="ignore")
    return {
        "type": "EPS",
        "header": text[:40],
        "parseable_header": text.startswith("%!PS-Adobe"),
        "bounding_box": (re.findall(r"%%BoundingBox:\s*([^\r\n]+)", text) or [None])[0],
        "contains_raster_operators": any(token in text for token in ("colorimage", "imagemask", " image")),
        "path_operator_count": sum(text.count(token) for token in (" lineto", " curveto", " moveto")),
    }


def production_fact(path: Path) -> dict | None:
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return _svg_facts(path)
    if suffix == ".pdf":
        return _pdf_facts(path)
    if suffix == ".eps":
        return _eps_facts(path)
    return None


def output_inventory(run: Path) -> list[dict]:
    root = run / "outputs"
    rows = []
    if not root.is_dir():
        return rows
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        row = {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        image = image_facts(path)
        if image:
            row.update(image)
        structural = production_fact(path)
        if structural:
            row["structure"] = structural
        if path.suffix.lower() == ".json":
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                row["json_parseable"] = True
                row["json_top_level"] = type(value).__name__
                row["json_keys"] = sorted(value)[:50] if isinstance(value, dict) else None
            except Exception:
                row["json_parseable"] = False
        rows.append(row)
    return rows


def production_facts(run: Path) -> list[dict]:
    facts = []
    root = run / "outputs"
    if not root.is_dir():
        return facts
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        fact = production_fact(path)
        if fact:
            facts.append({"path": str(path.relative_to(root)), **fact})
    return facts


def business_text(run: Path, cap: int = 40000) -> str:
    root = run / "outputs"
    if not root.is_dir():
        return "(none)"
    excluded = {
        "verification.json",
        "project-state.json",
        "change_set.json",
        "design_document.json",
        "trajectory.jsonl",
    }
    blocks = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in excluded:
            continue
        if path.suffix.lower() not in {".md", ".txt", ".csv", ".json"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        blocks.append(f"--- {path.relative_to(root)}\n{content[:6000]}")
    return "\n\n".join(blocks)[:cap] or "(none)"


def trajectory_facts(run: Path, result: dict) -> dict:
    events = read_jsonl(run / "trajectory.jsonl")
    counts: dict[str, int] = {}
    for event in events:
        kind = str(event.get("type") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return {
        "intended_turns": result.get("intended_turns"),
        "completed_turns": result.get("completed_turns"),
        "logical_sessions": result.get("logical_sessions"),
        "latency_ms": result.get("latency_ms"),
        "event_count": len(events),
        "event_type_counts": counts,
        "command_count": sum(
            1 for event in events if event.get("type") == "codex.command" and event.get("phase") == "item.completed"
        ),
        "agent_message_count": sum(event.get("type") == "codex.agent_message" for event in events),
        "version_directories": sorted(
            path.name
            for path in (run / "outputs").glob("v*")
            if path.is_dir()
        ),
    }


def structured_artifact_facts(run: Path, query: dict) -> dict:
    root = run / "outputs"
    found = {}
    for name in query.get("required_structured_artifacts") or []:
        if name == "trajectory.jsonl":
            found[name] = (run / name).is_file() and (run / name).stat().st_size > 0
        else:
            found[name] = any(path.is_file() for path in root.rglob(name)) if root.is_dir() else False
    return found


def _candidate_edit_output(run: Path, size: tuple[int, int], source_hash: str) -> Path | None:
    root = run / "outputs"
    candidates = []
    if not root.is_dir():
        return None
    for path in root.rglob("*.png"):
        facts = image_facts(path)
        if not facts or tuple(facts["pixel_dimensions"]) != size or sha256(path) == source_hash:
            continue
        rel = str(path.relative_to(root)).lower()
        penalty = sum(token in rel for token in ("mask", "diff", "source", "contact", "proof"))
        bonus = sum(token in rel for token in ("edited", "final", "traffic", "road", "cartoon", "preview"))
        candidates.append((penalty, -bonus, -path.stat().st_mtime, path))
    return sorted(candidates)[0][-1] if candidates else None


def masked_edit_facts(run: Path, brief_id: str) -> dict | None:
    if brief_id not in {"DAB-L3-RDT-005", "DAB-L3-RDT-006"}:
        return None
    sources = {}
    for item in input_manifest(run):
        source_path = item.get("source_path")
        if source_path:
            path = DESIGN_AGENT_ROOT / source_path
            if path.is_file():
                sources[item.get("input_id")] = path
    source = sources.get("edit-target")
    mask_path = sources.get("edit-mask")
    if not source or not mask_path:
        return {"error": "bound source or mask missing"}
    with Image.open(source) as source_image, Image.open(mask_path) as mask_image:
        size = source_image.size
        output = _candidate_edit_output(run, size, sha256(source))
        if output is None:
            return {
                "source": str(source),
                "mask": str(mask_path),
                "candidate_output": None,
                "error": "no changed output PNG matching source dimensions",
            }
        source_mode = source_image.mode
        with Image.open(output) as output_image:
            output_mode = output_image.mode
            src = source_image.convert("RGBA")
            out = output_image.convert("RGBA")
            mask = mask_image.convert("L")
            outside = mask.point(lambda value: 255 if value == 0 else 0)
            inside = mask.point(lambda value: 255 if value > 0 else 0)
            diff = ImageChops.difference(src, out)
            channels = list(diff.split())
            diff_any = channels[0]
            for channel in channels[1:]:
                diff_any = ImageChops.lighter(diff_any, channel)
            diff_any = diff_any.point(lambda value: 255 if value else 0)
            outside_changed = ImageChops.multiply(diff_any, outside)
            inside_changed = ImageChops.multiply(diff_any, inside)
            outside_hist = outside_changed.histogram()
            inside_hist = inside_changed.histogram()
            outside_changed_pixels = sum(outside_hist[1:])
            inside_changed_pixels = sum(inside_hist[1:])
            outside_mask_hist = outside.histogram()
            inside_mask_hist = inside.histogram()
            outside_pixels = sum(outside_mask_hist[1:])
            inside_pixels = sum(inside_mask_hist[1:])
            return {
                "source": str(source.relative_to(DESIGN_AGENT_ROOT)),
                "mask": str(mask_path.relative_to(DESIGN_AGENT_ROOT)),
                "candidate_output": str(output.relative_to(run / "outputs")),
                "source_sha256": sha256(source),
                "output_sha256": sha256(output),
                "dimensions_match": out.size == src.size,
                "source_mode": source_mode,
                "output_mode": output_mode,
                "mode_matches": output_mode == source_mode,
                "outside_mask_pixels": outside_pixels,
                "outside_mask_changed_pixels": outside_changed_pixels,
                "outside_mask_changed_fraction": round(outside_changed_pixels / max(outside_pixels, 1), 8),
                "inside_mask_pixels": inside_pixels,
                "inside_mask_changed_pixels": inside_changed_pixels,
                "inside_mask_changed_fraction": round(inside_changed_pixels / max(inside_pixels, 1), 8),
            }


def latency_summary(rows: list[dict]) -> dict:
    values = [row.get("latency_ms") for row in rows if row.get("latency_ms") is not None]
    if not values:
        return {"n": 0, "mean_minutes": None, "p50_minutes": None, "max_minutes": None}
    return {
        "n": len(values),
        "mean_minutes": round(statistics.fmean(values) / 60000, 2),
        "p50_minutes": round(statistics.median(values) / 60000, 2),
        "max_minutes": round(max(values) / 60000, 2),
    }
