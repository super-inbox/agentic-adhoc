"""Rank the 08-18 Reddit corpus by TASK-shapedness (not pain vocabulary).

Prior passes measured pain vocab (analyze.py), full trajectories (trajectory_scan,
2/362) and process segments (segment_scan, 80/362). None extracted the *task*.
This one asks: does this post state a concrete design job someone had to do?
"""
import json, re, sys, collections

DELIVERABLE = r"(logo|packaging|package design|label|dieline|box|pouch|carton|bottle|can\b|poster|flyer|banner|brochure|menu|mockup|mock-?up|book cover|album cover|business card|t-?shirt|apparel|sticker|icon set|icons?\b|thumbnail|character sheet|product (?:photo|shot|image)|ad creative|ads?\b|social (?:post|media)|deck|presentation|infographic|brand(?:ing)? (?:identity|guide|kit)|style guide|wordmark|typeface|layout|catalog|lookbook|billboard|signage|wrap|tattoo|zine|magazine|editorial|website|landing page|ui\b|wedding invit|invitation|merch)"
TASK_VERB = r"(i (?:need|have|want|am trying|'m trying|was asked|got asked)|how (?:do|would|can) i|need to (?:make|create|design|produce|render|export)|trying to (?:make|create|design|get|recreate|match)|working on a|asked me to|client (?:wants|asked|needs|gave)|best way to|any way to|is there a way to|looking for a way|help me (?:make|design|create)|i'?m designing|i'?ve been asked)"
CONSTRAINT = r"(cmyk|300 ?dpi|bleed|die-?line|print(?:er|ing|-ready)?|vector|svg|eps|spot colou?r|pantone|foil|emboss|size[sd]? for|dimensions|aspect ratio|\d+ ?x ?\d+|multiple sizes|resize|variants?|skus?|flavou?rs|batch of|series of|set of \d|consistent(?:cy)? (?:character|style)|same character|brand guideline)"
NEGATIVE = r"(how much (?:should|do) i charge|charge for|my rate|salary|invoice|scam|non-?compete|contract|portfolio review|resume|cv\b|should i (?:go to|quit|study)|degree|internship|hiring|job market|got fired|client (?:won'?t|didn'?t) pay|ghosted|ai will (?:replace|kill)|is graphic design dead)"

def score(x):
    blob = ((x.get("title") or "") + "\n" + (x.get("text") or "")).lower()
    s, why = 0, []
    for name, pat, w in (("deliv", DELIVERABLE, 2), ("verb", TASK_VERB, 2), ("constraint", CONSTRAINT, 2)):
        m = set(m.group(0) for m in re.finditer(pat, blob))
        if m:
            s += w + min(len(m), 3)
            why.append(f"{name}:{','.join(sorted(m)[:4])}")
    if re.search(NEGATIVE, blob): s -= 6; why.append("NEG")
    if len(x.get("text") or "") > 250: s += 2
    if len(x.get("text") or "") < 60: s -= 3
    return s, why

d = json.load(open(sys.argv[1]))
ranked = sorted(((score(x)[0], score(x)[1], x) for x in d), key=lambda t: -t[0])
cut = int(sys.argv[2]) if len(sys.argv) > 2 else 6
keep = [r for r in ranked if r[0] >= cut]
print(f"# corpus={len(d)} candidates(score>={cut})={len(keep)}")
print("# by sub:", dict(collections.Counter(r[2]["sub"] for r in keep)))
for i, (s, why, x) in enumerate(keep):
    t = re.sub(r"\s+", " ", (x.get("text") or ""))[:900]
    print(f"\n### [{i}] score={s} r/{x['sub']} up={x['score']} nc={x['nc']} h={x['h']}")
    print(f"T: {x['title']}")
    print(f"B: {t}")
