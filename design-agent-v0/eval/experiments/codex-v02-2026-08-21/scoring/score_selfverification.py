#!/usr/bin/env python3
"""Deterministic audit of Codex's v0.2 runs. No model, no network, no cost.

The point is NOT to read `verification.json` and copy its `status`. That file is
the agent's own report on its own work, so trusting it is letting the candidate
grade itself — the failure this repo has already paid for twice (a summary that
looked confident while measuring the wrong thing).

So this scores three things that can be checked mechanically:

  1. CONTRACT BINDING   ⚠️ NOT SCOREABLE, and that is the finding. The brief's
     verification_contract names checks (feedback_delta_only,
     state_version_continuity, locked_invariants ...) but the runs emit their
     own vocabulary (requested_delta_only, version_isolation,
     logo_preservation ...). Semantically close, lexically disjoint — exact-id
     matching scores 0/31 on every run, which reads as total failure and is
     purely an artifact of the comparison. Nothing in v0.2 binds a run's check
     ids to the contract's, so coverage cannot be computed at all. Reported as
     `contract_binding: "unmeasurable"`, never as a score.
  2. EVIDENCE INTEGRITY every check cites evidence_paths. Do those files exist?
     A self-verification citing files that were never written is the specific
     way a self-report goes wrong.
  3. DELIVERABLE PRESENCE the brief names required structured_artifacts. Are
     they on disk?

Self-reported status is carried through, but reported SEPARATELY from what was
independently confirmed, so the two can never be conflated.

Rubric dimensions needing judgment — brief_understanding, revision_fidelity,
cross_asset_consistency — are explicitly NOT scored here and are listed as
`needs_judge`. Pretending code can settle them would be the same overreach as
the consistency_gate negative result.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parent.parent
BRIEFS = EVAL / "brief_bank" / "briefs.v0.2.jsonl"

NEEDS_JUDGE = [
    "brief_understanding",
    "tool_execution",
    "revision_fidelity",
    "cross_asset_consistency",
]


def load_briefs():
    out = {}
    for line in BRIEFS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["id"].lower()] = r
    return out


def selected_runs(briefs: dict[str, dict]):
    """Select the latest primary completed attempt for each benchmark condition."""
    latest = {}
    for rj in sorted((EXP / "runs").rglob("result.json")):
        run_dir = rj.parent
        try:
            res = json.loads(rj.read_text(encoding="utf-8"))
        except Exception:
            continue
        if res.get("outcome") != "completed" or res.get("primary_eligible") is False:
            continue
        bid = str(res.get("base_brief_id") or "").lower()
        brief = briefs.get(bid)
        if not brief:
            continue
        condition = str(res.get("context_condition") or run_dir.parent.name)
        key = (brief["id"], condition)
        stamp = str(res.get("started_at") or run_dir.name)
        if key not in latest or stamp > latest[key][0]:
            latest[key] = (stamp, run_dir, brief)
    return [(run_dir, brief) for _, run_dir, brief in sorted(latest.values())]


def audit_run(run_dir: Path, brief: dict) -> dict:
    res = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    required_checks = set((brief.get("verification_contract") or {}).get("checks") or [])
    required_artifacts = [
        a["name"] for a in (brief.get("structured_artifacts") or []) if a.get("required")
    ]

    # every verification.json the run produced (one per version dir)
    vfiles = sorted(run_dir.glob("outputs/*/verification.json"))
    reported, passed, missing_evidence, checked_evidence = set(), set(), [], 0
    unnamed = 0
    for vf in vfiles:
        try:
            v = json.loads(vf.read_text(encoding="utf-8"))
        except Exception:
            missing_evidence.append(f"{vf.name}: unparseable")
            continue
        for c in v.get("checks") or []:
            cid = str(c.get("id"))
            if not c.get("id"):
                unnamed += 1      # a check with no id cannot be bound to anything
                continue
            reported.add(cid)
            if str(c.get("status")).lower() == "pass":
                passed.add(cid)
            for ev in c.get("evidence_paths") or []:
                checked_evidence += 1
                if not (run_dir / ev).exists():
                    missing_evidence.append(f"{cid} -> {ev}")

    present_artifacts = [
        a for a in required_artifacts
        if list(run_dir.glob(f"**/{a}")) or (run_dir / a).exists()
    ]

    return {
        "run": str(run_dir.relative_to(EXP)),
        "brief_id": brief["id"],
        "condition": run_dir.parent.name,
        "level": brief.get("level"),
        "outcome": res.get("outcome"),
        "turns": f"{res.get('completed_turns')}/{res.get('intended_turns')}",
        # 1. contract coverage — independently computed from the brief
        # See module docstring: ids are lexically disjoint from the contract,
        # so this is coverage-UNKNOWN, not coverage-zero.
        "contract_binding": "unmeasurable",
        "checks_required": len(required_checks),
        "checks_emitted": len(reported),
        "checks_unnamed": unnamed,
        # 2. evidence integrity — independently confirmed on disk
        "evidence_cited": checked_evidence,
        "evidence_missing": missing_evidence,
        # 3. deliverables
        "artifacts_required": required_artifacts,
        "artifacts_present": present_artifacts,
        "artifacts_missing": [a for a in required_artifacts if a not in present_artifacts],
        # self-report, kept separate on purpose
        "self_reported_pass": sorted(passed & required_checks),
        "needs_judge": NEEDS_JUDGE,
    }


def main() -> int:
    briefs = load_briefs()
    rows = []
    for run_dir, brief in selected_runs(briefs):
        rows.append(audit_run(run_dir, brief))

    out = HERE / "selfverification-audit.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                   encoding="utf-8")

    scored = [r for r in rows if "error" not in r]
    clean_ev = sum(1 for r in scored if not r["evidence_missing"])
    all_art = sum(1 for r in scored if not r["artifacts_missing"])
    print(f"completed runs audited: {len(scored)}")
    print(f"  contract binding           : UNMEASURABLE — run check-ids are")
    print(f"                               lexically disjoint from the contract's")
    print(f"  checks emitted (named)     : {sum(r['checks_emitted'] for r in scored)}")
    print(f"  checks with NO id          : {sum(r['checks_unnamed'] for r in scored)}")
    print(f"  evidence paths all resolve : {clean_ev}/{len(scored)}")
    print(f"  required artifacts present : {all_art}/{len(scored)}")
    print(f"  evidence citations checked : {sum(r['evidence_cited'] for r in scored)}")
    print(f"\nwrote {out.relative_to(EVAL)}")
    print(f"NOT scored here (needs a judge): {', '.join(NEEDS_JUDGE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
