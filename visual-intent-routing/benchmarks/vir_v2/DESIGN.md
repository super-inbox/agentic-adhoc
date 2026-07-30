# Visual Intent Routing v2 design

## Existing system

The standalone v1 benchmark freezes 293 catalog records, including 227
`allow_generation` templates, 3,115 inspirations, bilingual descriptions, a
three-axis taxonomy, and a mined capability KB. Its 58-query
`vir_routing_gold.json` supports acceptable target sets and content gaps, but is
explicitly a Claude draft awaiting human sign-off. The v1 offline Path A router
is lexical; optional Path B reproduces an older whole-catalog LLM matcher.

The current frontend has moved to multi-route retrieval followed by a bounded
`gpt-4o-mini` reranker. Its HTTP response is `{matches: [...]}` with IDs,
confidence, parameters, and reasons. The production router depends on provider
credentials and is therefore not used by unit tests.

At inspection time, the moving frontend catalog contained 332 templates (233
with `allow_generation`), versus 293/227 in the intentionally frozen benchmark
snapshot. Content-gap labels were checked against the moving catalog as well as
the frozen capability KB. The point-in-time results, source hashes, adjacent
capabilities, and functional-output boundaries are frozen in
`registry/full_catalog_gap_audit.json`.

## Reuse

- Frozen catalog, bilingual descriptions, inspirations, capability KB, and
  taxonomy remain the reproducible evidence snapshot.
- Canonical IDs are verified against the frozen catalog.
- The normalized adapter accepts the current production HTTP shape.
- v1 files and labels remain unchanged.

## Missing pieces addressed by v2

V1 has no versioned per-record JSONL schema, reproducible expansion, independent
validation pipeline, leakage-safe split, provider-neutral adapter contract,
abstention classification metrics, robustness/slice metrics, regression
comparison, or complete report artifacts. V2 adds these as CommonJS modules and
a single resumable CLI, following this repository's Node conventions.

## Architecture

`seeds → registry → expansion → deterministic/optional LLM validation →
cluster-aware split → adapter → normalized predictions → deterministic metrics
→ reports/comparison`.

Rule expansion is deterministic and fixture-backed. Optional LLM generation and
validation use separate prompts, versioned prompt hashes, on-disk caches,
schema-constrained JSON parsing, retries, resume, batch and dry-run controls.
No network call occurs unless `--provider=llm` or an external adapter is
explicitly selected.

Character n-gram similarity is the dependency-free fallback for collision,
near-duplicate, and leakage checks. The interface can be replaced by an
embedding implementation later. Routing equality is always exact canonical-ID
equality and never an LLM judgment.

## Compatibility and assumptions

- Supplied v2 anchors are authoritative for this benchmark, even when v1 listed
  extra acceptable targets for the same terse query. Anchors are stored
  verbatim and converted traceably to approved JSONL records.
- Generated records are candidates. Deterministically clean core records may be
  `auto_accepted`, but are not called manually approved Gold. Challenge and
  content-gap candidates default to `needs_review`.
- The benchmark scope is text query → text-only generatable template or
  abstention. Reference-image workflows are outside this routing target.
- The full-generation default requests 650 candidate records. Quality checks may
  reject or queue records; counts are never padded after validation.
- A future catalog refresh must rerun the content-gap audit; a no-match label is
  not assumed to remain true merely because this point-in-time audit passed.

## Gold-label conflict audit

The current catalog has no dedicated text-only ID/passport-photo generator. It
does contain an upload-only `template-portrait-retouching-blueprint` whose
description can accept an ID photo as an input portrait type, and several
search aliases loosely mention ID photos. The current production planning code
explicitly returns no text-only generation direction for `证件照` because a
portrait upload is required. Therefore `vir-s16` remains a valid abstention for
this benchmark scope, while the registry records the reference-image boundary
as a possible future scope conflict—not a silent relabel.

## Difficulty rubric

- **Low:** explicit task, specific subject, named artifact, little distraction.
- **Medium:** one implicit axis or an audience/style/aspect/conversational
  modifier.
- **High:** terse, code-switched, noisy, multi-clause, or near a boundary while
  retaining one defensible core target. Truly ambiguous requests are challenge
  records.

The intended core language mix is 40% Chinese, 40% English, and 20% natural
mixed Chinese-English; low/medium/high are balanced within each target.
