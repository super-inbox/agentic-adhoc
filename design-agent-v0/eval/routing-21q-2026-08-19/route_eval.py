"""Offline routing eval for the 21q set — no image generation, no credits.

Measures ONLY what the planner decides. P0-2 (edit intent) and P0-3 (export
step) are routing changes, so they are fully observable here. It says nothing
about brief_adherence or visual quality: those need generation.

Expected intents are assigned from the judge rationales in spec §7o, not from
the pattern under test, so this is not marking its own homework.
"""
import json, subprocess, sys, time

EXPECTED = {
    # class A — must consume the supplied source
    "AR-001": "edit", "AR-002": "edit", "AR-003": "edit",
    "AR-007": "edit", "AR-008": "edit", "AR-009": "edit",
    "TIQ-029": "edit", "TIQ-070": "edit", "TIQ-084": "edit",
    "TIQ-085": "edit", "TIQ-088": "edit", "TIQ-100": "edit",
    # no edit verb at all; documented as NOT fixed by P0-2
    "TIQ-086": "edit(known-miss)",
    # class B — needs an evaluate/rank deliverable that does not exist yet
    "AR-004": "evaluate", "AR-005": "evaluate", "AR-006": "evaluate",
    # class D — must plan a production export step
    "AR-010": "export", "AR-011": "export", "AR-012": "export",
    # ordinary generation / batch
    "TIQ-096": "generate", "TIQ-098": "generate",
}

URL = "https://www.curify-ai.com/api/design-agent/plan"

def plan(brief):
    body = json.dumps({"query": brief, "hasImage": True, "locale": "en"})
    p = subprocess.run(
        ["curl", "-s", "--max-time", "60", "-X", "POST", URL,
         "-H", "Content-Type: application/json", "-d", body],
        capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"_error": p.stdout[:160]}

cases = json.load(open("q21.json"))
rows = []
for i, c in enumerate(cases, 1):
    d = plan(c["brief"])
    if "_error" in d:
        rows.append({**c, "type": "ERROR", "tools": [], "note": d["_error"]})
    else:
        rows.append({**c,
                     "type": (d.get("routing", {}).get("deliverable") or {}).get("type"),
                     "tools": [s.get("tool_id") for s in d.get("steps", [])]})
    print(f"  {i:2}/21 {c['task_id']:9} -> {rows[-1]['type']}", flush=True)
    time.sleep(1)
json.dump(rows, open("route_results.json", "w"), ensure_ascii=False, indent=1)
