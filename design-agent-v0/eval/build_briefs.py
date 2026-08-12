#!/usr/bin/env python3
"""Extract workflow BRIEFS from the 5-domain workflow research.

Why briefs and not more queries: the eval already has 118 routing/agent-route
queries with real reference images. What it has none of is multi-step workflow
briefs — a whole design job with a known-good step sequence — which is what
evaluation and distillation actually need (spec §7f).

Source: visual-search-adhoc .../workflow-research-5-domains/candidates/*.md —
18 documented real jobs (agency case studies, brand/packaging/merch/edu/ecom).

Only PROCESS FACTS are taken: the domain, the ordered stage labels the case
observed, and provenance. The brief text is written fresh from those facts —
none of the source prose is copied.
"""
import json, os, re, sys
from collections import Counter

SRC = "/Users/qqwjq/visual-search-adhoc/docs/daily_report/8.8/workflow-research-5-domains/candidates"
OUT = sys.argv[1] if len(sys.argv) > 1 else "briefs.jsonl"

# stage label -> controlled step slug, so shapes compare across cases and map
# onto the agent's tool registry
STEP_VOCAB = [
    # order matters — first match wins, so put specific before generic
    (r"dieline", "dieline"),
    (r"mockup test|prototype|physical", "prototype_test"),
    (r"brief|requirement|discovery|objective|business context|input|problem|goal|challenge",
     "intake_brief"),
    (r"research|audit|benchmark|competitor|persona|audience|investigation|insight",
     "research"),
    (r"pedagog|cognitive|principle|rationale|basis|strategy", "principles"),
    (r"process|scale|method|team|crowdsourc|workflow|pipeline", "process_model"),
    (r"structur|dimension|measure|format|spec|layout system", "structure_spec"),
    (r"concept|exploration|direction|option|variant|development", "explore_concepts"),
    (r"select|chosen|decision|vote|approve", "select_direction"),
    (r"refine|revision|feedback|iterat", "refine"),
    (r"identity|logo|typograph|palette|colou?r system|visual system", "identity_system"),
    (r"apply|extend|expansion|family|collateral|asset|sku|product line|merchandis",
     "expand_assets"),
    (r"practice|exercise|quiz|activity|lesson", "learning_activities"),
    (r"production|print|press|factory|final layout|output file|manufactur", "production_file"),
    (r"launch|deliver|shipp|retail|publish|output|result", "deliver"),
]

DOMAIN_MAP = {
    "packaging": "packaging", "brand": "brand", "merch": "merch",
    "education": "education", "ecommerce": "product", "e-commerce": "product",
}


def to_step(label: str):
    low = label.lower()
    for pat, slug in STEP_VOCAB:
        if re.search(pat, low):
            return slug
    return None


def parse(path):
    text = open(path, encoding="utf-8").read()
    head = text.split("## What was actually observed", 1)
    meta = head[0]

    def field(name):
        m = re.search(rf"^- \*\*{name}:?\*\*\s*(.+)$", meta, re.M)
        return m.group(1).strip() if m else ""

    domain_raw = field("Domain").lower()
    domain = next((v for k, v in DOMAIN_MAP.items() if k in domain_raw), "general")
    title = field("Title") or os.path.basename(path)[:-3]
    url = field("Source URL")
    org = field("Author/Org")

    steps, seen = [], set()
    if len(head) > 1:
        body = head[1].split("## ", 1)[0]
        for line in body.splitlines():
            m = re.match(r"^- \*\*([^:*]+):?\*\*", line.strip())
            if not m:
                continue
            slug = to_step(m.group(1))
            if slug and slug not in seen:
                seen.add(slug)
                steps.append(slug)
    return domain, title, url, org, steps


rows = []
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith(".md"):
        continue
    domain, title, url, org, steps = parse(os.path.join(SRC, fn))
    if len(steps) < 3:          # not a documented multi-step process
        continue
    case_id = fn.split("-")[0] + "-" + fn.split("-")[1]
    rows.append({
        "id": f"BRF-{case_id}",
        "layer": "workflow_brief",
        # written fresh from the observed facts — no source prose copied
        "brief": f"Take a {domain} job from brief to delivered assets: {title}.",
        "domain": domain,
        "expected_steps": steps,
        "expected_step_count": len(steps),
        "has_reference": False,
        "provenance": {"case": fn[:-3], "org": org, "source_url": url},
        "evidence": "external_case_study",
    })

with open(OUT, "w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"wrote {len(rows)} briefs -> {OUT}")
print("  by domain:", dict(Counter(r["domain"] for r in rows)))
print("  step-count range:", min(r["expected_step_count"] for r in rows), "-",
      max(r["expected_step_count"] for r in rows))
print("  most common steps:", Counter(s for r in rows for s in r["expected_steps"]).most_common(8))
