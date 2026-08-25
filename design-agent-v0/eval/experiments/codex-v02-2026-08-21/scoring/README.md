# Deterministic audit of the Codex v0.2 runs (2026-08-25)

31 completed runs, audited with **no model and no network** —
`python3 score_selfverification.py`, output `selfverification-audit.jsonl`.

## Why this is an audit, not a score

Each run ships its own `verification.json`. Reading its `status: pass` and
calling the run scored would be **letting the candidate grade itself**. So this
independently confirms what can be confirmed mechanically, and keeps the
self-report in a separate field it can never be conflated with.

## Results

| | |
|---|---|
| Required structured artifacts present | **31/31** ✅ |
| Runs whose cited evidence all resolves | **21/31** |
| Evidence citations checked on disk | 460 |
| Named checks emitted | 253 |
| **Checks emitted with no `id` at all** | **138** |
| Contract binding | ⚠️ **unmeasurable** — see below |

**Codex reliably produces the required artifacts.** That part of §7x holds up:
`verification.json` and `trajectory.jsonl` are there every time.

**10 of 31 runs cite evidence paths that do not exist.** This is the finding the
audit exists for — a self-verification pointing at files that were never
written. It is invisible if you trust the `status` field.

## ⚠️ Contract binding cannot be measured, and that is a v0.2 spec gap

The brief's `verification_contract.checks` names checks:

    brief_adherence · deliverable_completeness · locked_invariants ·
    reference_role_compliance · state_version_continuity · feedback_delta_only ·
    resume_integrity · territory_distinctness · human_selection_used

The runs emit their own vocabulary:

    requested_delta_only · version_isolation · state_file_validity ·
    logo_preservation · product_identity_preservation · approved_copy_only

Semantically close, **lexically disjoint**. An exact-id comparison returns 0/31
on every run — which reads as total failure and is entirely an artifact of the
comparison. The first version of this scorer reported exactly that; it was wrong
and was corrected before publication.

**Nothing in v0.2 binds a run's check ids to the contract's**, so coverage is
genuinely unknown, not zero. Plus 138 checks carry no `id` field at all, so they
cannot be bound even in principle.

**Fix belongs in the spec, not the scorer:** `verification_contract` should
declare the check id vocabulary, and runs should be required to use it. Until
then "did the agent verify what it was asked to verify?" is unanswerable for
either candidate.

## Not scored here

`brief_understanding`, `revision_fidelity`, `cross_asset_consistency` need a
judge. Code cannot settle them, and pretending otherwise would repeat the
`consistency_gate` negative result. The other four rubric dimensions
(`workflow_completion`, `artifact_contract`, `recovery`, `efficiency`) are
partially covered by the run index and this audit.
