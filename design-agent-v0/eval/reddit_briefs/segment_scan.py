"""Score a corpus by PROCESS SEGMENT rather than by full trajectory.

§7r-G asked "can we harvest end-to-end trajectories" and answered no (2/362).
§7s asks the better question — are individual segments usable — and gets 80/362
(22%). Keep both: the first sizes the moat, the second sizes the eval corpus.
"""
import json, re, sys, collections
SEG = {
 "S1_artifact_critique": [r"\b(?:c&c|critique|feedback|thoughts\?|roast|first draft|wip\b)",
                          r"would love (?:some|any) .{0,20}(?:feedback|eyes|critique)", r"what do you think"],
 "S2_before_after":      [r"\bbefore (?:and|/|&) after\b", r"\bv\d ?(?:->|→|vs\.?|to) ?v\d",
                          r"\b(?:redesign|rebrand)(?:ed)?\b", r"\bupdated (?:version|design|logo)\b",
                          r"\bafter (?:the )?feedback"],
 "S3_options_selection": [r"\bwhich (?:one|of these|do you)\b", r"\boption [abc1-3]\b",
                          r"\b[abc] or [abc]\b", r"\bhelp me (?:choose|pick|decide)"],
 "S4_brief_concept":     [r"asked me to", r"\bclient (?:want|ask|need)", r"\bthe brief\b", r"\bthey wanted\b"],
 "S5_design_production": [r"\bprinted\b", r"went to print", r"\bmanufactur", r"\bproof\b", r"\bfactory\b"],
}
def scan(path, min_comments=15):
    d=json.load(open(path)); ct=collections.Counter(); rich=collections.defaultdict(list)
    for x in d:
        blob=((x.get("title") or "")+" \n "+(x.get("text") or "")).lower()
        for k,ps in SEG.items():
            if any(re.search(p,blob) for p in ps):
                ct[k]+=1
                if x.get("nc",0)>=min_comments: rich[k].append(x)
    return d, ct, rich
if __name__=="__main__":
    d,ct,rich=scan(sys.argv[1] if len(sys.argv)>1 else "reddit_corpus_2026-08-18.json")
    for k in SEG: print(f"{k:24s} {ct[k]:4d} ({100*ct[k]//len(d)}%)  high-comment: {len(rich[k])}")
    print(f"NOTE S3==0 means multi-option ranking data is absent from public corpora; "
          f"it is exactly what the missing evaluate/rank deliverable (§7o class B) needs.")
