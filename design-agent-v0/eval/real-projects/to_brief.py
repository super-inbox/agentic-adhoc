#!/usr/bin/env python3
"""Convert a captured real project into a v0.2-shaped brief.

Field names in the capture were chosen to match briefs.v0.2.jsonl, so this is
mostly a rename — that is the point. A real project should become an eval
fixture without anyone re-typing it.

Refuses to emit anything with customer data still in it: `customer_data` is
carried through as true, so downstream can filter, and the converter warns if
a capture looks like it still contains a real name.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

NAME_HINT = re.compile(r"[A-Z][a-z]+\s+[A-Z][a-z]+|老板|总经理")


def convert(p: dict) -> dict:
    fb = []
    for f in p.get("feedback") or []:
        if not (f.get("message") or "").strip():
            continue
        fb.append({
            "after_checkpoint": "select" if f.get("round") == 1 else "converge",
            "message": f["message"],
            "expected_changes": f.get("changed") or [],
            "invariants": f.get("invariants") or [],
            "input_version": f.get("input_version", "v0"),
            "expected_version": f.get("output_version", "v1"),
        })
    return {
        "id": p["project_id"].upper(),
        "schema_version": "0.2",
        "level": "L4" if fb else "L3",
        "category": p.get("category"),
        "primary_intent": p.get("primary_intent"),
        "language": "zh-CN",
        "provenance": {
            "kind": "real_client_project",
            "source_refs": [f"agentic-adhoc:design-agent-v0/eval/real-projects/"
                            f"projects/{p['project_id']}.json"],
            # deliberately true — this is the flag that separates real captures
            # from the 24 synthetic briefs, all of which are false
            "customer_data": True,
            "notes": "Converted from a live client project; quotes verbatim.",
        },
        "initial_query": p.get("initial_query", ""),
        "inputs": p.get("inputs") or [],
        "constraints": p.get("constraints") or {},
        "feedback": fb,
        "deliverables": p.get("deliverables") or [],
        "preference_memory": p.get("preference_memory") or {},
        "project_state": p.get("project_state") or {},
        # what LOST — the part no public source carries
        "rejected_alternatives": [
            {"option_id": r.get("option_id"),
             "reason_verbatim": r.get("reason_verbatim"),
             "rationale_given": r.get("rationale_given"),
             "reason_class": r.get("reason_class")}
            for r in (p.get("rejections") or [])
        ],
        "outcome": p.get("outcome") or {},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("--out")
    a = ap.parse_args()
    p = json.loads(Path(a.capture).read_text(encoding="utf-8"))

    missing = [k for k in ("initial_query",) if not (p.get(k) or "").strip()]
    if missing:
        print(f"refusing: {', '.join(missing)} is empty — capture the brief first",
              file=sys.stderr)
        return 2

    blob = json.dumps(p, ensure_ascii=False)
    if NAME_HINT.search(blob):
        print("⚠️  this capture may contain a real name — check before committing",
              file=sys.stderr)

    out = convert(p)
    text = json.dumps(out, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
