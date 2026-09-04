#!/usr/bin/env python3
"""Score the completed Codex v0.2 runs against the v0.2 rubric — as far as the
runs actually permit. No model, no network.

HEADLINE: most of the rubric is NOT scoreable from these runs, and the reason is
a spec gap, not missing effort.

  dimension                 status
  artifact_contract         SCOREABLE   required files on disk
  efficiency                SCOREABLE   completed vs intended turns
  workflow_completion       PROXY ONLY  see below
  recovery                  NOT OBSERVABLE
  brief_understanding       NEEDS JUDGE
  tool_execution            NEEDS JUDGE (L3 only)
  revision_fidelity         NEEDS JUDGE
  cross_asset_consistency   NEEDS JUDGE

Weights VARY BY BRIEF, so no fixed table applies. Each row carries its own
brief's weights; the summary prints a spread rather than one number.

`expected_workflow` names checkpoints (understand / diverge / cluster / select /
converge / deliver) but nothing requires a run to emit them, and the published
trajectory carries Codex-native events (codex.command, codex.agent_message)
instead. So checkpoint attainment cannot be observed. The same gap already
broke verification-check binding: v0.2 specifies vocabularies it never obliges
the run to use.

The proxy used for workflow_completion is output VERSION progression — v0, v1,
v2 directories — because a converge/revise cycle must produce a new version.
It is a floor, not the dimension.

So roughly a quarter to two-fifths of rubric weight is machine-scoreable today,
a further 0.15-0.45 needs a judge, and the remainder is unobservable until the
spec obliges runs to emit the checkpoint and check vocabularies it names. That
split is the finding.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parent.parent
BRIEFS = EVAL / "brief_bank" / "briefs.v0.2.jsonl"

SCOREABLE = {"artifact_contract", "efficiency"}
PROXY = {"workflow_completion"}
NEEDS_JUDGE = {
    "brief_understanding",
    "tool_execution",
    "revision_fidelity",
    "cross_asset_consistency",
}
UNOBSERVABLE = {"recovery"}


def selected_runs(briefs: dict[str, dict]):
    """Select the latest primary completed attempt for each benchmark condition."""
    latest = {}
    for rj in sorted((EXP / "runs").rglob("result.json")):
        try:
            res = json.loads(rj.read_text(encoding="utf-8"))
        except Exception:
            continue
        if res.get("outcome") != "completed" or res.get("primary_eligible") is False:
            continue
        brief = briefs.get(str(res.get("base_brief_id") or "").lower())
        if not brief:
            continue
        condition = str(res.get("context_condition") or rj.parent.parent.name)
        key = (brief["id"], condition)
        stamp = str(res.get("started_at") or rj.parent.name)
        if key not in latest or stamp > latest[key][0]:
            latest[key] = (stamp, rj.parent, brief, res)
    return [(run, brief, res) for _, run, brief, res in sorted(latest.values())]


def main() -> int:
    briefs = {}
    for line in BRIEFS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            briefs[r["id"].lower()] = r

    rows = []
    for run, b, res in selected_runs(briefs):
        weights = (b.get("rubric") or {}).get("checkpoint_weights") or {}

        # artifact_contract — required structured artifacts on disk
        req = [a["name"] for a in (b.get("structured_artifacts") or []) if a.get("required")]
        have = [a for a in req if list(run.glob(f"**/{a}"))]
        artifact = len(have) / len(req) if req else None

        # efficiency — did it finish the turns it intended, without overrun
        ct, it = res.get("completed_turns"), res.get("intended_turns")
        efficiency = (1.0 if ct == it else max(0.0, 1 - abs((ct or 0) - (it or 1)) / max(it or 1, 1))) \
            if ct is not None and it else None

        # workflow_completion PROXY — version progression only
        versions = sorted({p.name for p in (run / "outputs").glob("v*") if p.is_dir()})
        expected_cps = len(b.get("expected_workflow") or [])
        proxy = min(1.0, len(versions) / max(1, (it or 1)))

        scored_w = sum(weights.get(k, 0) for k in SCOREABLE)
        rows.append({
            "run": str(run.relative_to(EXP)),
            "brief_id": b["id"], "condition": run.parent.name, "level": b.get("level"),
            "artifact_contract": artifact,
            "efficiency": efficiency,
            "workflow_completion_proxy": proxy,
            "versions": versions,
            "expected_checkpoints": expected_cps,
            "checkpoints_observable": False,
            "partial_weighted": round(
                (artifact or 0) * weights.get("artifact_contract", 0)
                + (efficiency or 0) * weights.get("efficiency", 0), 4),
            "weight_scored": round(scored_w, 2),
            "weight_needs_judge": round(sum(weights.get(k, 0) for k in NEEDS_JUDGE), 2),
            "weight_unobservable": round(
                sum(weights.get(k, 0) for k in UNOBSERVABLE | PROXY), 2),
        })

    out = HERE / "rubric-v02-partial.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                   encoding="utf-8")
    n = len(rows)
    mean = lambda k: round(sum(r[k] or 0 for r in rows) / n, 3) if n else 0
    print(f"runs scored: {n}")
    print(f"  artifact_contract        {mean('artifact_contract')}   (weight 0.20)")
    print(f"  efficiency               {mean('efficiency')}   (weight 0.05)")
    print(f"  workflow_completion*     {mean('workflow_completion_proxy')}   PROXY (weight 0.20)")
    print(f"  partial weighted score   {mean('partial_weighted')}  "
          f"(each run against its OWN brief's weights)")
    import collections
    print("\n  weight scored (spread)      "
          + str(dict(collections.Counter(r["weight_scored"] for r in rows))))
    print("  weight needing judge        "
          + str(dict(collections.Counter(r["weight_needs_judge"] for r in rows))))
    print("  NOTE: rubric weights differ per brief; there is no single total.")
    print(f"\nwrote {out.relative_to(EVAL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
