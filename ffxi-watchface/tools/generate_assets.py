"""Render the FFXI "We Are Vana'diel" chronograph-style watch face assets.

Writes PNGs into app/src/main/res/drawable-nodpi/ plus a composited
preview. All art is drawn at SS x supersampling and downscaled.

    python3 tools/generate_assets.py
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

N = 450            # watch face canvas (matches watchface.xml)
SS = 4             # supersampling factor
C = N * SS / 2     # canvas centre in supersampled px
OUT = os.path.join(os.path.dirname(__file__), '..', 'app', 'src', 'main', 'res', 'drawable-nodpi')

FONTS = os.path.join(os.path.dirname(__file__), 'fonts')
FONT_SERIF = os.path.join(FONTS, 'Cinzel-Bold.ttf')      # XI, wordmark, date
FONT_LABEL = os.path.join(FONTS, 'Cinzel-SemiBold.ttf')  # nation names, day names
FONT_NUM = os.path.join(FONTS, 'Oswald-SemiBold.ttf')    # sub-dial numerals
FONT_FF = os.path.join(FONTS, 'FinalFantasy.ttf')        # caps only; no digits/space/'
EMBLEMS = os.path.join(os.path.dirname(__file__), 'emblems')  # square crops of the nation crests

# Layout (in 450px units) -- keep in sync with watchface.xml
SUB_OFFSET = 100   # sub-dial centre distance from main centre
SUB_R = 56         # sub-dial radius
EMBLEM_R = 33      # crest medallion radius inside each sub-dial
DATE_POS = (225 + 103, 225 + 103)  # date window centre (4:30)
DATE_SIZE = (34, 24)

NAVY_IN, NAVY_OUT = (30, 48, 84), (6, 11, 24)
# Nation colours: San d'Oria red, Bastok blue, Windurst green
NATIONS = {
    'sandoria': ((150, 28, 38), (70, 10, 16)),
    'bastok': ((36, 84, 168), (12, 32, 78)),
    'windurst': ((34, 120, 66), (10, 50, 26)),
}


def s(v):
    return v * SS


def polar(r, deg, cx=C, cy=C):
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def font(path, size):
    return ImageFont.truetype(path, int(size * SS))


def text_c(d, xy, txt, f, fill, **kw):
    d.text(xy, txt, font=f, fill=fill, anchor='mm', **kw)


def text_ff(d, xy, txt, size, fill, stroke=0, stroke_fill=None):
    """Centre txt in the Final Fantasy font, falling back to Cinzel for missing glyphs."""
    ff, fb = font(FONT_FF, size), font(FONT_SERIF, size * 0.8)
    have = set(chr(c) for c in _ff_cmap())
    runs = []
    for ch in txt:
        f = ff if ch in have else fb
        runs.append((ch, f, d.textlength(ch, font=f) if ch != ' ' else size * SS * 0.35))
    x = xy[0] - sum(w for *_, w in runs) / 2
    for ch, f, w in runs:
        if ch != ' ':
            d.text((x, xy[1]), ch, font=f, fill=fill, anchor='lm',
                   stroke_width=stroke, stroke_fill=stroke_fill)
        x += w


_FF_CMAP = None


def _ff_cmap():
    global _FF_CMAP
    if _FF_CMAP is None:
        from fontTools.ttLib import TTFont
        _FF_CMAP = list(TTFont(FONT_FF).getBestCmap())
    return _FF_CMAP


def radial_gradient(size, inner, outer, cx=None, cy=None, r=None):
    w, h = size
    cx = w / 2 if cx is None else cx
    cy = h / 2 if cy is None else cy
    r = min(w, h) / 2 if r is None else r
    y, x = np.mgrid[0:h, 0:w]
    t = np.clip(np.hypot(x - cx, y - cy) / r, 0, 1)[..., None] ** 1.3
    rgb = np.array(inner) * (1 - t) + np.array(outer) * t
    return Image.fromarray(rgb.astype(np.uint8), 'RGB').convert('RGBA')


def circle_mask(size, cx, cy, r):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    return m


def finish(img):
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


# ------------------------------------------------------------------ lighting
# One light source, top-left (315 deg clockwise from 12): raised parts are bright
# on that side, recesses on the opposite side, and shadows fall down-right.
LIGHT_DEG = 315
SHADOW_DXY = (1.0, 1.6)


def angle_map(size, cx, cy):
    """Clockwise-from-12 angle (radians) of every pixel around (cx, cy)."""
    h, w = size[1], size[0]
    y, x = np.mgrid[0:h, 0:w]
    return np.arctan2(x - cx, -(y - cy))


def conic(size, cx, cy, dark, bright, light_deg=LIGHT_DEG, power=1.5):
    """Metal ring shading: bright towards light_deg, dark opposite."""
    t = (0.5 + 0.5 * np.cos(angle_map(size, cx, cy) - math.radians(light_deg))) ** power
    rgb = np.array(dark) + (np.array(bright) - np.array(dark)) * t[..., None]
    return Image.fromarray(rgb.astype(np.uint8), 'RGB').convert('RGBA')


def vgrad(size, stops, y0=0, y1=None):
    """Vertical gradient through (t, rgb) stops between rows y0 and y1."""
    w, h = size
    y1 = h if y1 is None else y1
    t = np.clip((np.arange(h) - y0) / max(1, y1 - y0), 0, 1)
    ts = [p for p, _ in stops]
    col = np.stack([np.interp(t, ts, [c[i] for _, c in stops]) for i in range(3)], -1)
    rgb = np.repeat(col[:, None, :], w, axis=1)
    return Image.fromarray(rgb.astype(np.uint8), 'RGB').convert('RGBA')


def lgrad(size, p0, p1, stops):
    """Linear gradient along p0 -> p1 through (t, rgb) stops."""
    w, h = size
    y, x = np.mgrid[0:h, 0:w]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    t = np.clip(((x - p0[0]) * dx + (y - p0[1]) * dy) / (dx * dx + dy * dy), 0, 1)
    ts = [p for p, _ in stops]
    rgb = np.stack([np.interp(t, ts, [c[i] for _, c in stops]) for i in range(3)], -1)
    return Image.fromarray(rgb.astype(np.uint8), 'RGB').convert('RGBA')


def fill_mask(img, mask, fill):
    """Composite fill (RGBA image or colour) onto img through an L mask."""
    if not isinstance(fill, Image.Image):
        fill = Image.new('RGBA', img.size, fill)
    layer = fill.copy()
    layer.putalpha(Image.fromarray((np.asarray(fill.getchannel('A'), float) *
                                    np.asarray(mask, float) / 255).astype(np.uint8)))
    img.alpha_composite(layer)


def drop_shadow(img, mask, blur=1.6, alpha=0.6, dxy=SHADOW_DXY):
    sh = Image.new('L', img.size, 0)
    sh.paste(mask, (round(s(dxy[0])), round(s(dxy[1]))))
    sh = sh.filter(ImageFilter.GaussianBlur(s(blur))).point(lambda v: int(v * alpha))
    fill_mask(img, sh, (0, 0, 0, 255))


def inner_shadow(img, mask, depth=2.2, blur=1.6, alpha=0.75):
    """Shadow cast by the rim onto a recessed area (top-left inside edge)."""
    shifted = Image.new('L', img.size, 0)
    shifted.paste(mask, (round(s(depth * 0.6)), round(s(depth))))
    crescent = Image.fromarray(np.clip(np.asarray(mask, int) - np.asarray(shifted, int), 0, 255).astype(np.uint8))
    crescent = crescent.filter(ImageFilter.GaussianBlur(s(blur)))
    sh = Image.fromarray((np.asarray(crescent, float) * np.asarray(mask, float) / 255 * alpha).astype(np.uint8))
    fill_mask(img, sh, (0, 0, 0, 255))


def ring_mask(size, cx, cy, r_out, r_in):
    m = circle_mask(size, cx, cy, r_out)
    ImageDraw.Draw(m).ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=0)
    return m


def metal_ring(img, cx, cy, r_out, r_in, dark, bright, recessed=False):
    light = LIGHT_DEG + (180 if recessed else 0)
    fill_mask(img, ring_mask(img.size, cx, cy, r_out, r_in), conic(img.size, cx, cy, dark, bright, light))


GOLD_STOPS = [(0, (255, 232, 150)), (0.45, (226, 182, 82)), (0.55, (176, 128, 42)), (1, (236, 196, 104))]


def applied_text(img, draw_fn, stops=GOLD_STOPS, shadow=True):
    """Raised metal lettering: draw_fn(draw, fill) paints a mask; filled with a gradient + shadow."""
    m = Image.new('L', img.size, 0)
    draw_fn(ImageDraw.Draw(m), 255)
    box = m.getbbox()
    if not box:
        return
    if shadow:
        drop_shadow(img, m, blur=0.7, alpha=0.7, dxy=(0.6, 1.0))
    fill_mask(img, m, vgrad(img.size, stops, box[1], box[3]))


# --------------------------------------------------------------------- crystals
CRYSTAL_R = (140, 204)   # 12 o'clock crystal spans these radii


def load_crystal(height):
    cr = Image.open(os.path.join(EMBLEMS, 'crystal.png')).convert('RGBA')
    return cr.resize((round(height * cr.width / cr.height), round(height)), Image.LANCZOS)


# Gem line drawing for the outline styles: outer outline, inner table, and facet
# lines joining them. Points are (x in widths, y in half-heights), mirrored left/right.
GEM_OUTER = [(0, -1), (0.34, -0.66), (0.5, -0.12), (0.47, 0.42), (0.3, 0.84), (0, 1)]
GEM_TABLE = [(0, -0.6), (0.17, -0.38), (0.25, -0.06), (0.23, 0.3), (0.14, 0.58), (0, 0.7)]


def crystal_lines(img, bright=1.0):
    """The 12 o'clock crystal as white minimal line art (more detailed than plain markers)."""
    h = s(CRYSTAL_R[1] - CRYSTAL_R[0])
    w = h * 0.43
    cx, cy = C, C - s((CRYSTAL_R[0] + CRYSTAL_R[1]) / 2)

    def ring(pts):
        right = [(cx + x * w, cy + y * h / 2) for x, y in pts]
        left = [(cx - x * w, cy + y * h / 2) for x, y in pts[-2:0:-1]]
        return right + left
    outer, table = ring(GEM_OUTER), ring(GEM_TABLE)
    col = tuple(int(c * bright) for c in (236, 242, 255))
    thin = tuple(int(c * bright * 0.75) for c in (236, 242, 255))
    d = ImageDraw.Draw(img)
    d.polygon(outer, fill=(0, 0, 0, 255))
    n = len(outer)
    for i in range(n):   # facets: each table corner to its outer corner and the next one
        d.line([table[i], outer[i]], fill=thin, width=round(s(0.8)))
        d.line([table[i], outer[(i + 1) % n]], fill=thin, width=round(s(0.6)))
    d.line([table[0], table[n // 2]], fill=thin, width=round(s(0.6)))
    d.line(table + table[:1], fill=col, width=round(s(1.0)), joint='curve')
    d.line(outer + outer[:1], fill=col, width=round(s(1.4)), joint='curve')


def place_crystal(img, ambient, bright=1.0):
    """The big blue crystal at 12, from tools/emblems/crystal.png (background already cut out)."""
    if ambient:
        crystal_lines(img, bright)
        return
    cr = load_crystal(s(CRYSTAL_R[1] - CRYSTAL_R[0]))
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    layer.paste(cr, (round(C - cr.width / 2), round(C - s(CRYSTAL_R[1]))))
    if not ambient:
        drop_shadow(img, layer.getchannel('A'), blur=1.8, alpha=0.7)
    img.alpha_composite(layer)


# --------------------------------------------------------------------- dial
def sub_centers():
    return {
        'sandoria': (225 - SUB_OFFSET, 225),   # 9 o'clock: day of week
        'bastok': (225 + SUB_OFFSET, 225),     # 3 o'clock: battery
        'windurst': (225, 225 + SUB_OFFSET),   # 6 o'clock: 24 hour
    }


def crest_masks(key, a):
    """(figure, accent, detail) masks for a crest at source resolution, from its colours."""
    from scipy import ndimage

    def keep(m, min_size):
        lab, n = ndimage.label(m)
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        return np.isin(lab, [i + 1 for i, sz in enumerate(sizes) if sz >= min_size])

    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    detail = np.zeros(a.shape[:2], bool)
    if key == 'sandoria':   # black griffins; gold crown, spears and spear tips
        fig = keep(a.max(2) < 100, 300)
        acc = keep(((r > 160) & (g > 100) & (b < 150) & (g > b + 30)) | (a.min(2) > 190), 40)
        # the dimmer gold feather and outline work on the griffins
        goldish = (r > 110) & (g > 55) & (b < 110) & (g > b + 15) & (r > g)
        detail = goldish & ndimage.binary_dilation(fig, iterations=4) & ~acc
    elif key == 'bastok':   # navy gear and bottles; light-blue rims, bars and white dots
        fig = keep((b > 70) & (r < 80) & (g < 80) & (b > r + 40), 200)
        light = (b > 180) & (r < 150) & (g > 70) & (b > r + 60)
        greyblue = (b > 130) & (g > 100) & (r < 130) & (b > r + 30) & ~light
        white = (a.min(2) > 170) & (b >= r - 5) & (b > g - 5)
        yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
        rr = np.hypot(xx - a.shape[1] / 2, yy - a.shape[0] / 2)
        dots = ndimage.binary_dilation(ndimage.binary_opening(white & (rr > a.shape[0] * 0.32), iterations=2), iterations=3)
        acc = (keep(light | greyblue, 20) | dots) & (rr < a.shape[0] * 0.47)
    else:                   # windurst: green star tree; yellow stars
        star = (r > 170) & (g > 170) & (b < 110)
        fig = keep((g > r + 25) & ~star, 300)
        acc = keep(star, 30)
    return fig, acc, detail


def crest_art(key, size, bright=1.0):
    """Crest for the outline styles, the same treatment for every nation: the main figure
    as a grey silhouette with a light edge, accents (crown, stars, rims...) bright."""
    from scipy import ndimage
    a = np.asarray(Image.open(os.path.join(EMBLEMS, key + '.png')).convert('RGB')).astype(int)
    fig, acc, detail = crest_masks(key, a)

    def soft_mask(m, sigma, thresh):
        f = ndimage.gaussian_filter(m.astype(float), sigma)
        f = Image.fromarray((np.clip(f, 0, 1) * 255).astype(np.uint8)).resize(size, Image.LANCZOS)
        return np.asarray(f) > thresh * 255

    fine = detail.any()   # crests with interior detail keep finer shapes so it survives
    fig = soft_mask(fig, 0.9 if fine else 2.2, 0.5)
    acc = soft_mask(acc, 1.0 if fine else 1.2, 0.45)
    edge = fig & ~ndimage.binary_erosion(fig, iterations=2 if fine else 3)
    v = np.where(fig, 70 if fine else 85, 0) + np.where(edge, 130 if fine else 120, 0)
    if fine:
        v = np.where(soft_mask(detail, 0.7, 0.35), 175, v)
    v = np.where(acc, 235 if fine else 230, v)
    v = np.clip(v, 0, 255) * bright
    return Image.fromarray(v.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)).convert('RGB')


def draw_emblem(img, key, cx, cy, ambient, bright=1.0):
    """Nation crest in a round medallion at the sub-dial centre."""
    r = s(EMBLEM_R)
    em = Image.open(os.path.join(EMBLEMS, key + '.png')).convert('RGB').resize((2 * r, 2 * r), Image.LANCZOS)
    if ambient:   # engraved line art: readable on black and keeps few pixels lit
        em = crest_art(key, em.size, bright)
    img.paste(em, (int(cx - r), int(cy - r)), circle_mask((2 * r, 2 * r), r, r, r))
    if ambient:
        ImageDraw.Draw(img).ellipse([cx - r, cy - r, cx + r, cy + r], outline=(90, 90, 90), width=round(s(1.4)))
        return
    inner_shadow(img, circle_mask(img.size, cx, cy, r), depth=1.4, blur=1.0, alpha=0.55)
    drop_shadow(img, ring_mask(img.size, cx, cy, r + s(1.8), r - s(0.2)), blur=0.8, alpha=0.6, dxy=(0.5, 0.8))
    metal_ring(img, cx, cy, r + s(1.8), r - s(0.2), (120, 84, 24), (255, 230, 150))


def draw_subdial(img, key, ambient=False, bright=1.0):
    cx, cy = (s(v) for v in sub_centers()[key])
    R = s(SUB_R)
    d = ImageDraw.Draw(img)
    fg = (150, 150, 150) if ambient else (240, 240, 240)
    if not ambient:
        inner, outer = NATIONS[key]
        g = radial_gradient((2 * R, 2 * R), inner, outer)
        rings = Image.new('RGBA', g.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(rings)
        for rr in range(s(2), R, round(s(2.5))):     # azurage / snailing rings
            rd.ellipse([R - rr, R - rr, R + rr, R + rr], outline=(255, 255, 255, 14), width=SS)
        g.alpha_composite(rings)
        img.paste(g, (int(cx - R), int(cy - R)), circle_mask((2 * R, 2 * R), R, R, R))
        inner_shadow(img, circle_mask(img.size, cx, cy, R), depth=2.6, blur=2.0, alpha=0.8)
        metal_ring(img, cx, cy, R + s(2.4), R, (70, 76, 88), (238, 242, 248), recessed=True)
    else:
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(110, 110, 110), width=round(s(1.2)))
    draw_emblem(img, key, cx, cy, ambient, bright)
    d = ImageDraw.Draw(img)

    small = font(FONT_LABEL, 8)
    num = font(FONT_NUM, 8.5)
    tick_r0, tick_r1, lab_r = R - s(3), R - s(6.5), R - s(13.5)
    if key == 'sandoria':
        days = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA']
        for i, lab in enumerate(days):
            a = i * 360 / 7
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1, a, cx, cy)], fill=fg, width=round(s(1.4)))
            text_c(d, polar(lab_r, a, cx, cy), lab, small, fg)
    elif key == 'bastok':
        for i in range(11):
            a = -150 + i * 30
            long_ = i % 5 == 0
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1 - (s(1) if long_ else 0), a, cx, cy)],
                   fill=fg, width=round(s(1.6 if long_ else 1)))
        for val, a in (('E', -150), ('½', 0), ('F', 150)):
            text_c(d, polar(lab_r, a, cx, cy), val, num, fg)
    else:
        for i in range(24):
            a = i * 15
            long_ = i % 6 == 0
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1 - (s(1) if long_ else s(-2)), a, cx, cy)],
                   fill=fg, width=round(s(1.6 if long_ else 0.8)))
        for val, a in (('24', 0), ('6', 90), ('12', 180), ('18', 270)):
            text_c(d, polar(lab_r, a, cx, cy), val, num, fg)


def sunburst(size):
    """Navy sunburst: radial brushing that brightens in a bow-tie along the light axis."""
    base = np.asarray(radial_gradient(size, NAVY_IN, NAVY_OUT, r=s(225)).convert('RGB'), float)
    th = angle_map(size, C, C)
    sheen = 1 + 0.32 * np.cos(2 * (th - math.radians(LIGHT_DEG)))
    rng = np.random.default_rng(11)
    streaks = rng.normal(0, 1, 4096)
    streaks = np.convolve(streaks, np.ones(3) / 3, mode='same')
    idx = ((th + math.pi) / (2 * math.pi) * 4096).astype(int) % 4096
    sheen = sheen * (1 + 0.05 * streaks[idx])
    out = np.clip(base * sheen[..., None] + 6 * (sheen[..., None] - 1), 0, 255)
    return Image.fromarray(out.astype(np.uint8), 'RGB').convert('RGBA')


def make_dial(ambient=False, bright=0.6):
    """ambient=False: classic dial. ambient=True: outline dial; bright=1 is the
    Dark style (active), bright=0.6 the always-on version of both styles."""
    size = (s(N), s(N))
    if ambient:
        img = Image.new('RGBA', size, (0, 0, 0, 255))
    else:
        img = sunburst(size)
        # chapter ring: dark gunmetal, stepped down from the dial with a bright chamfer
        metal_ring(img, C, C, s(226), s(206), (10, 13, 19), (58, 64, 78))
        inner_shadow(img, ring_mask(size, C, C, s(226), s(206)), depth=1.2, blur=1.0, alpha=0.5)
        metal_ring(img, C, C, s(206.5), s(204.5), (60, 66, 80), (210, 216, 228), recessed=True)
    d = ImageDraw.Draw(img)

    for i in range(60):
        a = i * 6
        five = i % 5 == 0
        if ambient and not five:
            continue
        col = (120, 120, 120) if ambient else ((240, 240, 240) if five else (170, 176, 186))
        d.line([polar(s(222), a), polar(s(211 if five else 216), a)], fill=col, width=round(s(2.2 if five else 1)))

    # 12 = crystal, 11 = "XI"
    if not ambient:
        glow = Image.new('RGBA', size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([C - s(24), C - s(208), C + s(24), C - s(136)], fill=(60, 110, 255, 150))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s(9))))
    place_crystal(img, ambient, bright)
    d = ImageDraw.Draw(img)

    pos = polar(s(180), 330)
    if ambient:   # crystal-blue outline numeral
        blue = tuple(int(c * (0.6 + 0.4 * bright)) for c in (110, 155, 255))
        text_ff(d, pos, 'XI', 34, (14, 26, 70), stroke=round(s(1)), stroke_fill=blue)
    else:
        # applied (raised) gold numeral and wordmark; small print stays flat like pad printing
        applied_text(img, lambda dd, f: text_ff(dd, pos, 'XI', 34, f))
        applied_text(img, lambda dd, f: text_ff(dd, (C, C - s(99)), "VANA'DIEL", 23, f))
        d = ImageDraw.Draw(img)
        text_c(d, (C, C - s(118)), 'WE ARE', font(FONT_LABEL, 8), (200, 206, 218))

    for key in NATIONS:
        draw_subdial(img, key, ambient, bright)

    # date window frame (number drawn live by the watch face)
    if ambient and bright >= 1:
        x, y = s(DATE_POS[0]), s(DATE_POS[1])
        w, h = s(DATE_SIZE[0]), s(DATE_SIZE[1])
        ImageDraw.Draw(img).rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=s(3),
                                              outline=(150, 150, 150), width=round(s(1.2)))
    if not ambient:
        x, y = s(DATE_POS[0]), s(DATE_POS[1])
        w, h = s(DATE_SIZE[0]), s(DATE_SIZE[1])
        frame = Image.new('L', size, 0)
        ImageDraw.Draw(frame).rounded_rectangle([x - w / 2 - s(2.2), y - h / 2 - s(2.2), x + w / 2 + s(2.2),
                                                 y + h / 2 + s(2.2)], radius=s(4), fill=255)
        win = Image.new('L', size, 0)
        ImageDraw.Draw(win).rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=s(3), fill=255)
        # chamfered cut-out: dark on the lit side, bright on the far side
        fill_mask(img, frame, lgrad(size, (x - w / 2, y - h / 2), (x + w / 2, y + h / 2),
                                    [(0, (60, 66, 80)), (0.5, (140, 148, 162)), (1, (232, 236, 244))]))
        fill_mask(img, win, vgrad(size, [(0, (226, 222, 212)), (1, (248, 246, 240))], y - h / 2, y + h / 2))
        inner_shadow(img, win, depth=2.0, blur=1.4, alpha=0.6)

    img.putalpha(circle_mask(size, C, C, s(225)))
    return img


# --------------------------------------------------------------------- hands
HAND_PAD = 5   # room around each hand for its soft shadow


def hand_canvas(w, tip, tail, pad=HAND_PAD):
    """Canvas for a hand whose pivot is at (w/2 + pad, tip + pad)."""
    img = Image.new('RGBA', (round(s(w + 2 * pad)), round(s(tip + tail + 2 * pad))), (0, 0, 0, 0))
    return img, s(w / 2 + pad), s(tip + pad)


def with_shadow(img, blur=1.8, alpha=0.55):
    """Soft halo shadow under a rotating hand (no offset, so it reads right at any angle)."""
    sh = img.getchannel('A').filter(ImageFilter.GaussianBlur(s(blur))).point(lambda v: int(v * alpha))
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.putalpha(sh)
    out.alpha_composite(img)
    return out


def poly_mask(size, pts):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m


PHOTO_HANDS = os.path.join(os.path.dirname(__file__), 'hands')   # from tools/extract_hands.py


_PHOTO_CACHE = {}


def prepare_photo(name, tip, thin=1.0):
    """Scaled, straightened cut-out of a photographed hand at supersampled size.

    Every row is shifted so the hand's centre line runs exactly through the pivot
    (the photo is slightly off-axis), the pivot hole is filled with steel so the
    centre stays clean, and thin < 1 narrows the hand. Returns (rgba, pivot_x, pivot_y).
    """
    key = (name, tip, thin)
    if key in _PHOTO_CACHE:
        return _PHOTO_CACHE[key]
    from scipy import ndimage
    meta = json.load(open(os.path.join(PHOTO_HANDS, 'hands.json')))[name]
    src = Image.open(os.path.join(PHOTO_HANDS, name + '.png')).convert('RGBA')
    k = s(tip) / meta['pivot'][1]
    w = round(src.width * k * thin)
    src = src.resize((w, round(src.height * k)), Image.LANCZOS)
    a = np.asarray(src).astype(float)
    solid = a[..., 3] > 8
    hole = ndimage.binary_fill_holes(solid) & ~solid
    if hole.any():
        steel = np.median(a[solid & (a[..., 3] > 200)][:, :3], axis=0)
        a[hole, :3] = steel
        a[hole, 3] = 255
    # pad so rows can shift, then centre every row on the pivot column
    pad = round(w * 0.5) + SS
    a = np.pad(a, ((0, 0), (pad, pad), (0, 0)))
    target = pad + w / 2
    for y in range(a.shape[0]):
        xs = np.nonzero(a[y, :, 3] > 128)[0]
        if len(xs):
            a[y] = np.roll(a[y], round(target - (xs[0] + xs[-1]) / 2), axis=0)
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA')
    box = img.getchannel('A').getbbox()
    half = max(target - box[0], box[2] - target)
    img = img.crop((round(target - half), 0, round(target + half), img.height))
    _PHOTO_CACHE[key] = (img, img.width / 2, meta['pivot'][1] * k)
    return _PHOTO_CACHE[key]


def photo_hand(name, tip, thin=1.0, pad=HAND_PAD, blur=1.8, alpha=0.55):
    """A photographed hand on a padded canvas, pivot centred, with a soft shadow."""
    src, sx, sy = prepare_photo(name, tip, thin)
    w, tail = photo_geom(name, tip, thin)
    img, px, py = hand_canvas(w, tip, tail, pad)
    img.alpha_composite(src, (round(px - sx), round(py - sy)))
    return with_shadow(img, blur, alpha)


def photo_geom(name, tip, thin=1.0):
    """(visual width, tail length) in 450px units; even width keeps XML coordinates whole."""
    src, sx, sy = prepare_photo(name, tip, thin)
    w = 2 * math.ceil(sx / SS)
    tail = math.ceil((src.height - sy) / SS) + 1
    return w, tail


def domed_cap(r, pad=HAND_PAD):
    """Static polished centre cap with a blued pin, drawn above the hands."""
    size = s(2 * (r + pad))
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c = size / 2
    # polished steel: soft highlight towards the light, crisp darker rim
    hl = radial_gradient(img.size, (250, 252, 255), (150, 158, 172), cx=c - s(r * 0.3), cy=c - s(r * 0.35), r=s(r * 1.4))
    fill_mask(img, circle_mask(img.size, c, c, s(r)), hl)
    d = ImageDraw.Draw(img)
    d.ellipse([c - s(r), c - s(r), c + s(r), c + s(r)], outline=(70, 76, 90), width=round(s(0.8)))
    pin = s(r * 0.38)
    fill_mask(img, circle_mask(img.size, c, c, pin),
              radial_gradient(img.size, (120, 170, 255), (20, 50, 130), cx=c - pin * 0.3, cy=c - pin * 0.3, r=pin * 1.3))
    return with_shadow(img, blur=0.9, alpha=0.5)


def outline_hand(tip, tail, w, stroke=1.4, pad=2, color=(225, 225, 225)):
    """Minimal Dark-style hand: a slim lance drawn as an outline, hollow (black) inside."""
    img, px, py = hand_canvas(w, tip, tail, pad)
    half = s(w) / 2
    pts = [(px, py - s(tip)), (px + half, py - s(tip) * 0.2), (px + half * 0.35, py + s(tail)),
           (px - half * 0.35, py + s(tail)), (px - half, py - s(tip) * 0.2)]
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=(0, 0, 0, 255))
    d.line(pts + pts[:1], fill=color, width=round(s(stroke)), joint='curve')
    return img


def needle_hand(tip, tail, stroke=1.3, ring=3.2, pad=2, color=(225, 225, 225)):
    """Minimal Dark-style sub-dial hand: a hairline with a hollow pivot ring."""
    img, px, py = hand_canvas(8, tip, tail, pad)
    d = ImageDraw.Draw(img)
    d.line([(px, py - s(tip)), (px, py - s(ring))], fill=color, width=round(s(stroke)))
    d.line([(px, py + s(ring)), (px, py + s(tail))], fill=color, width=round(s(stroke)))
    d.ellipse([px - s(ring), py - s(ring), px + s(ring), py + s(ring)], fill=(0, 0, 0, 255),
              outline=color, width=round(s(stroke)))
    return img


def outline_cap(r, pad=2, color=(225, 225, 225)):
    size = s(2 * (r + pad))
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c = size / 2
    d = ImageDraw.Draw(img)
    d.ellipse([c - s(r), c - s(r), c + s(r), c + s(r)], fill=(0, 0, 0, 255), outline=color, width=round(s(1.4)))
    d.ellipse([c - s(1.3), c - s(1.3), c + s(1.3), c + s(1.3)], fill=color)
    return img


CAP_R = 6
CAPS = {
    # name: (builder, canvas half-size in 450px units)
    'cap': (lambda: domed_cap(CAP_R), CAP_R + HAND_PAD),
    'cap_dark': (lambda: outline_cap(5), 5 + 2),
}


def _photo(name, tip, thin=1.0, pad=HAND_PAD, **kw):
    w, tail = photo_geom(name, tip, thin)
    return (lambda: photo_hand(name, tip, thin, pad, **kw), w, tip, tail, pad)


HANDS = {
    # name: (builder, visual width, tip length, tail length, shadow padding)
    'hand_hour': _photo('hour', 118, thin=0.48),
    'hand_minute': _photo('minute', 182, thin=0.5),
    'hand_sub': _photo('sub', 46, pad=3, blur=1.0, alpha=0.6),
    # Dark style: thin outline hands
    'hand_hour_dark': (lambda: outline_hand(112, 16, 10), 10, 112, 16, 2),
    'hand_minute_dark': (lambda: outline_hand(180, 20, 8), 8, 180, 20, 2),
    'hand_sub_dark': (lambda: needle_hand(44, 10), 8, 44, 10, 2),
}


def hand_geom(name):
    """(canvas width, pivot-from-top, canvas height) in 450px units."""
    _, w, tip, tail, pad = HANDS[name]
    return w + 2 * pad, tip + pad, tip + tail + 2 * pad


def patch_xml():
    """Write hand / cap geometry into watchface.xml so it always matches the PNGs."""
    import re
    path = os.path.join(os.path.dirname(__file__), '..', 'app', 'src', 'main', 'res', 'raw', 'watchface.xml')
    xml = open(path).read()

    def setattrs(pattern, cx, cy, name):
        nonlocal xml
        W, P, H = hand_geom(name)
        vals = {'x': cx - W / 2, 'y': cy - P, 'width': W, 'height': H, 'pivotY': P / H}

        def sub(m):
            tag = m.group(0)
            for k, v in vals.items():
                v = f'{v:.4f}' if k == 'pivotY' else f'{v:g}'
                tag = re.sub(rf'\b{k}="[^"]*"', f'{k}="{v}"', tag)
            return tag
        xml, n = re.subn(pattern, sub, xml)
        assert n == 1, pattern

    for sfx in ('', '_dark'):
        setattrs(rf'<HourHand resource="hand_hour{sfx}" [^>]*>', 225, 225, 'hand_hour' + sfx)
        setattrs(rf'<MinuteHand resource="hand_minute{sfx}" [^>]*>', 225, 225, 'hand_minute' + sfx)
        for key, (cx, cy) in sub_centers().items():
            setattrs(rf'<PartImage name="sub_{key}{sfx}" [^>]*>', cx, cy, 'hand_sub' + sfx)
    for name, (_, half) in CAPS.items():
        xml, n = re.subn(rf'(<PartImage name="{name}" )[^>]*>',
                         rf'\g<1>x="{225 - half:g}" y="{225 - half:g}" width="{2 * half:g}" height="{2 * half:g}">', xml)
        assert n == 1, name
    open(path, 'w').write(xml)


def make_glass():
    """Crystal-glass overlay: a soft reflection arc top-left and a darker rim."""
    size = (s(N), s(N))
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    refl = circle_mask(size, C - s(40), C - s(60), s(200))
    ImageDraw.Draw(refl).ellipse([C - s(40) - s(175), C - s(10) - s(175), C - s(40) + s(175), C - s(10) + s(175)], fill=0)
    refl = Image.fromarray((np.asarray(refl, float) * np.asarray(circle_mask(size, C, C, s(222)), float) / 255).astype(np.uint8))
    refl = refl.filter(ImageFilter.GaussianBlur(s(6))).point(lambda v: int(v * 0.10))
    fill_mask(img, refl, (255, 255, 255, 255))
    rim = ring_mask(size, C, C, s(226), s(214)).filter(ImageFilter.GaussianBlur(s(4))).point(lambda v: int(v * 0.35))
    fill_mask(img, rim, (0, 0, 0, 255))
    img.putalpha(Image.fromarray(np.minimum(np.asarray(img.getchannel('A')), np.asarray(circle_mask(size, C, C, s(225))))))
    return img


# --------------------------------------------------------------------- preview
def place(canvas, hand, name, cx, cy, deg):
    W, P, _ = hand_geom(name)
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    layer.paste(hand, (round(s(cx - W / 2)), round(s(cy - P))))
    canvas.alpha_composite(layer.rotate(-deg, center=(s(cx), s(cy)), resample=Image.BICUBIC))


def preview(dial_hi, hands_hi, caps_hi, glass_hi, hh=10, mm=8, ss=32, dow=5, day=29, batt=78, ambient=False, dark=False):
    img = dial_hi.copy()
    sfx = '_dark' if dark else ''
    cap_hi = caps_hi['cap' + sfx]
    sub = hands_hi['hand_sub' + sfx]
    centers = sub_centers()
    place(img, sub, 'hand_sub' + sfx, *centers['sandoria'], (dow - 1) * 360 / 7)
    place(img, sub, 'hand_sub' + sfx, *centers['bastok'], -150 + batt * 3)
    place(img, sub, 'hand_sub' + sfx, *centers['windurst'], (hh + mm / 60) * 15)
    if not ambient or dark:
        d = ImageDraw.Draw(img)
        text_c(d, (s(DATE_POS[0]), s(DATE_POS[1])), str(day), font(FONT_SERIF, 15),
               (190, 190, 190) if dark else (20, 20, 20))
    place(img, hands_hi['hand_hour' + sfx], 'hand_hour' + sfx, 225, 225, (hh % 12 + mm / 60) * 30)
    place(img, hands_hi['hand_minute' + sfx], 'hand_minute' + sfx, 225, 225, mm * 6 + ss / 10)
    img.alpha_composite(cap_hi, (round(C - cap_hi.width / 2), round(C - cap_hi.height / 2)))
    if not ambient and not dark:
        img.alpha_composite(glass_hi)
    return finish(img)


def main():
    os.makedirs(OUT, exist_ok=True)
    dial_hi = make_dial()
    amb_hi = make_dial(ambient=True)
    dark_hi = make_dial(ambient=True, bright=1.0)
    finish(dial_hi).save(os.path.join(OUT, 'dial.png'))
    finish(amb_hi).save(os.path.join(OUT, 'dial_ambient.png'))
    finish(dark_hi).save(os.path.join(OUT, 'dial_dark.png'))
    hands_hi = {}
    for name, (build, *_rest) in HANDS.items():
        hands_hi[name] = build()
        finish(hands_hi[name]).save(os.path.join(OUT, name + '.png'))
    cap_hi = {}
    for name, (build, _) in CAPS.items():
        cap_hi[name] = build()
        finish(cap_hi[name]).save(os.path.join(OUT, name + '.png'))
    glass_hi = make_glass()
    finish(glass_hi).save(os.path.join(OUT, 'glass.png'))
    patch_xml()
    active = preview(dial_hi, hands_hi, cap_hi, glass_hi)
    active.save(os.path.join(OUT, 'preview.png'))
    docs = os.path.join(os.path.dirname(__file__), '..', 'docs')
    os.makedirs(docs, exist_ok=True)
    active.save(os.path.join(docs, 'preview_active.png'))
    preview(amb_hi, hands_hi, cap_hi, glass_hi, ambient=True).save(os.path.join(docs, 'preview_ambient.png'))
    dark = preview(dark_hi, hands_hi, cap_hi, glass_hi, ambient=True, dark=True)
    dark.save(os.path.join(docs, 'preview_dark.png'))
    print('assets written to', os.path.abspath(OUT))


if __name__ == '__main__':
    main()
