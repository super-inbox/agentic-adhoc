#!/usr/bin/env python3
"""Black-box, single-turn Design Agent evaluation.

Uploads each case's local images, creates one agent run, polls to a terminal
state, and scores route/status/stage coverage/verdict/artifacts. The bundled
scoring snapshot is used by default; ``CURIFY_BACKEND_ROOT`` can override it.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx

DEFAULT_BACKEND_ROOT = (
    Path(__file__).resolve().parents[1]
    / "curify-integration"
    / "curify_background"
)
BACKEND_ROOT = Path(
    os.getenv("CURIFY_BACKEND_ROOT", str(DEFAULT_BACKEND_ROOT))
).expanduser().resolve()
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent_runtime.evaluation import aggregate_results, render_markdown, score_case


TERMINAL = {"COMPLETED", "ABSTAINED", "FAILED"}


def _load_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _upload(client: httpx.Client, path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as handle:
        response = client.post(
            "/images/upload",
            files={"image_file": (path.name, handle, media_type)},
        )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    if not data.get("blob_url"):
        raise RuntimeError(payload.get("message") or "Image upload returned no blob_url.")
    return str(data["blob_url"])


def _probe_artifacts(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    probes: List[Dict[str, Any]] = []
    # Use a separate client with no Authorization header so the Curify bearer
    # token is never forwarded to the signed GCS host.
    with httpx.Client(timeout=30.0, follow_redirects=True) as artifact_client:
        for artifact in payload.get("artifacts") or []:
            probe = {
                "artifact_id": artifact.get("artifact_id"),
                "reachable": False,
            }
            url = artifact.get("url")
            if not url:
                probes.append(probe)
                continue
            try:
                with artifact_client.stream("GET", url) as response:
                    response.raise_for_status()
                    first_chunk = next(response.iter_bytes(), b"")
                    probe["reachable"] = bool(first_chunk)
                    probe["content_type"] = response.headers.get("content-type")
            except Exception as exc:
                probe["error"] = type(exc).__name__
            probes.append(probe)
    return probes


def _execute_case(
    client: httpx.Client,
    case: Dict[str, Any],
    case_dir: Path,
    timeout_seconds: int,
    poll_seconds: float,
) -> Dict[str, Any]:
    request = dict(case.get("request") or {})
    local_files = request.pop("image_files", [])
    uploaded = [_upload(client, (case_dir / value).resolve()) for value in local_files]
    request["image_urls"] = [*uploaded, *(request.get("image_urls") or [])]
    created = client.post("/design-agent/runs", json=request)
    created.raise_for_status()
    run_id = created.json()["run_id"]
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/design-agent/runs/{run_id}")
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") in TERMINAL:
            if (case.get("expected") or {}).get("artifacts_reachable"):
                payload["_artifact_probe"] = _probe_artifacts(payload)
            return payload
        time.sleep(poll_seconds)
    raise TimeoutError(f"Run {run_id} did not finish in {timeout_seconds}s.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default=os.getenv("CURIFY_EVAL_TOKEN"))
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--poll", type=float, default=2.0)
    parser.add_argument("--out-jsonl", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()
    if not args.token:
        parser.error("Pass --token or set CURIFY_EVAL_TOKEN.")

    cases_path = args.cases.resolve()
    cases = _load_cases(cases_path)
    results: List[Dict[str, Any]] = []
    headers = {"Authorization": f"Bearer {args.token}"}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=60.0) as client:
        for index, case in enumerate(cases, 1):
            started = time.perf_counter()
            try:
                response = _execute_case(
                    client,
                    case,
                    cases_path.parent,
                    args.timeout,
                    args.poll,
                )
                scored = score_case(case, response)
            except Exception as exc:
                expected = case.get("expected") or {}
                checks = {"execution": False}
                if expected.get("task_type") is not None:
                    checks["route"] = False
                scored = {
                    "id": case["id"],
                    "task_type": expected.get("task_type"),
                    "coverage": case.get("coverage", "unknown"),
                    "passed": False,
                    "checks": checks,
                    "stage_coverage": 0.0,
                    "error": str(exc)[:500],
                }
            scored["latency_seconds"] = round(time.perf_counter() - started, 3)
            results.append(scored)
            print(f"{index}/{len(cases)} {case['id']}: {'PASS' if scored['passed'] else 'FAIL'}")

    summary = aggregate_results(results)
    out_jsonl = args.out_jsonl or cases_path.with_name("runtime_eval_results.jsonl")
    out_md = args.out_md or cases_path.with_name("runtime_eval_report.md")
    with out_jsonl.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    out_md.write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Results: {out_jsonl}\nReport: {out_md}")


if __name__ == "__main__":
    main()
