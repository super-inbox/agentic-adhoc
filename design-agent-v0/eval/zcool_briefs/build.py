import re, subprocess, json, time, html, os
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
CHROME = ("看点高级的","拿点有用的","学点真干货","找点新财路","发布 登录 注册","站酷ZCOOL")
FOOT = ("大家都在看","查看更多","为你推荐","猜你喜欢","站酷旗下","版权声明","相关作品","Copyright","举报","热门标签")

def get(u):
    return subprocess.run(["curl","-s","-A",UA,"--max-time","70",u], capture_output=True, text=True).stdout

def plain(h):
    h = re.sub(r'(?is)<(script|style|noscript).*?</\1>', ' ', h)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'(?s)<[^>]+>', ' ', h)))

def describe(t):
    """Pick the segment that reads like project prose: high CJK density, low
    token repetition (ZCOOL's footer is a tag cloud that repeats '设计' endlessly)."""
    for f in FOOT:
        t = t.split(f)[0]
    best, score = "", 0.0
    for seg in re.split(r'关注|私信|浏览', t):
        seg = seg.strip()
        if len(seg) < 80:
            continue
        zh = len(re.findall(r'[一-鿿]', seg)) / max(len(seg), 1)
        toks = re.findall(r'[一-鿿]{2,4}', seg)
        rep = (len(toks) - len(set(toks))) / max(len(toks), 1)
        if zh < 0.35 or rep > 0.45:
            continue
        if any(c in seg for c in CHROME):
            continue
        s = len(seg) * zh * (1 - rep)
        if s > score:
            best, score = seg, s
    return best[:2500]

def imgs(h):
    us = [u.replace("&amp;", "&") for u in re.findall(r'https?://img\.zcool\.cn/community/[^\s"\'\\]+', h)]
    return [u for u in dict.fromkeys(us) if "saveexif" in u]

if __name__ == "__main__":
    works = json.load(open("works.json"))
    os.makedirs("out", exist_ok=True)
    recs = []
    for w in works:
        h = get(w["url"]); t = plain(h)
        d = describe(t); im = imgs(h)
        title = (re.search(r'<title>(.*?)</title>', h, re.S) or [None, ""])[1].strip()
        author = title.split("_")[-1].replace("-站酷ZCOOL", "").strip() if "_" in title else ""
        print(f"  {w['id']} {w['brief_class']:26s} 正文{len(d):>5}字 图{len(im):>4}张")
        recs.append({**w, "title": title, "author": author, "description": d,
                     "image_urls": im[:60], "n_images": len(im)})
        time.sleep(2.5)
    json.dump(recs, open("out/raw_works.json","w"), ensure_ascii=False, indent=1)
    print(f"\n  ✓ {len(recs)} 条")
