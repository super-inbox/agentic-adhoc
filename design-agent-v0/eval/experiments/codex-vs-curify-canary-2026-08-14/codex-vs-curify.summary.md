# Codex vs Curify — two-case canary

Codex ran in two new `codex exec --ephemeral` sessions. Each session received only the exact Query,
its input images, and neutral one-turn/save-output instructions. It did not receive Curify results,
the judge rubric, or hidden artifact-count requirements.

## Result

| Case | Evidence-based result | Codex contract | Curify contract | Main tradeoff |
| --- | --- | --- | --- | --- |
| AR-001 | Codex wins | Pass | Pass | Codex enlarges the title more proportionally and adds no unrelated brand. Curify is much faster but inserts a Curify logo. |
| AR-008 | Codex wins on fidelity; both fail overall | Fail | Fail | Codex uses both references and preserves identity plus the navy bomber. Curify omits the garment input and invents a black leather jacket. Both return only one image. |

This is a two-case canary, not an overall Agent ranking.

## Deterministic comparison

| Metric | Codex | Curify |
| --- | ---: | ---: |
| Evidence-based case wins | 2/2 | 0/2 |
| Artifact-contract passes | 1/2 | 1/2 |
| Cases using every input reference | 2/2 | 1/2 |
| Mean latency | 120.5 s | 34.1 s |

Codex is materially slower in these two runs. The current efficiency scorer still gives both AR-008
runs full efficiency because both are under the 240-second task budget; AR-001 gives Codex 0.9559
and Curify 1.0. Normalized USD cost remains unavailable, so cost is not ranked.

## AR-001

After resizing outputs to the common 928×1152 analysis canvas, the title-zone navy-pixel area rises
26.5% for Codex versus 97.8% for Curify. This diagnostic is not an aesthetic score, but it supports
the visible conclusion that Codex is closer to “放大一点.” Codex regenerates more pixels outside the
title band (normalized difference 0.0147 versus Curify's 0.0107), while Curify introduces an explicit
unrelated logo. Both provide one readable high-resolution image and pass the file contract.

## AR-008

Codex explicitly distinguishes the person as the edit target and the jacket as the garment reference.
Its image preserves the person's face, pose, anatomy, trousers, shoes, and studio background, while
applying a recognizable navy zipped bomber. Curify's deployed UI records the bomber asset as omitted
and generates a black leather biker jacket. Codex therefore wins core reference fidelity.

The Dataset nevertheless requires three image directions plus a manifest, a requirement not present
in the user Query. Since each Agent returns one image, both fail the artifact and production hard gates.
This mismatch should be resolved before the 100-case benchmark: either expose the required deliverable
count in every Agent prompt, or score the raw Query contract rather than a hidden three-image contract.

## Independent judge status

Gemini judge-v2 remains blocked by the project's monthly spending cap. No numeric visual score or
official cross-Agent total is reported. The raw images, candidate traces, deterministic checks, and
manual findings are preserved so the blind judge can be run later without regenerating either Agent.
