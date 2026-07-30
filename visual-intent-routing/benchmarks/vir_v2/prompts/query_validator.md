# VIR independent Gold validator — vir-query-validator-v1

Judge the proposed annotation using only the supplied capability registry and
full catalog evidence. This validator is independent from the router under
evaluation.

Answer:

1. Does the query fit the proposed capability on subject, information type,
   and layout?
2. Is another template more appropriate?
3. Is the request supported, unsupported, ambiguous, or multi-intent?
4. Is the query natural for its language label?
5. Should it be accepted, manually reviewed, or rejected?

Return JSON only with: decision, target_consistency, competing_targets,
intent_mode, language_natural, rationale. Never infer capability from a slug
alone.
