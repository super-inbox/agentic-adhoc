# VIR query expander — vir-query-expander-v2

Generate natural user requests for the supplied Curify template capability.
Match all three axes: `subject_event`, `information_type`, and `style_layout`.
Do not expose canonical IDs or internal slugs. Do not broaden capability beyond
the supplied evidence. Return JSON only, using the requested quotas for
language, difficulty, and transformation. A high-difficulty core query must
remain unambiguous; move genuinely ambiguous or multi-intent requests to the
challenge partition.

For an `exploration` task, keep one stable subject and user goal while leaving
the desired style/layout intentionally open. Every annotated target must remain
relevant to that core request and must introduce an evidence-backed visual-style
or layout family. Do not add unrelated targets merely to increase diversity.
Exploration records are scored separately from single-label accuracy.

Each item must contain: query, language, difficulty, transformation_types,
semantic_cluster_hint, ontology, and a short capability-grounded rationale.
