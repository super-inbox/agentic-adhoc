# Codex planner-only routing — results

Dataset: 118 rows · `d64860e5ea095cbfc061b4fa38f7c8e32bd83ea8cfb6b9755992e5d7319a61a4`

Candidate: `{"agent": "codex-cli", "cli_version": "codex-cli 0.146.0", "model": "gpt-5.6-sol", "reasoning_effort": "max", "sandbox": "read-only", "session_mode": "ephemeral"}`

The two layers use different gold semantics and are intentionally not merged into one score.

## Reliability

- Selected valid runs: **118/118**
- First-attempt completion: **118/118**
- Retried cases: **0**
- Planner-only invariant (no tool call): **100.0%**

## routing_benchmark (100)

| Metric | Score |
|---|---:|
| Intent any-hit | 98.0% |
| Intent exact set | 50.0% |
| Intent macro F1 | 80.9% |
| Template top-1 (77 labeled) | 71.4% |
| Template any-hit (77 labeled) | 100.0% |
| Template macro recall (77 labeled) | 87.0% |
| Gap abstention (23 empty-gold) | 0.0% |
| Strict joint pass | 75.0% |

## agent_route (18)

Exact route accuracy: **88.9%**.

## Same-dataset matcher context

| Metric | Existing production matcher | Codex planner |
|---|---:|---:|
| Intent any-hit / overlap | 34.4% | 98.0% |
| Candidate any-hit (77) | 33.8% | 100.0% |
| Candidate macro recall (77) | 27.3% | 87.0% |
| Gap abstention (23) | 8.7% | 0.0% |

The comparison uses the existing frozen matcher output, but Codex was explicitly given the closed 35-ID catalog; treat it as a planner upper-bound, not a drop-in latency/cost comparison.

## Cost/latency observability

- Sum of independent case latency: **1260.6s**; mean **10.7s**.
- CLI usage counters: `{'input_tokens': 1780950, 'cached_input_tokens': 693248, 'cache_write_input_tokens': 0, 'output_tokens': 41626, 'reasoning_output_tokens': 15845}`.
- Most-selected templates: `[{'template_id': 'template-product-theme-promotional-poster', 'count': 76}, {'template_id': 'template-product-poster', 'count': 61}, {'template_id': 'template-food-product-packaging-design', 'count': 25}]`.

## Caveats

- Reference presence and roles are passed, but not pixels; this isolates planner routing.
- The 100-query intent labels and template candidates are weak/multi-valid gold, so any-hit and recall are more informative than exact-set accuracy.
- A gold-empty template list is treated as an abstention target, not proof that no acceptable design workflow exists.

## Agent-route misses

- `AR-013` expected `creative_explore`, predicted `ask`
- `AR-014` expected `creative_explore`, predicted `ask`
