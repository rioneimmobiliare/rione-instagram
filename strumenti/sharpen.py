import sys
import numpy as np
from PIL import Image, ImageFilter

S = 3  # supersampling factor
SEEDS = {
    'navy': (2, 38, 72),
    'cream': (250, 248, 242),
    'white': (252, 252, 250),
    'cyan': (25, 235, 240),
    'teal': (0, 175, 195),
}


def palette(img, names, box):
    a = np.asarray(img.crop(box)).astype(np.float32)
    # flat pixels: low local gradient
    g = np.asarray(img.crop(box).convert('L').filter(ImageFilter.FIND_EDGES)).astype(np.float32)
    flat = a[g < 6]
    pal = []
    for n in names:
        s = np.array(SEEDS[n], np.float32)
        d = np.linalg.norm(flat - s, axis=1)
        sel = flat[d < 45]
        c = np.median(sel, axis=0) if len(sel) > 200 else s
        pal.append(c)
    return np.array(pal, np.float32)


def harden(region, pal):
    """region: HxWx3 float at supersampled res. snap each pixel to nearer end of best palette segment."""
    h, w, _ = region.shape
    x = region.reshape(-1, 3)
    best = np.full(len(x), 1e9, np.float32)
    out = np.zeros_like(x)
    n = len(pal)
    for i in range(n):
        for j in range(i + 1, n):
            p, q = pal[i], pal[j]
            v = q - p
            t = np.clip(((x - p) @ v) / (v @ v), 0, 1)
            proj = p + t[:, None] * v
            r = np.linalg.norm(x - proj, axis=1)
            m = r < best
            best[m] = r[m]
            out[m] = np.where((t[m] < 0.5)[:, None], p, q)
    return out.reshape(h, w, 3)


def process(src, dst, names, box):
    img = Image.open(src).convert('RGB')
    pal = palette(img, names, box)
    W, H = img.size
    x0, y0, x1, y1 = box
    crop = img.crop(box)
    big = np.asarray(crop.resize(((x1 - x0) * S, (y1 - y0) * S), Image.BICUBIC)).astype(np.float32)
    res = np.zeros_like(big)
    step = 300
    for y in range(0, big.shape[0], step):
        res[y:y + step] = harden(big[y:y + step], pal)
    small = Image.fromarray(res.clip(0, 255).astype(np.uint8)).resize((x1 - x0, y1 - y0), Image.BOX)
    out = img.copy()
    # feather the bottom edge into the untouched photo when the box doesn't reach the image bottom
    if y1 < H:
        mask = Image.new('L', (x1 - x0, y1 - y0), 255)
        f = 40
        ma = np.asarray(mask).copy()
        for k in range(f):
            ma[-f + k, :] = int(255 * (1 - (k + 1) / f))
        mask = Image.fromarray(ma)
        out.paste(small, (x0, y0), mask)
    else:
        out.paste(small, (x0, y0))
    out.save(dst, quality=95, subsampling=0)
    print(dst, pal.astype(int).tolist())


if __name__ == '__main__':
    src, dst, names, box = sys.argv[1], sys.argv[2], sys.argv[3].split(','), tuple(map(int, sys.argv[4].split(',')))
    process(src, dst, names, box)
