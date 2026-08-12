#!/usr/bin/env python3
"""Factory-Ready Production Exporter — v0: Sticker (die-cut).

Design image  ->  factory production package (not a high-res PNG):
  01_artwork.png      300 DPI, transparent, subject only
  02_cutline.svg      die-cut contour = offset silhouette (mm-accurate)
  03_artwork_cmyk.pdf print-ready CMYK (via ImageMagick)
  04_preview.png      artwork + cutline overlay (QA)
  05_spec.pdf         size / material / DPI / bleed / cut

Deps: numpy, scipy, PIL, ImageMagick (`magick`); rembg[cpu] for bg removal (optional —
falls back to alpha/white-bg; swap in BEN2 for higher quality). No cv2/reportlab needed.
Core = deterministic pre-press (LLM plans params; CODE draws the cutline — never AI).

Usage: python sticker_exporter.py <image> [--mm 60] [--dpi 300] [--cut-mm 3]
"""
import os, sys, io, zipfile, subprocess, argparse
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFont

# ---------- background removal ----------
def ensure_cutout(im: Image.Image) -> Image.Image:
    """RGBA with subject on transparent bg. Real alpha -> as-is; else rembg (u2net,
    swap in BEN2 later for higher quality); else fall through to white-bg removal."""
    im = im.convert("RGBA")
    if np.array(im.split()[-1]).ptp() > 10:
        return im                                   # already has a real alpha channel
    try:
        from rembg import remove
        out = remove(im)
        if np.array(out.split()[-1]).ptp() > 10:
            print("  bg-removed via rembg (u2net)")
            return out
    except Exception as e:
        print(f"  [warn] rembg unavailable ({str(e)[:50]}); using white-bg fallback")
    return im

# ---------- subject mask ----------
def subject_mask(im: Image.Image) -> np.ndarray:
    """Bool mask, True = subject. Use alpha if present, else drop near-white bg."""
    if im.mode in ("RGBA", "LA") and np.array(im.split()[-1]).ptp() > 10:
        a = np.array(im.convert("RGBA").split()[-1])
        m = a > 128
    else:
        rgb = np.array(im.convert("RGB")).astype(int)
        # near-white background removal (corners assumed background)
        white = (rgb > 244).all(axis=2)
        m = ~white
    m = ndimage.binary_fill_holes(m)
    lbl, n = ndimage.label(m)
    if n > 1:                                   # keep largest connected component
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
        m = lbl == (1 + int(np.argmax(sizes)))
    return m

# ---------- die-cut contour ----------
def moore_trace(mask: np.ndarray):
    """Ordered outer boundary (clockwise) of a filled binary mask (Moore tracing)."""
    ys, xs = np.where(mask)
    if len(xs) == 0: return []
    sy = ys.min(); sx = xs[ys == sy].min()      # top-most, then left-most
    start = (sy, sx)
    # 8-neighborhood clockwise from West
    nb = [(-1,-1),(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1)]
    H, W = mask.shape
    def inb(y,x): return 0 <= y < H and 0 <= x < W and mask[y,x]
    contour = [start]; b = start; prev_dir = 6  # came from West-ish
    for _ in range(8 * int(mask.sum()) + 10):
        found = False
        for k in range(8):
            d = (prev_dir + 1 + k) % 8
            ny, nx = b[0]+nb[d][0], b[1]+nb[d][1]
            if inb(ny, nx):
                b = (ny, nx); prev_dir = (d + 4) % 8; found = True
                contour.append(b)
                break
        if not found or (b == start and len(contour) > 2): break
    return contour  # list of (y,x)

def dp_simplify(pts, eps):
    """Douglas-Peucker on list of (x,y)."""
    if len(pts) < 3: return pts
    a, b = np.array(pts[0]), np.array(pts[-1])
    ab = b - a; L = np.hypot(*ab) or 1e-9
    d = np.abs(np.cross(np.array(pts) - a, ab)) / L
    i = int(np.argmax(d))
    if d[i] > eps:
        return dp_simplify(pts[:i+1], eps)[:-1] + dp_simplify(pts[i:], eps)
    return [pts[0], pts[-1]]

def simplify_closed(pts, eps):
    """Douglas-Peucker for a CLOSED contour: split at the point farthest from pts[0]."""
    if len(pts) < 4: return pts
    a = np.array(pts[0])
    far = int(np.argmax([np.hypot(*(np.array(p) - a)) for p in pts]))
    if far < 1 or far >= len(pts) - 1: return pts
    return dp_simplify(pts[:far+1], eps)[:-1] + dp_simplify(pts[far:], eps)[:-1]

def chaikin(pts, iters=2):
    """Round the polygon corners (closed)."""
    for _ in range(iters):
        out = []
        for i in range(len(pts)):
            p, q = np.array(pts[i]), np.array(pts[(i+1) % len(pts)])
            out.append(tuple(0.75*p + 0.25*q)); out.append(tuple(0.25*p + 0.75*q))
        pts = out
    return pts

def cutline(mask, offset_px):
    """Offset silhouette -> simplified, rounded closed polygon in pixel coords (x,y)."""
    struct = ndimage.generate_binary_structure(2, 2)   # 8-conn -> rounder offset
    dil = ndimage.binary_dilation(mask, structure=struct, iterations=int(max(1, offset_px)))
    dil = ndimage.binary_fill_holes(dil)
    yx = moore_trace(dil)
    xy = [(x, y) for (y, x) in yx]
    xy = simplify_closed(xy, eps=max(1.0, offset_px * 0.15))
    return chaikin(xy, iters=2)

# ---------- helpers ----------
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: print("  [warn]", " ".join(cmd)[:80], r.stderr[-200:])
    return r.returncode == 0

def spec_pdf(fields, png_path, pdf_path):
    W, H = 1000, 720
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    try: fb = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 40); fr = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 30)
    except Exception: fb = fr = ImageFont.load_default()
    d.text((50, 40), "Sticker — Production Spec", font=fb, fill=(20, 20, 40))
    d.line([(50, 100), (W-50, 100)], fill=(200, 200, 210), width=2)
    y = 140
    for k, v in fields:
        d.text((50, y), k, font=fr, fill=(90, 90, 110)); d.text((360, y), str(v), font=fr, fill=(20, 20, 40)); y += 52
    d.text((50, H-50), "Generated by Curify · factory-ready", font=fr, fill=(150, 150, 160))
    im.save(png_path)
    run(["magick", png_path, pdf_path])

# ---------- main ----------
def export(img_path, mm=60.0, dpi=300, cut_mm=3.0, outdir=None):
    name = os.path.splitext(os.path.basename(img_path))[0]
    outdir = outdir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", name)
    work = os.path.join(outdir, "_pkg"); os.makedirs(work, exist_ok=True)
    im = ensure_cutout(Image.open(img_path))

    # crop to subject bbox
    m = subject_mask(im)
    ys, xs = np.where(m); y0, y1, x0, x1 = ys.min(), ys.max()+1, xs.min(), xs.max()+1
    im = im.crop((x0, y0, x1, y1)); m = m[y0:y1, x0:x1]

    # target pixel size: longest physical side = mm at dpi
    px_per_mm = dpi / 25.4
    long_px = int(round(mm * px_per_mm))
    scale = long_px / max(im.size)
    tw, th = int(round(im.width * scale)), int(round(im.height * scale))
    art = im.resize((tw, th), Image.LANCZOS)
    art.putalpha(Image.fromarray((m * 255).astype("uint8")).resize((tw, th), Image.LANCZOS))
    # zero-out RGB where transparent, keep subject
    art_path = os.path.join(work, "01_artwork.png"); art.save(art_path)

    # cutline on the scaled mask, offset = cut_mm
    m_s = np.array(Image.fromarray((m * 255).astype("uint8")).resize((tw, th), Image.NEAREST)) > 128
    poly = cutline(m_s, offset_px=cut_mm * px_per_mm)
    Wmm, Hmm = tw / px_per_mm, th / px_per_mm
    pts_mm = " ".join(f"{x/px_per_mm:.2f},{y/px_per_mm:.2f}" for x, y in poly)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{Wmm:.2f}mm" height="{Hmm:.2f}mm" '
           f'viewBox="0 0 {Wmm:.2f} {Hmm:.2f}">\n'
           f'  <!-- CutContour spot color; die-cut line -->\n'
           f'  <polygon points="{pts_mm}" fill="none" stroke="#ff00ff" stroke-width="0.25"/>\n</svg>\n')
    svg_path = os.path.join(work, "02_cutline.svg"); open(svg_path, "w").write(svg)

    # CMYK print-ready pdf (ImageMagick; naive convert — swap in an ICC profile for prod)
    cmyk_path = os.path.join(work, "03_artwork_cmyk.pdf")
    run(["magick", art_path, "-background", "white", "-flatten", "-colorspace", "CMYK",
         "-density", str(dpi), cmyk_path])

    # preview: artwork on light bg + cutline overlay
    prev = Image.new("RGBA", (tw, th), (245, 245, 248, 255)); prev.alpha_composite(art)
    pd = ImageDraw.Draw(prev)
    pd.line([tuple(p) for p in poly] + [tuple(poly[0])], fill=(255, 0, 255, 255), width=max(2, int(0.4*px_per_mm)))
    prev_path = os.path.join(work, "04_preview.png"); prev.convert("RGB").save(prev_path)

    # spec
    spec_png = os.path.join(work, "_spec.png"); spec_path = os.path.join(work, "05_spec.pdf")
    spec_pdf([("Product", "Die-cut sticker"), ("Size", f"{Wmm:.0f} × {Hmm:.0f} mm"),
              ("Resolution", f"{dpi} DPI"), ("Color", "CMYK"), ("Cut offset", f"{cut_mm:.1f} mm"),
              ("Bleed", "included in cutline"), ("Files", "artwork PNG · cutline SVG · CMYK PDF"),
              ("Material", "Vinyl / PP (matte or gloss)")], spec_png, spec_path)
    os.remove(spec_png)

    # zip
    zip_path = os.path.join(outdir, f"{name}-sticker-production.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ["01_artwork.png", "02_cutline.svg", "03_artwork_cmyk.pdf", "04_preview.png", "05_spec.pdf"]:
            p = os.path.join(work, f)
            if os.path.exists(p): z.write(p, f)
    print(f"  {name}: {Wmm:.0f}×{Hmm:.0f}mm @{dpi}DPI · cutline pts={len(poly)} · -> {zip_path}")
    return zip_path, prev_path

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("image"); ap.add_argument("--mm", type=float, default=60.0)
    ap.add_argument("--dpi", type=int, default=300); ap.add_argument("--cut-mm", type=float, default=3.0)
    a = ap.parse_args()
    export(a.image, mm=a.mm, dpi=a.dpi, cut_mm=a.cut_mm)
