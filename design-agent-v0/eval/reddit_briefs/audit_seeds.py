"""Strict audit of the 35 raw seeds → a kept set and a rejected set.

Run after `task_scan.py` + hand-extraction. Encodes one verdict per seed so the
audit is reproducible and arguable rather than a silent hand-edit.

    python3 audit_seeds.py reddit_brief_seeds_2026-08-30.raw.jsonl

Three rules decide the verdict:

1. **Is it a design job, or a tool complaint?**  "--sref won't hold my character"
   is a real need wearing one product's controls. Building an eval case from it
   measures "can we do what Midjourney can't", which is a different benchmark
   from the one §7m set out to build. Tool complaints are rejected.
2. **Is there a criterion?**  A request whose deliverable is an opinion with no
   stated standard ("which do you prefer?") cannot be scored. Rejected.
3. **Would the fixture have to be invented wholesale?**  If we author the prior
   artifact, the difficulty becomes whatever we authored and the corpus grounding
   is gone. Rejected unless the fixture is generic (any two images, a road photo).

`level` is re-derived from the shape of the TASK, not from how complete the post
is: L4 needs an arc (explore / select / revise with a client), L3 is a bounded
operation however many assets it touches. The raw pass labelled 18 as L4; only 8
carried client feedback and 4 carried a selection, so most of those were L3 batch
work wearing an L4 label.

Three kept records are not cases at all — they are reference material (a gold
artifact, a verification checklist, a deliverable-scope definition). They carry
`record_type: reference_material` and no level, so nothing downstream counts them
as briefs.
"""
import json, sys, collections

# ---------------------------------------------------------------- verdicts
# id -> (level_or_None, why_kept)   None level = reference material, not a case
KEEP = {
    "RBS-SET-003": ("L3", "The only set-consistency case in the corpus tied to a physical production spec (14x8.5 heat-press bed). Self-contained: one style reference, five subjects, fixed aspect. Commercial POD work, not a hobby project."),
    "RBS-REF-001": ("L3", "Per-channel reference permission stated by someone who had never heard of the term: colour only, subject explicitly not. A standing art-direction instruction, and the fixture is any two images we already own."),
    "RBS-REF-002": ("L3", "The exact inverse of REF-001 - style minus colour. Kept as a matched pair because a negative channel permission is a different test from a positive one."),
    "RBS-REF-003": ("L3", "Cleanest reference-contract case in the file: reference A supplies layout with style explicitly forbidden, reference B supplies style. Two slots, two mutually exclusive policies."),
    "RBS-EDIT-001": ("L3", "Bounded edit with a deterministic check - replace text inside an existing bubble, and everything outside the mask must be byte-identical. Pixel-diff scores it without a judge."),
    "RBS-EDIT-003": ("L3", "The best hard-gate candidate in the corpus: cars must drive on the left. Binary, cheap to verify, and no prompt wording enforces it. Real retouching work."),
    "RBS-CFR-001": ("L4", "Real paid client project with a recorded feedback sequence: opening references (minimal B2B marks) contradicted by later feedback ('more bold'), six rounds, nothing locked between them."),
    "RBS-CFR-002": ("L4", "Real commercial multi-turn revision where the feedback is itself machine-generated and self-contradictory across rounds, and a competing artifact arrives mid-loop. No invariant is ever stated."),
    "RBS-CFR-003": ("L4", "Real client deck project: brand adherence asserted by the reviewer but underdetermined by the supplied assets, one named problem element, and week-long gaps between rounds - a resume case, not a continue case."),
    "RBS-BID-001": ("L4", "A genuine client-written logo brief quoted verbatim, carrying exactly the amount of vagueness real briefs carry, plus two checkable requirements (scalability, consistency)."),
    "RBS-BID-002": ("L4", "Kept despite being speculative work: it is the only selection task in the corpus with a stated criterion - candidates must pair with the icon - and evaluate_rank is our structurally thinnest axis."),
    "RBS-SEL-001": (None, "Not a case - the richest process artifact in the corpus. An ordered five-revision chain with the client's chosen endpoint marked and per-version authorship annotated, so client-side edits are separable. Gold reference only."),
    "RBS-PSF-002": ("L4", "Real production problem asked independently twice: design packaging when the manufacturer supplied no dieline, so W x H x D, panel map and bleed geometry are all undefined. Matches a gap we already hit in the packaging-mockup pipeline."),
    "RBS-PSF-003": (None, "Not a case - a verification checklist someone else wrote (packed dimensions, inserts, bleed/folds/small-text/low-res artwork check, physical sample). Use it as a verification contract, not a brief."),
    "RBS-CFRY-001": ("L4", "Commercial volume workflow, not one artifact: every approved design must end as a true vector master across hundreds of labels. The open question - is auto-trace enough or is manual redraw required - is what the workflow costs at volume."),
    "RBS-CFRY-002": ("L3", "The strongest moat case in the file. Input is a photograph OF a printed product; the artwork must be separated from its substrate before vectorising; and 'can you print this' wants a verdict, not an image. Stated as costlier than printing itself."),
    "RBS-CFRY-003": ("L3", "Three separate posters asking the same thing - convert a client raster to vector without redrawing it. Recurrence is the evidence; the task is bounded and the output is checkable (is it vector, does it match)."),
    "RBS-CFRY-004": (None, "Not a case - it draws the AI-concept to professional handoff line explicitly, and enumerates the remaining work: rebuild, dieline, typography, hierarchy, regulatory information, print specifications. That list is a deliverable-scope definition for concept_to_factory_ready."),
    "RBS-MFA-001": ("L4", "Thin, and kept deliberately: multi_format_adaptation is nearly absent from this corpus (1 in 362), and this one has a concrete propagating revision - change colours, remove gradients in a few places - across print and screen surfaces."),
    "RBS-ECO-001": ("L4", "A working commercial loop described tool by tool, whose named cost is a single late object-level client change (phone -> coffee cup) forcing a full regeneration. That is the edit-semantics gap stated as a business cost."),
}

REJECT = {
    "RBS-SET-001": "Indie game project, and the style invariant is a fixture we would have to author ourselves - at which point the difficulty is whatever we made. Keep the demand signal, not the case.",
    "RBS-SET-002": "Midjourney parameter problem (--cref vs style ref). The underlying need - identity surviving an attribute change - is real, but the post is about one product's controls.",
    "RBS-SET-004": "Hobby visual novel, 1,732 sprites via a LoRA. Not our customer, and the method is the poster's own pipeline rather than a stated job.",
    "RBS-SET-005": "Personal short film; the task is location continuity inside a specific video model.",
    "RBS-SET-006": "Personal horror short. Genuine three-way reference split, but expressed entirely as Midjourney v6 capability questions.",
    "RBS-REF-004": "Reframing it as 'place a brand mark faithfully into a generated scene' would be our invention, not the post - the poster is a game player fighting a video model's reference slots.",
    "RBS-REF-005": "Deriving a reusable style handle from five references is a tool-affordance request (--sref codes), and the reference set is a fixture we would have to build.",
    "RBS-REF-006": "No task statement. It is a buyer complaining that freelancers missed the brief. Valuable as vocabulary, not as a case.",
    "RBS-EDIT-002": "A workflow release post, not a job anyone had. The contract it ships (name the region, preserve the face) is worth citing as a competitive baseline, not running as our case.",
    "RBS-EDIT-004": "Hobbyist compositing question about seam alignment in a masked edit; the example is a comic-book character.",
    "RBS-CFR-004": "A situation, not a task: a whole brand package rejected at once, with no artifacts, no feedback wording and nothing to act on. It argues for the select checkpoint; it cannot be run.",
    "RBS-BID-003": "Two candidates and no decision criterion. 'Which do you prefer' is unscoreable - there is nothing for a judge to check an answer against.",
    "RBS-BID-004": "Critique request whose deliverable is an opinion. The poster names a suspect element, but no standard is stated, so a response cannot be marked right or wrong.",
    "RBS-PSF-001": "A billing and process complaint (revisions per SKU, non-designer reviewer), not a design task. Useful as a messy_condition when authoring packaging episodes.",
    "RBS-CFRY-005": "Tool-usage question about vector-to-raster handoff inside Adobe, not a design job.",
}

# Split constraints into what the post states vs what we concluded. Anything not
# listed here keeps all its constraints as `stated`, which is only true when every
# one of them was lifted directly from the post.
INFERRED = {
    "RBS-SET-003": ["one style reference held across all five subjects"],
    "RBS-REF-001": ["allowed influence from the reference is exactly one channel: colour"],
    "RBS-REF-002": ["allowed influence is style minus colour - a negative channel, not a positive one"],
    "RBS-REF-003": ["the two must not blend"],
    "RBS-EDIT-001": ["the rest of the image must be byte-level untouched, not merely similar"],
    "RBS-EDIT-003": ["the constraint is invisible in the prompt-to-pixel path and needs verification, not persuasion"],
    "RBS-CFR-001": ["the agent must carry the conflict forward, not silently drop the earlier constraint"],
    "RBS-CFR-002": ["no invariant is ever stated - the agent has to infer what must not change"],
    "RBS-CFR-003": ["sessions are days or weeks apart - resume, not continue"],
    "RBS-BID-001": ["every adjective is unfalsifiable (minimalist, professional, reliable)"],
    "RBS-BID-002": ["ranking is over PAIRS (wordmark + icon), not over single candidates"],
    "RBS-PSF-002": ["everything downstream (panel assignment, safe area, fold allowance) is undefined until it is derived or assumed"],
    "RBS-CFRY-001": ["vectorisation is a per-approval recurring cost, not a one-off"],
    "RBS-CFRY-002": ["the answer 'can you print this' is a verification verdict, not an image",
                     "the artwork must be separated from its substrate (fabric, folds, lighting) before vectorising"],
    "RBS-CFRY-003": ["source is client-supplied and its quality is not negotiable"],
    "RBS-MFA-001": ["revisions are attribute-level and must propagate consistently across all surfaces"],
    "RBS-ECO-001": ["baked-in text must be separable after the fact",
                    "the loop crosses three tools and the state does not survive the crossings"],
}

READINESS = {  # re-assessed strictly: is the fixture generic, or must we invent it?
    "RBS-SET-003": "ready_to_author", "RBS-REF-001": "ready_to_author",
    "RBS-REF-002": "ready_to_author", "RBS-REF-003": "ready_to_author",
    "RBS-EDIT-001": "ready_to_author", "RBS-EDIT-003": "ready_to_author",
    "RBS-CFR-001": "needs_fixture_assets", "RBS-CFR-002": "needs_fixture_assets",
    "RBS-CFR-003": "needs_fixture_assets", "RBS-BID-001": "ready_to_author",
    "RBS-BID-002": "needs_fixture_assets", "RBS-SEL-001": "needs_fixture_assets",
    "RBS-PSF-002": "ready_to_author", "RBS-PSF-003": "ready_to_author",
    "RBS-CFRY-001": "ready_to_author", "RBS-CFRY-002": "ready_to_author",
    "RBS-CFRY-003": "ready_to_author", "RBS-CFRY-004": "ready_to_author",
    "RBS-MFA-001": "needs_fixture_assets", "RBS-ECO-001": "needs_fixture_assets",
}


def audit(rows):
    kept, rejected = [], []
    for x in rows:
        i = x["id"]
        if i in REJECT:
            rejected.append({
                "id": i, "category": x["category"], "language": x["language"],
                "provenance": x["provenance"],
                "observed_task": x["observed_task"],
                "observed_failure": x["observed_failure"],
                "vernacular": x["vernacular"],
                "rejected_because": REJECT[i],
                "still_counts_as": "demand_signal",
            })
            continue
        if i not in KEEP:
            raise SystemExit(f"unaudited seed: {i}")
        level, why = KEEP[i]
        inferred = INFERRED.get(i, [])
        stated = [c for c in x["constraints_observed"] if c not in inferred]
        if len(stated) + len(inferred) != len(x["constraints_observed"]):
            raise SystemExit(f"{i}: an INFERRED entry does not match any constraint verbatim")
        rec = {
            "id": i,
            "record_type": "case" if level else "reference_material",
            "schema_version": "seed-0.2",
            "category": x["category"],
            "primary_intent": x["primary_intent"],
            "secondary_intents": x["secondary_intents"],
            "language": x["language"],
            "provenance": x["provenance"],
            "observed_task": x["observed_task"],
            "observed_failure": x["observed_failure"],
            "constraints_stated": stated,
            "constraints_inferred": inferred,
            "vernacular": x["vernacular"],
            "chain": x["chain"],
            "eval_use": x["eval_use"],
            "brief_readiness": READINESS[i],
            "audit": {"reviewed": "2026-08-31", "kept_because": why},
        }
        if level:
            rec["level"] = level
        else:
            rec["eval_use"] = [u for u in x["eval_use"] if u != "input_brief"]
        kept.append(rec)
    return kept, rejected


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "reddit_brief_seeds_2026-08-30.raw.jsonl"
    rows = [json.loads(l) for l in open(src)]
    kept, rejected = audit(rows)
    with open("reddit_brief_seeds_2026-08-30.jsonl", "w") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open("reddit_seeds_rejected_2026-08-30.jsonl", "w") as f:
        for r in rejected:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    cases = [r for r in kept if r["record_type"] == "case"]
    print(f"in {len(rows)} → kept {len(kept)} ({len(cases)} cases + "
          f"{len(kept)-len(cases)} reference records) · rejected {len(rejected)}")
    print("  level  ", dict(collections.Counter(r["level"] for r in cases)))
    print("  intent ", dict(collections.Counter(r["primary_intent"] for r in cases)))
    print("  ready  ", dict(collections.Counter(r["brief_readiness"] for r in cases)))
    inf = sum(len(r["constraints_inferred"]) for r in kept)
    tot = inf + sum(len(r["constraints_stated"]) for r in kept)
    print(f"  constraints: {tot-inf} stated / {inf} inferred")
