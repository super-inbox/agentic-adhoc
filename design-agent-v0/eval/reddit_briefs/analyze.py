import json, re, collections, sys
d=json.load(open("raw.json"))
TOOLS=["Canva","Midjourney","Figma","Photoshop","Illustrator","Firefly","ChatGPT","DALL","Stable Diffusion",
 "ComfyUI","Ideogram","Recraft","Krea","Leonardo","Flux","Nano Banana","Adobe Express","InDesign","Procreate","Affinity"]
# pain vocabulary probes tied to §7m hypotheses
PROBE={
 "H1 改稿/迭代": [r"\brevision", r"\bre-?do\b", r"start over", r"from scratch", r"\btweak", r"minor change",
                 r"change one thing", r"back and forth", r"\bendless\b", r"round of (?:edits|revisions)"],
 "H2 一次性生成漂移": [r"\bconsisten", r"\bdrift", r"\bvariation", r"\bsame character", r"\bsame style",
                 r"keeps? changing", r"random(?:ly)? (?:add|chang)", r"\bseed\b", r"batch"],
 "H3 参考图/局部改": [r"\breference", r"\bimg2img", r"\binpaint", r"\bmask", r"style ref", r"\bcontrolnet",
                 r"local(?:ised|ized)? edit", r"only change", r"keep the rest"],
 "H4 发散过度/需收敛": [r"too many (?:options|variations)", r"overwhelm", r"which one", r"narrow down",
                 r"pick one", r"decision"],
 "H5 元素级/图层": [r"\blayer", r"\bvector", r"\beditable", r"\bpsd\b", r"\bsvg\b", r"\bassets?\b",
                 r"compos(?:e|ite|iting)", r"\belements?\b"],
 "生产/交付约束": [r"print[- ]ready", r"\bcmyk\b", r"\bdieline\b", r"\bbleed\b", r"\bdpi\b", r"production file"],
 "模糊客户语言": [r"make it pop", r"too cheap", r"more modern", r"not quite", r"\bcheap looking", r"i'?ll know it when"],
}
tool_ct=collections.Counter(); probe_ct=collections.Counter(); probe_ex=collections.defaultdict(list)
for x in d:
    blob=((x.get("title") or "")+" \n "+(x.get("text") or ""))
    low=blob.lower()
    for t in TOOLS:
        if re.search(r"\b"+re.escape(t.lower()), low): tool_ct[t]+=1
    for k,pats in PROBE.items():
        for p in pats:
            if re.search(p, low):
                probe_ct[k]+=1
                if len(probe_ex[k])<6 and x.get("score",0)>=20:
                    m=re.search(p, low); s=max(0,m.start()-90); 
                    probe_ex[k].append((x["score"],x["sub"],blob[s:m.start()+130].replace("\n"," ").strip()))
                break
print(f"  语料: {len(d)} 帖 | 覆盖 {len(set(x['sub'] for x in d))} 个 subreddit\n")
print("  ── 假设命中率（占全部帖子） ──")
for k,c in probe_ct.most_common(): print(f"    {k:18s} {c:4d}  {100*c//len(d):3d}%")
print("\n  ── 工具提及 ──")
for t,c in tool_ct.most_common(12): print(f"    {t:16s} {c}")
print("\n  ── 高分原话样本 ──")
for k in PROBE:
    if probe_ex[k]:
        print(f"\n  【{k}】")
        for sc,sub,q in sorted(probe_ex[k],reverse=True)[:3]:
            print(f"    [{sc:>4}] r/{sub}: …{q[:165]}…")
top=sorted(d,key=lambda x:-(x.get("score") or 0))[:12]
print("\n  ── 最高分帖子 ──")
for x in top: print(f"    [{x['score']:>5}|{x['nc']:>4}c] r/{x['sub']:16s} {(x['title'] or '')[:78]}")
