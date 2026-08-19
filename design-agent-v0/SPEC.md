# Design Agent v0 — Spec

> ## ⛔ This file is not the spec. It is a pointer.
>
> **Single source of truth:** `curify-studio/docs/design-agent-v0-spec.md`
>
> Read that. Do not add sections here, and do not treat anything below as current.

## Why this file no longer holds the spec

It used to carry a full copy, and the copy went stale the way copies do. At the
point this pointer replaced it, the fork was **179 lines frozen at §1–§7**,
while the canonical document was **~1,690 lines through §7s** — the fork was
missing, among others:

| Section | Subject |
|---|---|
| §7c–§7h | AS-BUILT audit; deliverable-type routing; the two-implementations reconciliation (`agent_runtime` is canonical) |
| §7i–§7j | workflow / trajectory / preference data layering; one-click workflows |
| §7k–§7n | eval status vs L1–L5; the 176-case inventory; 21q deterministic results |
| §7o | first 21q quality scores + three harness bugs + the brief_adherence decomposition |
| §7p–§7q | Reddit demand mining (362 posts); the three-evidence-chain synthesis |
| §7r–§7s | Design Context Layer; corpus-source findings and the ZCOOL PoC |

Anyone reading the old copy would have concluded the project was still at "v0
scope & phasing" and missed every measured result. A stale fork of a live
document is worse than no fork: it is confidently wrong, and it is discoverable.

## Which repo holds what

| Repo | Holds |
|---|---|
| **curify-studio** (+ curify-frontend) | Production code, and the canonical design/strategy docs — including this spec |
| **agentic-adhoc** (this repo) | **Eval, data, trajectory**: benchmarks, datasets, experiment snapshots, factory exporters, integration patches |

So the spec lives with the product it specifies, and the evidence it cites lives
here. When they disagree, the spec is authoritative for intent and this repo is
authoritative for what was actually measured.

## The evidence in this repo that the spec cites

| Path | Cited by |
|---|---|
| [`eval/experiments/curify-vs-codex-21q-2026-08-16/`](eval/experiments/curify-vs-codex-21q-2026-08-16/) | §7n, §7o — deterministic coverage, the corrected quality scores, and `RESULTS-2026-08-18.md` |
| [`eval/experiments/canva-vs-curify-canary-2026-08-14/`](eval/experiments/canva-vs-curify-canary-2026-08-14/) | §7o — the canary that invented a jacket |
| [`eval/`](eval/) | §7k, §7l — case inventory and rerun records |
| [`factory/`](factory/) | §4, §7q-C — sticker/acrylic exporters behind the production moat |
| [`benchmarks/creative-exploration/`](benchmarks/creative-exploration/) | §3b — the FaCeo packaging vote case |
