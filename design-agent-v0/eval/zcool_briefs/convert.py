"""Align the ZCOOL workflow briefs to agentic-adhoc/design-agent-v0/eval/briefs.jsonl.

Three things the incumbent schema requires that the first cut got wrong:
  1. `brief` is a STRING ("the job as a user would state it"), not an object.
  2. `domain` / `provenance` / `evidence`, not `brief_class` / `source`.
  3. build_briefs.py policy: "Only PROCESS FACTS are taken … none of the source
     prose is copied." So the ZCOOL description text is NOT carried over; the
     brief line is written fresh from the factual job description.

expected_steps is left EMPTY on purpose: a portfolio page does not publish its
stage sequence, and inventing a plausible one would be exactly the fabrication
spec §7i warns about. Absent is honest; guessed is not.
"""
import json

FRESH = {  # id -> (domain, BRF id, freshly written job description)
 "ZCB-001": ("packaging","BRF-PACK-03","a Xinjiang tomato-products brand — identity plus a tomato-sauce packaging family across SKUs"),
 "ZCB-002": ("packaging","BRF-PACK-04","a bakery brand — identity and packaging for a small retail line"),
 "ZCB-007": ("packaging","BRF-PACK-05","a pet-food brand — identity and packaging for a wet-food pouch line"),
 "ZCB-003": ("packaging","BRF-PACK-06","a Mid-Autumn festival gift box — structural and finish decisions through to a producible package"),
 "ZCB-004": ("brand",    "BRF-BRAND-04","a restaurant group — full brand identity programme"),
 "ZCB-006": ("brand",    "BRF-BRAND-05","a modern-Chinese dessert parlour — logo and visual identity system"),
 "ZCB-005": ("brand",    "BRF-BRAND-06","a game x QSR anniversary collaboration — campaign key visual and themed space"),
}
rows=[json.loads(l) for l in open("out/zcool_briefs.jsonl")]
out=[]
for r in rows:
    dom, bid, desc = FRESH[r["id"]]
    out.append({
      # ---- fields the incumbent schema defines ----
      "id": bid,
      "layer": "workflow_brief",
      "brief": f"Take a {dom} job from brief to delivered assets: {desc}.",
      "domain": dom,
      "expected_steps": [],          # portfolio pages do not publish stages — see docstring
      "expected_step_count": 0,
      "has_reference": False,
      "provenance": {"case": r["id"], "org": r["source"]["author"],
                     "source_url": r["source"]["url"], "site": "zcool",
                     "captured_at": r["source"]["captured_at"]},
      "evidence": "external_portfolio",   # NOT external_case_study — a portfolio is not a case study
      # ---- additive: the gradient metadata (spec §7t) ----
      "brief_class": r["brief_class"],
      "deliverable_intent": r["deliverable_intent"],
      "language": r["language"],
      "brief_text_source": r["brief"]["extraction"],   # html_text | requires_vlm_image_read
      "chain": r["chain"],
      "gaps": r["gaps"],
      "assets": r["assets"],
      "gold": r["gold"],
      "eval_use": r["eval_use"],
    })
out.sort(key=lambda x: x["id"])
with open("out/zcool_briefs.aligned.jsonl","w") as f:
    for o in out: f.write(json.dumps(o,ensure_ascii=False)+"\n")
for o in out: print(f"  {o['id']:14s} {o['domain']:10s} {o['brief_class']:26s} {o['brief_text_source']}")
print(f"\n  ✓ {len(out)} 条 → out/zcool_briefs.aligned.jsonl（未携带任何站酷原文）")
