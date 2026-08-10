# Visual Intent Routing v2 evaluation report

## 1. Benchmark and run metadata

- Benchmark: `vir-v2`
- Router adapter: `mock-capability-lexical`
- Records evaluated: 696
- Run configuration hash: `f808ae9cd4416d2653e67d8478274cb08522f279d91270a758c59f2ef6a84649`
- Locked test SHA256: `8850de17ebf2dd02ad540e57ff7687307979319bce3a81137b725f88b057a687`
- Exploration split SHA256: `fddf895870376a5d380a87cc346803307d1e7b97398d79e5f363ad102af3b63c`
- Registry version: `vir-capabilities-2026-07-29-exploration-v1`

This report evaluates query-to-template routing only. It does not judge generated-image quality.

## 2. Dataset counts and distributions

- Requested candidates: 680
- Generated candidates: 680
- Rejected: 0
- Needs review: 380
- Auto-accepted: 300
- Manually approved anchors: 16
- Exploration split: 30

| Dimension | Value | Count |
|---|---|---:|
| partition | core | 450 |
| partition | content_gap | 80 |
| partition | challenge | 120 |
| partition | exploration | 30 |
| target | template-vocabulary | 55 |
| target | template-english-grammar-wordlist-infographic | 48 |
| target | template-interior-design-mood-board-generator | 64 |
| target | template-education-card | 68 |
| target | template-fandom-character-grid-poster | 55 |
| target | template-lifestyle-watercolor-infographic | 62 |
| target | template-travel | 41 |
| target | template-intangible-heritage | 47 |
| target | template-recipe | 45 |
| target | template-mbti-generic | 51 |
| target | template-species-science | 63 |
| target | template-figure-principles-infographic | 41 |
| target | template-product-poster | 50 |
| target | template-fashion-inspired-gown-design-sheet | 33 |
| target | template-mbti-personality-compatibility-infographic | 45 |
| target | __none__ | 80 |
| language | zh | 250 |
| language | en | 270 |
| language | mixed | 160 |
| difficulty | low | 170 |
| difficulty | medium | 210 |
| difficulty | high | 300 |
| core_target | template-vocabulary | 30 |
| core_target | template-english-grammar-wordlist-infographic | 30 |
| core_target | template-interior-design-mood-board-generator | 30 |
| core_target | template-education-card | 30 |
| core_target | template-fandom-character-grid-poster | 30 |
| core_target | template-lifestyle-watercolor-infographic | 30 |
| core_target | template-travel | 30 |
| core_target | template-intangible-heritage | 30 |
| core_target | template-recipe | 30 |
| core_target | template-mbti-generic | 30 |
| core_target | template-species-science | 30 |
| core_target | template-figure-principles-infographic | 30 |
| core_target | template-product-poster | 30 |
| core_target | template-fashion-inspired-gown-design-sheet | 30 |
| core_target | template-mbti-personality-compatibility-infographic | 30 |
| core_language | zh | 180 |
| core_language | en | 180 |
| core_language | mixed | 90 |
| core_difficulty | low | 150 |
| core_difficulty | medium | 150 |
| core_difficulty | high | 150 |
| transformation_type | different_example | 210 |
| transformation_type | explicit_artifact | 170 |
| transformation_type | paraphrase | 210 |
| transformation_type | conversational | 170 |
| transformation_type | audience_modifier | 150 |
| transformation_type | style_modifier | 75 |
| transformation_type | aspect_ratio_modifier | 75 |
| transformation_type | implicit_intent | 150 |
| transformation_type | code_switch | 100 |
| transformation_type | layout_modifier | 75 |
| transformation_type | boundary_nearby | 150 |
| transformation_type | underspecified | 120 |
| transformation_type | typo_noise | 75 |
| transformation_type | unsupported_visual_request | 60 |
| transformation_type | clean | 40 |
| transformation_type | noisy | 40 |
| transformation_type | boundary_case | 60 |
| transformation_type | ambiguous_intent | 60 |
| transformation_type | conflicting_modifier | 40 |
| transformation_type | multi_intent | 60 |
| transformation_type | multi_clause | 40 |
| transformation_type | paired_artifacts | 48 |
| transformation_type | supported_plus_unsupported | 12 |
| transformation_type | open_ended_exploration | 30 |
| transformation_type | multiple_visual_directions | 30 |
| transformation_type | style_unspecified | 20 |
| validation_status | auto_accepted | 300 |
| validation_status | needs_review | 380 |

## 3. Validation warnings

- Schema errors: 0
- Rejected: 0
- Needs human review: 380
- Auto-accepted (not human-approved): 300
- Near-duplicate pairs: 32
- Content-gap catalog-collision warnings: 0
- Exploration taxonomy conflicts: 0
- Full-catalog gap audit: vir-gap-audit-2026-07-29 (332 templates; 0 unaudited records)
- Balance warnings: none

## 4. Primary metrics

- Positive top-1 exact accuracy: 24.30% (95% CI 20.62%–28.40%; n=465)
- Macro top-1 across templates: 0.2430
- Overall exact accuracy including no-match: 35.53% (95% CI 31.63%–39.63%; n=546)
- Recall@3: 24.52% (95% CI 20.83%–28.62%; n=465)
- Recall@5: 24.52% (95% CI 20.83%–28.62%; n=465)
- MRR: 0.2441

## 5. Content-gap results

- Abstention precision: 0.1875
- Abstention recall: 1.0000
- Abstention F1: 0.3158
- False-routing rate: 0.00% (95% CI 0.00%–4.53%; n=81)
- False-abstention rate: 75.48% (95% CI 71.38%–79.17%; n=465)
- Match-confidence AUROC / AUPRC: 0.7817 / 0.9550

## 6. Robustness

- Semantic-cluster consistency: 0.4133
- Translation consistency: 0.4133
- Paraphrase consistency: 0.4133
- Typo/noise accuracy: 0.0933
- Explicit-to-implicit drop: -0.1267

## 7. Language and difficulty gaps

- Language accuracy: `{"zh":0,"en":0.5789473684210527,"mixed":0.03333333333333333}`
- Language gap: 0.5789
- Difficulty accuracy: `{"low":0.23026315789473684,"medium":0.3875,"high":0.10457516339869281}`
- Low-to-high change: -0.1257

## 8. Per-template results

See `slice_metrics.csv` rows where `dimension=template` for full counts and Wilson intervals.

## 9. Top confusion pairs

| Gold | Predicted | Count |
|---|---|---:|
| template-interior-design-mood-board-generator | __abstain__ | 27 |
| template-recipe | __abstain__ | 27 |
| template-education-card | __abstain__ | 26 |
| template-fandom-character-grid-poster | __abstain__ | 26 |
| template-product-poster | __abstain__ | 26 |
| template-fashion-inspired-gown-design-sheet | __abstain__ | 25 |
| template-intangible-heritage | __abstain__ | 24 |
| template-species-science | __abstain__ | 24 |
| template-travel | __abstain__ | 24 |
| template-mbti-generic | __abstain__ | 22 |
| template-mbti-personality-compatibility-infographic | __abstain__ | 21 |
| template-english-grammar-wordlist-infographic | __abstain__ | 20 |
| template-figure-principles-infographic | __abstain__ | 20 |
| template-lifestyle-watercolor-infographic | __abstain__ | 20 |
| template-vocabulary | __abstain__ | 19 |

## 10. False routing examples

_None._

## 11. False abstention examples

| Query | Lang / difficulty | Transformations | Ontology | Gold | Predicted ranking | Confidence / closest competitor | Seed / status |
|---|---|---|---|---|---|---|---|
| 单词 | zh / high | manual_anchor | language vocabulary on a chosen topic / bilingual vocabulary learning / illustrated card grid or visual guide | template-vocabulary | ABSTAIN | 0 / template-education-card | vir-s01 / approved |
| homophones and homonyms | en / medium | manual_anchor | English confusing word relationships / definition and distinction / boxed educational word-list infographic | template-english-grammar-wordlist-infographic | ABSTAIN | 0.036649 / template-english-grammar-wordlist-infographic | vir-s02 / approved |
| 家居装饰 | zh / medium | manual_anchor | interior space design / style and material inspiration / interior mood board | template-interior-design-mood-board-generator | ABSTAIN | 0 / template-education-card | vir-s03 / approved |
| 趣味经济学知识科普 | zh / medium | manual_anchor | general educational topic / accessible explanation and key facts / modular 3:4 knowledge card infographic | template-education-card | ABSTAIN | 0.003012 / template-education-card | vir-s04 / approved |
| chiikawa | en / medium | manual_anchor | fandom or themed character ensemble / character collection and showcase / vertical cinematic character grid poster | template-fandom-character-grid-poster | ABSTAIN | 0.011864 / template-fandom-character-grid-poster | vir-s05 / approved |
| cozy reading aesthetic | en / medium | manual_anchor | cozy everyday lifestyle / tips, habits, or aesthetic inspiration / warm watercolor infographic poster | template-lifestyle-watercolor-infographic | ABSTAIN | 0.042991 / template-lifestyle-watercolor-infographic | vir-s06 / approved |
| remote destination | en / high | manual_anchor | destination trip / itinerary and route planning / cute hand-drawn map with daily blocks | template-travel | ABSTAIN | 0.031359 / template-travel | vir-s07 / approved |
| paper cutting | en / medium | manual_anchor | traditional heritage craft / history, process, meaning, and preservation / dense A3 heritage information board | template-intangible-heritage | ABSTAIN | 0.023009 / template-intangible-heritage | vir-s08 / approved |
| cuban sandwich recipe poster | en / low | manual_anchor | named dish / ingredients and cooking instructions / food-photography recipe poster | template-recipe | ABSTAIN | 0.055762 / template-recipe | vir-s09 / approved |
| marvel mbti character chart 16 types | en / medium | manual_anchor | MBTI types or MBTI-mapped character set / personality classification and behavior comparison / labeled cartoon multi-character chart | template-mbti-generic | ABSTAIN | 0.057878 / template-mbti-generic | vir-s10 / approved |

## 12. Ambiguous and multi-intent challenges

- Ambiguous acceptable-set match: 66.67% (95% CI 54.06%–77.27%; n=60)
- Ambiguous abstention: 33.33% (95% CI 22.73%–45.94%; n=60)
- Multi exact set match: 0.00% (95% CI 0.00%–6.02%; n=60)
- Multi set precision / recall / F1: 0.2267 / 0.6000 / 0.3270

Challenge results are excluded from primary core accuracy.

## 13. Style exploration

- Relevant Effective Style Count@3: 0.244 effective styles per query (95% CI 0.078–0.422; n=30)
- Mean relevance@3: 13.33% (95% CI 4.44%–22.81%; n=30)
- Distinct relevant style families: 0.400 style families per query (95% CI 0.167–0.667; n=30)
- Distinct relevant layout families: 0.400 layout families per query (95% CI 0.133–0.633; n=30)
- Normalized exploration score: 8.15% (95% CI 2.40%–14.07%; n=30)
- Exploration abstention rate: 76.67% (95% CI 59.07%–88.21%; n=30)
- Exploration records awaiting human review: 30/30

Formula: `(relevant predictions / K) × exp(Shannon entropy of relevant style-family distribution)`

This is a capability-registry routing proxy: it measures whether the router exposes multiple relevant template/style directions. It does not measure pixel-level diversity or final-image quality. Exploration records are excluded from primary core accuracy; compare two runs to obtain Style Exploration Lift@K.

## 14. Latency and system failures

- Mean / median latency: 1.3174 / 1.2930 ms
- p90 / p95 latency: 1.4270 / 1.4988 ms
- Error rate: 0.0000
- Retry rate: 0.0000

## 15. Limitations

- The committed pilot uses a deterministic lexical mock over the capability registry; it is plumbing validation, not a production-quality baseline.
- Generated candidate annotations have not received independent human approval.
- Character n-gram similarity is a reproducible fallback, not a semantic embedding model.
- Current text-only routing treats reference-image ID-photo work as out of scope.
- Confidence calibration metrics are only meaningful for adapters returning valid scores.
- Style families are evidence-grounded registry annotations and still require human review; they are coarser than perceptual image style.

## 16. Records awaiting human review

380 records remain in `review_queue.csv` / `review_queue.jsonl`. Auto-accepted records are still distinguishable from the 16 manually approved anchors.
