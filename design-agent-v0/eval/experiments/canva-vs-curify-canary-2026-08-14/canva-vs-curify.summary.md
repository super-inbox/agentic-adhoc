# Canva vs Curify — two-case fair comparison

The two downloaded Canva files map to different benchmark cases:

- The `SUMMER FORM` poster is AR-001: “把海报的标题放大一点”.
- The person wearing a navy bomber is AR-008: “try on this jacket on my photo for a lookbook”.

They must not be scored as two AR-008 directions.

## Result

| Case | Evidence-based result | Canva contract | Curify contract | Key reason |
| --- | --- | --- | --- | --- |
| AR-001 | Canva wins | Pass | Pass | Canva makes the smaller requested edit and preserves unrelated content. Curify over-enlarges the title and adds an unrelated Curify logo. |
| AR-008 | Canva wins on garment fidelity; both fail overall | Fail | Fail | Canva uses both references and returns two navy-bomber candidates, although the second changes identity. Curify omits the garment input and invents a black leather jacket. Neither supplies three images plus a manifest. |

This gives Canva two evidence-based case wins out of two, but it is only a canary result—not an
overall Agent ranking.

## AR-001: objective preservation check

Both systems return one readable 928×1152 image, so both pass the deterministic artifact and
resolution gates. Relative to the source image:

| Diagnostic | Canva | Curify |
| --- | ---: | ---: |
| Full-image normalized difference | 0.0272 | 0.0456 |
| Difference outside the title band | 0.0064 | 0.0107 |
| Title-zone navy-pixel increase | +12.7% | +97.8% |

These diagnostics are not aesthetic scores. They support the visible finding that Canva changes
the requested title more conservatively and preserves more of the rest of the image. Curify makes
the edit highly visible, but “放大一点” does not call for an approximately doubled title-ink area,
and the added Curify mark violates the no-unrelated-logo constraint.

## AR-008: reference and delivery check

- Canva consumes both source assets and both original outputs are stored. Candidate 1 keeps the
  person's identity; candidate 2 replaces the person with a different white male model. Both show
  a recognizable navy bomber, although both invent a sleeve zipper pocket and change garment details.
- Curify's deployed page consumes only the person image and records the bomber image as omitted.
  The generated poster uses a black leather biker jacket, so its polished layout cannot compensate
  for the missing product reference.
- The benchmark requires three image directions plus a manifest. With two Canva images and one
  Curify image, both fail the same hard delivery gate. Canva's deterministic rendered-asset readiness
  proxy improves to 0.6667 versus Curify's 0.1667, but neither passes the three-image production gate.

## Independent judge status

A fresh blind judge-v2 run was configured so that all four outputs would receive the same Dataset
contract, source pixels, Gemini 2.5 Pro model, temperature, and rubric without Agent identities.
Gemini rejected the first request with `RESOURCE_EXHAUSTED` because the project exceeded its monthly
spending cap. No partial numeric comparison was produced. Numeric visual-quality scores should be
generated later from these frozen artifacts with the same independent judge-v2 protocol; the
deterministic results above do not depend on that API call.
