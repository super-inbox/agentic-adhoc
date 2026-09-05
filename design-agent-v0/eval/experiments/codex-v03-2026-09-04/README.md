# Codex × Brief Bank v0.3

This directory is the canonical Codex baseline for Brief Bank v0.3.

## Frozen result

- Coverage: **43/43 conditions** across 35 episodes.
- Core: 32/32 unchanged conditions carried forward from frozen v0.2;
  condition-macro interval **0.659–0.909**.
- External extension: 11/11 newly executed and independently judged;
  weighted macro **0.984**, hard-gate pass **11/11**, score+gate pass **11/11**.
- Combined condition-macro interval: **0.742–0.928**.

See [`RESULTS.md`](RESULTS.md) and [`freeze-manifest.json`](freeze-manifest.json).

## Scope

- **43 projected conditions / 35 episodes** in `briefs.v0.3.jsonl`.
- **32 core conditions** are provenance-checked carry-forward rows from the
  unchanged frozen v0.2 contract. They are never described as new calls.
- **11 external extension conditions** are newly executed here from the
  Reddit-derived, ready-to-author partition.
- Candidate: Codex CLI, `gpt-5.6-sol`, reasoning `max`, service tier `default`,
  persisted thread resume for feedback turns.
- Judge: `gemini-2.5-pro`, temperature 0, artifact-grounded prompt plus
  evaluator-computed image, mask, SVG, EPS, PDF, JSON, and trajectory facts.

`RESULTS.md` is generated only after all 11 new conditions have a completed
candidate run and a successful judge row.

## Run the 11 new conditions

```bash
node scripts/run_codex_v03.mjs \
  --case DAB-L3-RDT-001 --case DAB-L3-RDT-002 \
  --case DAB-L3-RDT-003 --case DAB-L3-RDT-004 \
  --case DAB-L3-RDT-005 --case DAB-L3-RDT-006 \
  --case DAB-L4-RDT-007 --case DAB-L4-RDT-008 \
  --case DAB-L4-RDT-009 --case DAB-L3-RDT-010 \
  --case DAB-L3-RDT-011 \
  --full-episode --workers 3 --timeout-ms 3600000 \
  --allow-model-usage --skip-completed
```

The explicit model-usage flag prevents accidental paid reruns. Failed and
timed-out attempts stay in `run-index.jsonl`; `--skip-completed` only skips a
condition after a primary completed result exists.

## Judge and freeze

Use the Codex bundled Python runtime because it contains the image stack used
by the evaluator. Install the pinned judge dependencies into the ignored
`.private` directory and provide `GEMINI_API_KEY` in the environment.

```bash
BUNDLED_PY=/path/from/codex-workspace-dependencies/python/bin/python3
"$BUNDLED_PY" -m pip install \
  --target .private/judge-python \
  -r scoring/requirements-judge.txt

PYTHONPATH=".private/judge-python:scoring" \
  "$BUNDLED_PY" scoring/judge_v03.py

PYTHONPATH=".private/judge-python:scoring" \
  "$BUNDLED_PY" scoring/validate_judge_v03.py

PYTHONPATH=".private/judge-python:scoring" \
  "$BUNDLED_PY" scoring/summarize_v03.py

"$BUNDLED_PY" scripts/freeze_v03_experiment.py
```

No API key or private trace is included in tracked results.

## Score interpretation

The v0.3 external rows receive a 0–5 score for every episode-specific rubric
dimension. The weighted score is normalized to 0–1. A benchmark pass requires:

1. every hard gate is `MET`; and
2. weighted score is at least `0.70`.

The inherited core keeps its original honest lower/upper bounds because v0.2
did not make workflow completion and recovery independently observable. The
combined 43-condition result is therefore also an interval, not a fabricated
single point.
