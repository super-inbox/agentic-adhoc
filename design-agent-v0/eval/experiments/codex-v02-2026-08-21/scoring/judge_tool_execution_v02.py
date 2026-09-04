#!/usr/bin/env python3
"""Independent multimodal judge for the L3 ``tool_execution`` rubric dimension.

The original judge-v2 covers brief understanding, revision fidelity, and
cross-asset consistency. Eight L3 briefs instead reserve 0.35 rubric weight for
tool execution, so leaving that field out creates a silent coverage hole. This
pass scores only that missing dimension and keeps its output separate.

Judge-v1 was invalidated by counterfactual controls: after all campaign image
files were deleted it still claimed to see them, and after an edit result was
replaced with the unchanged source it trusted stale change-set claims. V2
therefore receives only evaluator-computed file facts and the actual source and
final artifacts. Candidate-authored verification, change-set, metrics, masks,
and final-response claims are excluded from evidence.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import struct
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from judge_rubric_v02 import selected_runs

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parent.parent
DESIGN_AGENT_ROOT = EVAL.parent
BRIEFS = EVAL / "brief_bank" / "briefs.v0.2.jsonl"
MODEL = os.environ.get("JUDGE_MODEL", "gemini-2.5-pro")
MAX_INPUT_IMAGES = int(os.environ.get("TOOL_JUDGE_MAX_INPUT_IMAGES", "4"))
MAX_OUTPUT_IMAGES = int(os.environ.get("TOOL_JUDGE_MAX_OUTPUT_IMAGES", "8"))
TEXT_CAP = 5000

PROMPT = """You are an independent evaluator scoring TOOL EXECUTION for one
L3 design-agent task. Judge only the evaluator-computed inventory and the actual
source/final artifacts attached after this text. Candidate-authored
verification, change-set, metrics, masks, and narrative claims have been
excluded because they are not independent evidence.

CRITICAL EVIDENCE RULES:
- If a required file is absent from OUTPUT INVENTORY, it is absent. Never infer
  it from a filename mentioned elsewhere.
- Compare SOURCE and OUTPUT images directly. Matching SHA-256 values mean the
  image is byte-for-byte unchanged.
- Do not claim to see an image unless its labelled attachment is present.
- Do not require an exact tool name or one golden workflow; grade observable
  execution against the requested intent and requirements.

PRIMARY INTENT
{primary_intent}

USER REQUEST
{brief}

TOOLS AVAILABLE TO THE CANDIDATE
{tools}

EXPECTED OBSERVABLE WORKFLOW
{workflow}

HARD GATES
{hard_gates}

HARD CONSTRAINTS
{hard_constraints}

NEGATIVE CONSTRAINTS
{negative_constraints}

DELIVERABLES
{deliverables}

INPUT MANIFEST
{input_manifest}

OUTPUT INVENTORY (dimensions are independently read from PNG headers)
{inventory}

EVALUATION/REPORT DELIVERABLE TEXT
Only included for evaluate/rank tasks, where the report itself is the requested
deliverable. It is not included for edit/adapt/export tasks.
{report_text}

INDEPENDENT PRODUCTION-FILE FACTS
{production_facts}

First evaluate every hard gate and deliverable requirement as
MET / VIOLATED / CANNOT_TELL, citing a concrete filename, visible feature, or
text excerpt. Then assign tool_execution using these anchors:
  5 = correct operation for the requested intent; every key output and hard
      gate is observably satisfied
  4 = correct, complete execution with only a minor production imperfection
  3 = usable execution, but one important requirement is weak or cannot be
      verified from the artifacts
  2 = a material execution error, missing/wrong key deliverable, or poor source
      preservation
  1 = wrong operation (for example regenerate instead of edit/adapt/evaluate),
      a hard gate is clearly broken, or the output is largely unusable
  0 = no task result; prose-only when the task requires an executable visual or
      production artifact

Return ONLY JSON:
{{"checks":[{{"item":"...","verdict":"MET|VIOLATED|CANNOT_TELL","evidence":"..."}}],
  "tool_execution":{{"score":0,"why":"..."}}}}"""


def load_briefs() -> dict[str, dict]:
    briefs = {}
    for line in BRIEFS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            briefs[row["id"].lower()] = row
    return briefs


def png_dimensions(path: Path):
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
            return list(struct.unpack(">II", header[16:24]))
    except Exception:
        pass
    return None


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_inventory(run: Path):
    inventory = []
    output_root = run / "outputs"
    if not output_root.is_dir():
        return inventory
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(output_root))
        item = {"path": rel, "bytes": path.stat().st_size, "sha256": sha256(path)}
        dimensions = png_dimensions(path)
        if dimensions:
            item["pixel_dimensions"] = dimensions
        inventory.append(item)
    return inventory


def collect_report_text(run: Path, primary_intent: str):
    if primary_intent != "evaluate_rank":
        return []
    texts = []
    output_root = run / "outputs"
    if output_root.is_dir():
        for path in sorted(output_root.rglob("*")):
            if not path.is_file() or path.name in {"verification.json", "project-state.json"}:
                continue
            if path.suffix.lower() not in {".md", ".json", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            texts.append(f"--- {path.relative_to(output_root)}\n{text[:TEXT_CAP]}")
            if len(texts) >= 8:
                break
    return texts


def production_file_facts(run: Path):
    """Read production properties from the files themselves, never self-report."""
    facts = []
    output_root = run / "outputs"
    if not output_root.is_dir():
        return facts
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        rel = str(path.relative_to(output_root))
        if suffix == ".svg":
            item = {"path": rel, "type": "SVG", "parseable": False}
            try:
                root = ET.parse(path).getroot()
                item.update({
                    "parseable": True,
                    "root_attributes": dict(root.attrib),
                    "element_count": sum(1 for _ in root.iter()),
                    "path_count": sum(1 for node in root.iter() if node.tag.endswith("path")),
                    "cut_contour_elements": [
                        {"tag": node.tag.split("}")[-1], "attributes": dict(node.attrib)}
                        for node in root.iter()
                        if "cutcontour" in " ".join(
                            [str(node.attrib.get("id", "")), str(node.attrib.get("{http://www.inkscape.org/namespaces/inkscape}label", ""))]
                        ).lower()
                    ][:4],
                })
            except Exception as exc:
                item["parse_error"] = type(exc).__name__
            facts.append(item)
        elif suffix == ".pdf":
            raw = path.read_bytes()
            text = raw.decode("latin-1", errors="ignore")
            media_boxes = re.findall(r"/MediaBox\s*\[([^\]]]+)\]", text)[:3]
            facts.append({
                "path": rel,
                "type": "PDF",
                "header": raw[:8].decode("latin-1", errors="ignore"),
                "media_boxes": media_boxes,
                "has_device_cmyk": "/DeviceCMYK" in text,
                "has_cutcontour_name": "CutContour" in text,
                "has_separation_color_space": "/Separation" in text,
                "has_overprint_graphics_state": any(token in text for token in ("/OP true", "/op true")),
            })
    return facts


def manifest_and_sources(run: Path):
    manifest_path = run / "input-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = []
    images = []
    for item in manifest:
        source = item.get("source_path")
        if not source:
            continue
        path = DESIGN_AGENT_ROOT / source
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"} or not path.is_file():
            continue
        images.append((f"INPUT {item.get('input_id')}: {source}", path))
        if len(images) >= MAX_INPUT_IMAGES:
            break
    return manifest, images


def choose_evenly(paths: list[Path], limit: int):
    if len(paths) <= limit:
        return paths
    if limit <= 1:
        return [paths[-1]]
    indices = {round(i * (len(paths) - 1) / (limit - 1)) for i in range(limit)}
    return [paths[i] for i in sorted(indices)]


def output_images(run: Path):
    root = run / "outputs"
    if not root.is_dir():
        return []
    candidates = [
        path for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    excluded_tokens = (
        "/qa/", "/masks/", "/layers/", "/evidence/", "/assets/",
        "-mask", "_mask", "-difference", "_difference", "-source", "_source", "-crop", "_crop",
    )
    primary = [p for p in candidates if not any(t in f"/{p.relative_to(root)}".lower() for t in excluded_tokens)]
    selected = choose_evenly(primary, MAX_OUTPUT_IMAGES)
    return [(f"OUTPUT {path.relative_to(root)}", path) for path in selected]


def inline_image(label: str, path: Path):
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return [
        {"text": label},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(path.read_bytes()).decode()}},
    ]


def judge(client, brief: dict, run: Path):
    from google.genai import types

    manifest, inputs = manifest_and_sources(run)
    constraints = brief.get("constraints") or {}
    prompt = PROMPT.format(
        primary_intent=brief.get("primary_intent"),
        brief=brief.get("initial_query", "")[:1600],
        tools=json.dumps(brief.get("tools_available") or [], ensure_ascii=False),
        workflow=json.dumps(brief.get("expected_workflow") or [], ensure_ascii=False)[:4000],
        hard_gates=json.dumps((brief.get("rubric") or {}).get("hard_gates") or [], ensure_ascii=False),
        hard_constraints=json.dumps(constraints.get("hard") or [], ensure_ascii=False),
        negative_constraints=json.dumps(constraints.get("negative") or [], ensure_ascii=False),
        deliverables=json.dumps(brief.get("deliverables") or [], ensure_ascii=False)[:4000],
        input_manifest=json.dumps(manifest, ensure_ascii=False)[:4000],
        inventory=json.dumps(output_inventory(run), ensure_ascii=False)[:12000],
        report_text="\n\n".join(
            collect_report_text(run, brief.get("primary_intent"))
        )[:30000] or "(not applicable or no report artifact)",
        production_facts=json.dumps(production_file_facts(run), ensure_ascii=False)[:12000]
        or "(none)",
    )
    parts = [{"text": prompt}]
    for label, path in inputs + output_images(run):
        if path.stat().st_size <= 5_000_000:
            parts.extend(inline_image(label, path))
    response = client.models.generate_content(
        model=MODEL,
        contents=[{"role": "user", "parts": parts}],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json").strip()
    return json.loads(raw)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-new-runs", type=int, default=0)
    return parser.parse_args()


def write_snapshot(path: Path, rows: dict[str, dict], selected_ids: set[str]):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(rows[rid], ensure_ascii=False) + "\n"
            for rid in sorted(selected_ids)
            if rid in rows
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    try:
        from google import genai
    except ImportError:
        print("Install google-genai before running this judge.", file=sys.stderr)
        return 2
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY is required.", file=sys.stderr)
        return 2

    briefs = load_briefs()
    runs = [
        (run, brief, result)
        for run, brief, result in selected_runs(briefs)
        if "tool_execution" in ((brief.get("rubric") or {}).get("checkpoint_weights") or {})
    ]
    selected_ids = {str(run.relative_to(EXP)) for run, _, _ in runs}
    output_path = HERE / "tool-execution-judged-v2.jsonl"
    rows = {}
    if output_path.exists():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["run"]] = row
    done = {
        rid for rid, row in rows.items()
        if rid in selected_ids and row.get("error") is None
    }
    write_snapshot(output_path, rows, selected_ids)

    client = genai.Client(api_key=key)
    attempted = 0
    for index, (run, brief, result) in enumerate(runs, 1):
        rid = str(run.relative_to(EXP))
        if rid in done:
            continue
        if args.max_new_runs and attempted >= args.max_new_runs:
            break
        attempted += 1
        try:
            value = judge(client, brief, run)
            score = (value.get("tool_execution") or {}).get("score")
            if not isinstance(score, (int, float)) or not 0 <= score <= 5:
                raise ValueError(f"invalid tool_execution score: {score!r}")
            error = None
        except Exception as exc:
            value, score = {}, None
            error = f"{type(exc).__name__}: {exc}"[:500]
        rows[rid] = {
            "run": rid,
            "brief_id": brief["id"],
            "condition": result.get("context_condition") or run.parent.name,
            "level": brief.get("level"),
            "model": MODEL,
            "error": error,
            "tool_execution": score,
            "tool_execution_why": (value.get("tool_execution") or {}).get("why"),
            "checks": value.get("checks") or [],
        }
        write_snapshot(output_path, rows, selected_ids)
        print(f"  {index}/{len(runs)} {brief['id']} -> tool_execution={score}"
              + (f" ERR {error}" if error else ""), flush=True)
        if error and ("RESOURCE_EXHAUSTED" in error or "spending cap" in error.lower()):
            break
        time.sleep(1)

    success = sum(
        1 for rid in selected_ids
        if rid in rows and rows[rid].get("error") is None
    )
    print(f"\ntool-execution judge coverage: {success}/{len(selected_ids)}")
    print(f"wrote {output_path.relative_to(EVAL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
