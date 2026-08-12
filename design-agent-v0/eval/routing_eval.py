#!/usr/bin/env python3
"""Design Agent v0 — routing eval (P0).

Scores Curify's existing query->template matcher (POST /api/search-template-match,
= Section-B multi-route retrieval + rerank) against the 100-query tool-intent
benchmark (agentic-adhoc/tool-intent-query-v1). Produces a baseline: match rate,
candidate-template recall, intent overlap, confidence — broken down by coverage &
specificity. coverage=gap queries -> the template/tool build roadmap.

Run: python routing_eval.py   (hits prod; ~2-3 min for 100 queries)
"""
import json, os, time, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
QUERIES = os.path.join(HERE, "tool_intent_queries.jsonl")
ENDPOINT = "https://www.curify-ai.com/api/search-template-match"
OUT_JSONL = os.path.join(HERE, "routing_eval_results.jsonl")
OUT_MD = os.path.join(HERE, "routing_eval_baseline.md")

def route(query, tries=2):
    body = json.dumps({"query": query}).encode()
    for a in range(1, tries + 1):
        try:
            req = urllib.request.Request(ENDPOINT, data=body,
                    headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=12) as r:
                return json.loads(r.read()).get("matches", [])
        except Exception as e:
            if a == tries: print(f"    FAIL {query[:20]}: {str(e)[:60]}")
            time.sleep(1.5 * a)
    return []

def main():
    rows = [json.loads(l) for l in open(QUERIES, encoding="utf-8") if l.strip()]
    results = []
    fout = open(OUT_JSONL, "w")
    for i, q in enumerate(rows):
        matches = route(q["query"])
        ids = [m.get("template_id") for m in matches]
        intents = {m.get("output_intent") for m in matches if m.get("output_intent")}
        confs = [m.get("confidence", 0) for m in matches]
        cand = set(q.get("candidate_templates") or [])
        exp = set(q.get("expected_route_intents") or [])
        recall = (len(cand & set(ids)) / len(cand)) if cand else None
        intent_hit = bool(exp & intents) if (exp and intents) else None
        results.append({
            "id": q["id"], "query": q["query"], "specificity": q.get("specificity"),
            "coverage": q.get("coverage"), "theme": q.get("theme"),
            "n_matches": len(matches), "top_conf": max(confs) if confs else 0.0,
            "returned_ids": ids, "returned_intents": sorted(intents),
            "candidate_recall": recall, "intent_hit": intent_hit,
        })
        fout.write(json.dumps(results[-1], ensure_ascii=False) + "\n"); fout.flush()
        print(f"  {i+1}/{len(rows)}  {q['query'][:24]} -> {len(matches)} matches", flush=True)
        time.sleep(0.2)
    fout.close()

    # ---- aggregate ----
    n = len(results)
    got = [r for r in results if r["n_matches"] > 0]
    with_cand = [r for r in results if r["candidate_recall"] is not None]
    with_intent = [r for r in results if r["intent_hit"] is not None]
    def rate(sub, pred): return (sum(1 for r in sub if pred(r)) / len(sub)) if sub else 0.0
    def by(field, pred, sub=results):
        d = defaultdict(list)
        for r in sub: d[r.get(field)].append(r)
        return {k: (len(v), rate(v, pred)) for k, v in sorted(d.items(), key=lambda x: str(x[0]))}

    L = []
    L.append("# Design Agent v0 — Routing Eval Baseline\n")
    L.append(f"_Endpoint: `POST /api/search-template-match` (Section-B matcher) · {n} queries · auto-generated._\n")
    L.append("## Headline\n")
    L.append(f"- **Match rate** (≥1 template returned): **{rate(results, lambda r: r['n_matches']>0):.0%}** ({len(got)}/{n}) — {n-len(got)} queries return NOTHING.")
    L.append(f"- **Candidate-template recall** (queries w/ labeled candidates, n={len(with_cand)}): mean **{(sum(r['candidate_recall'] for r in with_cand)/len(with_cand)) if with_cand else 0:.0%}**; any-hit **{rate(with_cand, lambda r: r['candidate_recall']>0):.0%}**.")
    L.append(f"- **Intent overlap** (matched output_intent ∩ expected_route_intents, n={len(with_intent)}): **{rate(with_intent, lambda r: r['intent_hit']):.0%}**.")
    L.append(f"- **Mean top confidence**: {(sum(r['top_conf'] for r in results)/n):.2f}.\n")
    L.append("## Match rate by coverage class\n")
    L.append("| coverage | n | match-rate | mean top-conf |\n|---|---|---|---|")
    cov = defaultdict(list)
    for r in results: cov[r["coverage"]].append(r)
    for k, v in sorted(cov.items(), key=lambda x: str(x[0])):
        mr = rate(v, lambda r: r["n_matches"] > 0)
        mc = sum(r["top_conf"] for r in v) / len(v)
        L.append(f"| {k} | {len(v)} | {mr:.0%} | {mc:.2f} |")
    L.append("\n## Match rate by specificity\n")
    L.append("| specificity | n | match-rate | cand-recall(any) |\n|---|---|---|---|")
    spd = defaultdict(list)
    for r in results: spd[r["specificity"]].append(r)
    for k, v in sorted(spd.items(), key=lambda x: str(x[0])):
        vc = [r for r in v if r["candidate_recall"] is not None]
        L.append(f"| {k} | {len(v)} | {rate(v, lambda r: r['n_matches']>0):.0%} | {rate(vc, lambda r: r['candidate_recall']>0):.0%} |")
    # zero-match queries = the gap roadmap
    zeros = [r for r in results if r["n_matches"] == 0]
    L.append(f"\n## Zero-match queries → build roadmap ({len(zeros)})\n")
    for r in zeros:
        L.append(f"- `{r['id']}` **{r['query']}** ({r['specificity']}/{r['coverage']}/{r['theme']})")
    open(OUT_MD, "w").write("\n".join(L) + "\n")
    print(f"\nDONE. results -> {OUT_JSONL}\nreport -> {OUT_MD}")
    print(f"  match-rate={rate(results, lambda r: r['n_matches']>0):.0%}  zero-match={len(zeros)}")

if __name__ == "__main__":
    main()
