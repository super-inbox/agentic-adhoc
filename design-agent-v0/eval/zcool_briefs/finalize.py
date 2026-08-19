import json, os, subprocess, io, time
from PIL import Image
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
OUT="out"; TH=os.path.join(OUT,"thumbs"); os.makedirs(TH,exist_ok=True)
recs=json.load(open(f"{OUT}/raw_works.json"))
CLASS_ZH={"packaging_sku_series":"包装 / SKU 系列","brand_visual_exploration":"品牌视觉探索",
          "brand_campaign":"品牌 Campaign","concept_to_production":"概念 → 可生产文件"}
out=[]
for r in recs:
    urls=r["image_urls"]
    pick=[urls[0]] + ([urls[len(urls)//2]] if len(urls)>2 else []) + ([urls[-1]] if len(urls)>1 else [])
    thumbs=[]
    for i,u in enumerate(pick[:3],1):
        p=f"{TH}/{r['id']}_{i}.jpg"
        if not os.path.exists(p):
            b=subprocess.run(["curl","-s","-A",UA,"--max-time","70",u],capture_output=True).stdout
            try:
                im=Image.open(io.BytesIO(b)); im=im.convert("RGB")
                # 长图裁上半部，避免生成超高缩略图
                if im.height > im.width*3: im=im.crop((0,0,im.width,im.width*3))
                im.thumbnail((480,1200)); im.save(p,quality=72)
            except Exception: continue
            time.sleep(1.2)
        if os.path.exists(p):
            w,h=Image.open(p).size
            thumbs.append({"path":f"thumbs/{os.path.basename(p)}","src_url":u,"w":w,"h":h})
    has_text=len(r["description"])>=150
    out.append({
      "id": r["id"],
      "layer": "workflow_brief",
      "brief_class": r["brief_class"],
      "brief_class_zh": CLASS_ZH[r["brief_class"]],
      "deliverable_intent": "generate",
      "language": "zh-CN",
      "source": {"site":"zcool","url":r["url"],"title":r["title"],"author":r["author"],
                 "captured_at":"2026-08-19",
                 "usage":"reference-only for internal eval; originals fetched at runtime; "
                         "low-res thumbnails stored for identification only"},
      "brief": {"text": r["description"], "text_available": has_text,
                "extraction": "html_text" if has_text else "requires_vlm_image_read"},
      # §7r-F 价值梯度，逐项标注有无——这是这份数据最重要的元信息
      "chain": {"brief": has_text, "references": False, "concepts": False,
                "alternatives": False, "selection": False, "rejection": False,
                "client_feedback": False, "revision": False, "final": True, "outcome": False},
      "gaps": ["references","concepts","alternatives","selection","rejection","client_feedback","revision"],
      "assets": {"image_count": r["n_images"], "image_urls": r["image_urls"][:40], "thumbnails": thumbs},
      "gold": {"final_deliverable": True,
               "notes": "Published portfolio outcome — usable as a gold reference for the finished "
                        "deliverable, NOT as a trajectory (§7s)."},
      "eval_use": ["input_brief","gold_reference"],
    })
    print(f"  {r['id']} {r['brief_class']:26s} text={'Y' if has_text else 'N'} thumbs={len(thumbs)} imgs={r['n_images']}")
with open(f"{OUT}/zcool_briefs.jsonl","w") as f:
    for o in out: f.write(json.dumps(o,ensure_ascii=False)+"\n")
print(f"\n  ✓ {len(out)} 条 → out/zcool_briefs.jsonl")
import collections
print("  类别分布:", dict(collections.Counter(o["brief_class"] for o in out)))
print("  有文本 brief:", sum(1 for o in out if o["brief"]["text_available"]), "/", len(out))
