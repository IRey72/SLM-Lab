"""Cut the hour, minute and sub-dial hands out of tools/hands/source_photo.png.

Writes upright RGBA cut-outs (tip at the top) plus hands.json with each
pivot position, for generate_assets.py to scale and shade.

    python3 tools/extract_hands.py
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

HERE = os.path.join(os.path.dirname(__file__), 'hands')


def hull(points):
    pts = sorted(set(map(tuple, points)))

    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def main():
    im = Image.open(os.path.join(HERE, 'source_photo.png')).convert('RGB')
    a = np.asarray(im).astype(int)
    dark = 255 - a.min(2)
    sat = a.max(2) - a.min(2)
    labels, n = ndimage.label(ndimage.binary_closing(dark > 10, iterations=3))
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
    comps = [i + 1 for i in np.argsort(sizes)[::-1][:3]]
    blue = max(comps, key=lambda c: sat[labels == c].mean())
    silver = sorted((c for c in comps if c != blue), key=lambda c: sizes[c - 1])   # small = hour
    meta = {}
    for name, comp in (('hour', silver[0]), ('minute', silver[1]), ('sub', blue)):
        ys, xs = np.nonzero(labels == comp)
        if name == 'sub':
            mask = (labels == comp) & (dark > 30)
            mask = ndimage.binary_closing(mask, iterations=2)
        else:   # brushed steel is close to the white backdrop: use the convex outline
            m = Image.new('L', im.size, 0)
            ImageDraw.Draw(m).polygon(hull(np.stack([xs, ys], 1)), fill=255)
            mask = np.asarray(m) > 0
        # orientation from the principal axis
        ys, xs = np.nonzero(mask)
        cx, cy = xs.mean(), ys.mean()
        evals, evecs = np.linalg.eigh(np.cov(np.stack([xs - cx, ys - cy])))
        ax = evecs[:, np.argmax(evals)]
        t = (xs - cx) * ax[0] + (ys - cy) * ax[1]
        perp = np.abs(-(xs - cx) * ax[1] + (ys - cy) * ax[0])
        # the tip is the thin end: compare widths of the two outer quarters
        lo_w = perp[t < np.percentile(t, 15)].mean()
        hi_w = perp[t > np.percentile(t, 85)].mean()
        if name == 'sub':   # needle: the tip is the end far from the disc
            disc_t = t[np.argmax(perp)]
            tip_sign = 1 if (t.max() - disc_t) > (disc_t - t.min()) else -1
        else:
            tip_sign = 1 if hi_w < lo_w else -1
        tip_dir = ax * tip_sign
        angle = math.degrees(math.atan2(tip_dir[0], -tip_dir[1]))   # clockwise from up
        alpha = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
        rgba = im.convert('RGBA')
        rgba.putalpha(alpha)
        if name != 'sub':   # see-through pivot hole: white pixels inside the outline
            hole = mask & (dark < 9)
            hole = ndimage.binary_opening(hole, iterations=2)
            hl, hn = ndimage.label(hole)
            if hn:
                big = 1 + int(np.argmax(ndimage.sum(np.ones_like(hl), hl, range(1, hn + 1))))
                hole = ndimage.binary_dilation(hl == big, iterations=2)
                py, px = [v.mean() for v in np.nonzero(hl == big)]
                al = np.asarray(rgba.getchannel('A')).copy()
                al[hole] = 0
                rgba.putalpha(Image.fromarray(al))
        else:   # pivot at the centre of the disc
            sel = np.abs(t - t[np.argmax(perp)]) < 12
            px, py = xs[sel].mean(), ys[sel].mean()
        # rotate upright about the pivot, then crop
        up = rgba.rotate(angle, center=(px, py), resample=Image.BICUBIC)
        box = up.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
        up = up.crop(box)
        meta[name] = {'pivot': [px - box[0], py - box[1]], 'size': list(up.size)}
        up.save(os.path.join(HERE, name + '.png'))
        print(name, up.size, 'pivot', [round(v, 1) for v in meta[name]['pivot']], 'rotated', round(angle, 1))
    json.dump(meta, open(os.path.join(HERE, 'hands.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
