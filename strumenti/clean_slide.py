"""Clean one Rione slide: remove glow/halo from flat-colour text, keep photos untouched.
usage: clean_slide.py src dst
Writes dst (JPEG) and prints a one-line report.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

S = 3
SEEDS = {
    'navy': (2, 42, 76), 'cream': (249, 247, 241), 'white': (252, 252, 250),
    'cyan': (20, 232, 240), 'teal': (0, 178, 196),
}


def palette(img, names):
    a = np.asarray(img).astype(np.float32).reshape(-1, 3)
    g = np.asarray(img.convert('L').filter(ImageFilter.FIND_EDGES)).reshape(-1)
    flat = a[g < 6]
    out = []
    for n in names:
        s = np.array(SEEDS[n], np.float32)
        sel = flat[np.linalg.norm(flat - s, axis=1) < 45]
        out.append(np.median(sel, axis=0) if len(sel) > 300 else s)
    # drop duplicates (e.g. cream ~ white)
    uniq = []
    for c in out:
        if all(np.linalg.norm(c - u) > 12 for u in uniq):
            uniq.append(c)
    return np.array(uniq, np.float32)


def seg_fit(x, pal):
    best = np.full(len(x), 1e9, np.float32)
    lab = np.zeros(len(x), np.uint8)
    n = len(pal)
    for i in range(n):
        for j in range(i + 1, n):
            p, q = pal[i], pal[j]
            v = q - p
            vv = float(v @ v)
            t = np.clip(((x - p) @ v) / vv, 0, 1)
            r = np.linalg.norm(x - (p + t[:, None] * v), axis=1)
            m = r < best
            best[m] = r[m]
            lab[m] = np.where(t[m] < 0.5, i, j)
    return best, lab


def photo_rects(a, pal):
    H, W, _ = a.shape
    r, _ = seg_fit(a.reshape(-1, 3), pal)
    off = (r.reshape(H, W) > 22)
    dens = ndimage.uniform_filter(off.astype(np.float32), 25)
    pm = dens > 0.12
    lbl, n = ndimage.label(pm)
    rects = []
    for k, sl in enumerate(ndimage.find_objects(lbl), 1):
        ys, xs = sl
        area = (lbl[sl] == k).sum()
        if area < 15000:
            continue
        # tighten to rows/cols really occupied by non-flat pixels
        sub = off[ys, xs]
        rows = np.where(sub.mean(1) > 0.35)[0]
        cols = np.where(sub.mean(0) > 0.35)[0]
        if len(rows) == 0 or len(cols) == 0:
            continue
        y0, y1 = ys.start + rows.min(), ys.start + rows.max() + 1
        x0, x1 = xs.start + cols.min(), xs.start + cols.max() + 1
        if (y1 - y0) < 60 or (x1 - x0) < 60:
            continue
        rects.append([max(x0 - 3, 0), max(y0 - 3, 0), min(x1 + 3, W), min(y1 + 3, H)])
    return rects


def main(src, dst):
    img = Image.open(src).convert('RGB')
    W, H = img.size
    a = np.asarray(img).astype(np.float32)
    bg = a[8:40, 8:40].reshape(-1, 3).mean(0)
    dark = bg.mean() < 128
    names = ['navy', 'white', 'cyan', 'cream', 'teal'] if dark else ['cream', 'navy', 'teal', 'cyan', 'white']
    pal = palette(img, names)
    big = np.asarray(img.resize((W * S, H * S), Image.BICUBIC)).astype(np.float32)
    lab = np.zeros(big.shape[:2], np.uint8)
    for y in range(0, big.shape[0], 300):
        blk = big[y:y + 300]
        _, l = seg_fit(blk.reshape(-1, 3), pal)
        lab[y:y + 300] = l.reshape(blk.shape[:2])
    lab = np.asarray(Image.fromarray(lab).filter(ImageFilter.ModeFilter(5)))
    clean = Image.fromarray(pal[lab].clip(0, 255).astype(np.uint8)).resize((W, H), Image.BOX)
    out = clean.copy()
    rects = photo_rects(a, pal)
    for x0, y0, x1, y1 in rects:
        out.paste(img.crop((x0, y0, x1, y1)), (x0, y0))
    out.save(dst, quality=95, subsampling=0)
    print(f"{src.split('/')[-1]} bg={'navy' if dark else 'cream'} pal={len(pal)} photos={rects}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
