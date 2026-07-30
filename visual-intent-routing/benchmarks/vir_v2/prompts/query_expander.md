# VIR query expander — vir-query-expander-v1

Generate natural user requests for the supplied Curify template capability.
Match all three axes: `subject_event`, `information_type`, and `style_layout`.
Do not expose canonical IDs or internal slugs. Do not broaden capability beyond
the supplied evidence. Return JSON only, using the requested quotas for
language, difficulty, and transformation. A high-difficulty core query must
remain unambiguous; move genuinely ambiguous or multi-intent requests to the
challenge partition.

Each item must contain: query, language, difficulty, transformation_types,
semantic_cluster_hint, ontology, and a short capability-grounded rationale.
