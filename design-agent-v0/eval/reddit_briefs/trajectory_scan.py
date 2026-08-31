"""Score a Reddit corpus against the §7r-F data-value gradient.

Answers one question: can design decision-trajectories be harvested from public
posts? Run 2026-08-18 on 362 posts: only 2 hit >=3 signal classes. See §7r-G.
"""
import json, re, sys, collections
SIG = {
 "brief":       [r"\bclient (?:want|ask|said|need)", r"\bthe brief\b", r"asked me to", r"\bthey wanted\b"],
 "alternatives":[r"\boption [abc1-3]\b", r"\bversion \d", r"\bconcept [abc1-3]\b", r"\bthree (?:options|concepts|directions)"],
 "selection":   [r"they (?:picked|chose|went with)", r"\bwe went with\b", r"\brejected\b", r"\bscrapped\b"],
 "feedback":    [r"client said", r"feedback (?:was|from)", r"they said", r"told me (?:to|it)"],
 "revision":    [r"\brevision", r"\bbefore (?:and|/) after\b", r"\bfinal (?:version|design)\b", r"\biteration"],
 "outcome":     [r"\bprinted\b", r"went to print", r"\bmanufactur", r"\bfactory\b", r"\bproof\b"],
}
def scan(path, min_hits=3):
    d=json.load(open(path)); out=[]; ct=collections.Counter()
    for x in d:
        blob=((x.get("title") or "")+" \n "+(x.get("text") or "")).lower()
        hit=[k for k,ps in SIG.items() if any(re.search(p,blob) for p in ps)]
        for h in hit: ct[h]+=1
        if len(hit)>=min_hits: out.append((hit,x))
    return d, ct, out
if __name__=="__main__":
    d,ct,rich=scan(sys.argv[1] if len(sys.argv)>1 else "reddit_corpus_2026-08-18.json")
    print(f"corpus={len(d)}")
    for k in SIG: print(f"  {k:13s} {ct[k]:4d} ({100*ct[k]//len(d)}%)")
    print(f"  >=3 signals: {len(rich)}")
    for hit,x in rich: print(f"    [{x['score']}] r/{x['sub']} {x['title'][:70]}  {'/'.join(hit)}")
