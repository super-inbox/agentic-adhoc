#!/usr/bin/env python3
"""Judge the three v0.2 rubric dimensions code cannot settle.

STATUS 2026-08-25: the violation-first prompt below WORKS but the run is
INCOMPLETE — 8 of 31 scored, the other 23 lost to a Gemini monthly spending cap
(429 RESOURCE_EXHAUSTED). Output: rubric-v02-judged-v2.jsonl.

  dimension                v1 (score-first)      v2 (violation-first, n=8)
  brief_understanding      {5:31}  sd 0.00       {1:1, 5:7}  sd 1.32
  cross_asset_consistency  {5:31}  sd 0.00       {2:1, 5:6}  sd 1.05
  violation ledger         (none asked for)      95 MET · 7 CANNOT_TELL · 2 VIOLATED

⚠️ Do NOT compute weighted totals from the 8. They are whatever completed before
quota ran out — alphabetically first, not a random sample — and
revision_fidelity has n=1. The method is validated; the coverage is not.

The judge is resumable (it skips runs already in the output file), so finishing
costs ~23 calls once quota resets. No regeneration needed.

SEQUENCING MISTAKE WORTH REMEMBERING: v1 was run over all 31 before anyone
checked whether it discriminated. Those 31 calls returned all-5s and consumed
the quota that v2 then needed. Validate a judge on 3-5 runs and check the score
variance BEFORE spending a full pass on it.

---- v1 post-mortem, kept because the diagnosis is what produced v2 ----
The first version DID NOT DISCRIMINATE: 5/5 on every dimension of every run,
sd 0.00 throughout. A judge that agrees with everything measures nothing.

Do not read the 5s as "Codex was perfect". The same model family scored
Curify 0.100 and Codex 0.322 on brief adherence in the 21q experiment, so it is
capable of separating candidates; the difference is what it was given.

Why this prompt failed, so the next attempt does not repeat it:
  * It supplied the brief and asked for a 0-5 score with anchors only at the
    ends. Nothing told the judge what a 3 looks like.
  * It never passed `negative_constraints` or the rubric `hard_gates`. judge-v2
    on the 21q set works because it checks output against explicit prohibitions
    ("Do not ignore or replace the supplied source image") — violations are
    findable; "is this good?" is not.
  * It asked for a score first rather than for violations first. Ask for a
    verdict and a model reaches for the middle-to-top of the scale.

Next attempt: pass negative_constraints + hard_gates, require the judge to
enumerate violations WITH evidence paths before scoring, and score only from
the violations it found. Keep the not_applicable handling below — that part
worked (7 single-turn runs correctly returned null for revision_fidelity
instead of being defaulted to a number).

---- original design notes ----

  brief_understanding      did it do what the brief asked, incl. unstated constraints
  revision_fidelity        did it change ONLY what feedback asked, preserving invariants
  cross_asset_consistency  do the deliverables belong to one system

Scores 0-5 per the rubric, converted to 0-1 for the weighted total.

Design notes, because a judge is easy to get wrong:
  * The judge sees the BRIEF and the RUN OUTPUTS. It does NOT see the agent's own
    verification.json — that file is the candidate's self-report and feeding it in
    would let the candidate argue its own case.
  * revision_fidelity is scored ONLY on multi-turn runs, and marked
    not_applicable elsewhere rather than defaulted to a number. A single-turn run
    has no revision to be faithful to; scoring it 0 or 5 would both be lies.
  * Images are attached where present, capped per run, because
    cross_asset_consistency is a visual claim and judging it from filenames is
    the failure this repo already documented in consistency_gate.
"""
from __future__ import annotations
import base64, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parent.parent
BRIEFS = EVAL / "brief_bank" / "briefs.v0.2.jsonl"
MODEL = os.environ.get("JUDGE_MODEL", "gemini-2.5-pro")
MAX_IMAGES = int(os.environ.get("JUDGE_MAX_IMAGES", "6"))
TEXT_CAP = 4000

DIMS = ["brief_understanding", "revision_fidelity", "cross_asset_consistency"]

PROMPT = """You are auditing one run of a design-agent benchmark for CONTRACT
VIOLATIONS. Your job is to find what was broken, not to award marks.

Work in this order and do not skip step 1.

STEP 1 — For every item below, decide VIOLATED / MET / CANNOT_TELL. A claim of
MET requires you to name the artifact that shows it. CANNOT_TELL is a valid and
expected answer when the deliverables do not contain the evidence.

HARD GATES (breaking any one of these is disqualifying)
{hard_gates}

HARD CONSTRAINTS
{hard_constraints}

NEGATIVE CONSTRAINTS (things that must NOT appear)
{negative_constraints}

DELIVERABLE REQUIREMENTS (several are countable — count them)
{deliverable_reqs}

LOCKED INVARIANTS (must survive every revision)
{invariants}

CLIENT FEEDBACK PER TURN (empty = single turn, no revision happened)
{feedback}

BRIEF
{brief}

RUN DELIVERABLES (text extracts; images attached separately)
{outputs}

STEP 2 — Score ONLY from what step 1 found. Anchors:
  5 = no violations, and the evidence is present to show it
  4 = only soft-preference misses
  3 = one requirement partly unmet, or key evidence absent (CANNOT_TELL on a
      countable requirement scores here, not higher)
  2 = a stated requirement clearly unmet
  1 = a hard constraint or negative constraint broken
  0 = the brief was not addressed
If a dimension does not apply (no revision occurred; only one asset exists),
return null — do not substitute a number.

Return ONLY json:
{{"violations":[{{"item":"...","verdict":"VIOLATED|MET|CANNOT_TELL","evidence":"path or quote"}}],
  "brief_understanding":{{"score":n,"why":"..."}},
  "revision_fidelity":{{"score":n|null,"why":"..."}},
  "cross_asset_consistency":{{"score":n|null,"why":"..."}}}}"""


def collect(run: Path):
    texts, images = [], []
    out = run / "outputs"
    if out.is_dir():
        for f in sorted(out.rglob("*")):
            if not f.is_file():
                continue
            if f.name == "verification.json":
                continue                      # candidate's self-report: excluded
            sfx = f.suffix.lower()
            if sfx in (".md", ".json", ".txt") and len(texts) < 12:
                try:
                    texts.append(f"--- {f.relative_to(out)}\n"
                                 + f.read_text(encoding="utf-8")[:TEXT_CAP])
                except Exception:
                    pass
            elif sfx in (".png", ".jpg", ".jpeg") and len(images) < MAX_IMAGES:
                try:
                    b = f.read_bytes()
                    if len(b) < 5_000_000:
                        images.append((f.name, sfx, base64.b64encode(b).decode()))
                except Exception:
                    pass
    for t in sorted(run.glob("turns/*/final-response.txt")):
        try:
            texts.append(f"--- {t.parent.name} final response\n"
                         + t.read_text(encoding="utf-8")[:TEXT_CAP])
        except Exception:
            pass
    return texts, images


def judge(client, brief: dict, run: Path):
    fb = brief.get("feedback") or []
    cons = brief.get("constraints") or {}
    rub = brief.get("rubric") or {}
    prompt = PROMPT.format(
        hard_gates=json.dumps(rub.get("hard_gates") or [], ensure_ascii=False),
        hard_constraints=json.dumps(cons.get("hard") or [], ensure_ascii=False),
        negative_constraints=json.dumps(cons.get("negative") or [], ensure_ascii=False),
        deliverable_reqs=json.dumps(
            [{"id": d.get("id"), "count": d.get("count"),
              "requirements": d.get("requirements")}
             for d in (brief.get("deliverables") or [])], ensure_ascii=False)[:2000],
        invariants=json.dumps(
            (brief.get("project_state") or {}).get("locked_invariants") or [],
            ensure_ascii=False),
        feedback=json.dumps(
            [{"after": f.get("after_checkpoint"), "msg": f.get("message"),
              "invariants": f.get("invariants")} for f in fb],
            ensure_ascii=False)[:1500] if fb else "(none — single turn)",
        brief=brief.get("initial_query", "")[:1200],
        outputs="\n\n".join(collect(run)[0])[:24000] or "(no text deliverables)")
    parts = [{"text": prompt}]
    for name, sfx, b64 in collect(run)[1]:
        parts.append({"inline_data": {
            "mime_type": "image/png" if sfx == ".png" else "image/jpeg", "data": b64}})
    resp = client.models.generate_content(
        model=MODEL, contents=[{"role": "user", "parts": parts}])
    raw = (resp.text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json").strip()
    return json.loads(raw)


def main() -> int:
    from google import genai
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY not set", file=sys.stderr)
        return 2
    client = genai.Client(api_key=key)

    briefs = {}
    for line in BRIEFS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            briefs[r["id"].lower()] = r

    runs = []
    for rj in sorted((EXP / "runs").rglob("result.json")):
        res = json.loads(rj.read_text(encoding="utf-8"))
        if res.get("outcome") == "completed":
            b = briefs.get(str(res.get("base_brief_id") or "").lower())
            if b:
                runs.append((rj.parent, b, res))

    out = HERE / "rubric-v02-judged-v2.jsonl"
    done = set()
    if out.exists():                                   # resumable
        for l in out.read_text(encoding="utf-8").splitlines():
            if l.strip():
                done.add(json.loads(l)["run"])

    with out.open("a", encoding="utf-8") as fh:
        for i, (run, brief, res) in enumerate(runs, 1):
            rid = str(run.relative_to(EXP))
            if rid in done:
                continue
            try:
                v = judge(client, brief, run)
                err = None
            except Exception as e:
                v, err = {}, f"{type(e).__name__}: {e}"[:180]
            row = {"run": rid, "brief_id": brief["id"], "condition": run.parent.name,
                   "level": brief.get("level"), "turns": res.get("completed_turns"),
                   "model": MODEL, "error": err}
            for d in DIMS:
                row[d] = (v.get(d) or {}).get("score")
                row[d + "_why"] = (v.get(d) or {}).get("why")
            row["violations"] = v.get("violations") or []
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"  {i}/{len(runs)} {rid[:44]} -> "
                  + " ".join(f"{d[:4]}={row[d]}" for d in DIMS)
                  + (f" ERR {err}" if err else ""), flush=True)
            time.sleep(1)
    print(f"\nwrote {out.relative_to(EVAL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
