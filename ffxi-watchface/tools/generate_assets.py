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
FONT_SANS_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_FF = os.path.join(FONTS, 'FinalFantasy.ttf')        # caps only; no digits/space/'
EMBLEMS = os.path.join(os.path.dirname(__file__), 'emblems')  # square crops of the nation crests
WORLD_LAND = os.path.join(EMBLEMS, 'worldmap_land.png')      # Vana'diel land mask

# Layout (in 450px units) -- keep in sync with watchface.xml
SUB_OFFSET = 112   # sub-dial centre distance from main centre
SUB_R = 64         # sub-dial radius
EMBLEM_R = 38      # crest medallion radius inside each sub-dial
DATE_POS = (225 + 103, 225 + 103)  # date window centre (4:30)
DATE_SIZE = (34, 24)
# Sub-dials, as on the real watch: San d'Oria at 9, Bastok at 6, Windurst at 3.
POSITIONS = {'left': (225 - SUB_OFFSET, 225), 'right': (225 + SUB_OFFSET, 225), 'bottom': (225, 225 + SUB_OFFSET)}
POSITION_SCALE = {'left': 'days', 'right': 'battery', 'bottom': '24h', 'top': '24h'}
LAYOUT = {'left': 'sandoria', 'bottom': 'bastok', 'right': 'windurst'}
# Fourth dial at 12: Vana'diel time on a 24-hour scale under the Jeuno crest.
VANA_POS = (225, 225 - SUB_OFFSET)

NAVY_IN, NAVY_OUT = (30, 48, 84), (6, 11, 24)
# Nation colours: San d'Oria red, Bastok blue, Windurst green
NATIONS = {
    'sandoria': ((150, 28, 38), (70, 10, 16)),
    'bastok': ((36, 84, 168), (12, 32, 78)),
    'windurst': ((34, 120, 66), (10, 50, 26)),
    'jeuno': ((150, 112, 44), (70, 48, 14)),
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


def xi_mask(size, center, height=32, gap=0.14):
    """'XI' as an L mask with both letters cropped to their ink and scaled to exactly
    the same height, so tops and bottoms line up (the font's X and I differ)."""
    f = ImageFont.truetype(FONT_FF, 400)
    glyphs = []
    for ch in 'XI':
        g = Image.new('L', (600, 600), 0)
        ImageDraw.Draw(g).text((50, 500), ch, font=f, fill=255, anchor='ls')
        g = g.crop(g.getbbox())
        glyphs.append(g.resize((round(g.width * s(height) / g.height), round(s(height))), Image.LANCZOS))
    total = sum(g.width for g in glyphs) + s(height) * gap
    m = Image.new('L', size, 0)
    x, top = center[0] - total / 2, center[1] - s(height) / 2
    for g in glyphs:
        m.paste(g, (round(x), round(top)))
        x += g.width + s(height) * gap
    return m


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
XI_BLUE = (85, 135, 250)   # Dark style accent: XI and sub-dial needles
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
    """Raised metal lettering from a mask (or draw_fn(draw, fill) painting one): gradient + shadow."""
    if isinstance(draw_fn, Image.Image):
        m = draw_fn
    else:
        m = Image.new('L', img.size, 0)
        draw_fn(ImageDraw.Draw(m), 255)
    box = m.getbbox()
    if not box:
        return
    if shadow:
        drop_shadow(img, m, blur=0.7, alpha=0.7, dxy=(0.6, 1.0))
    fill_mask(img, m, vgrad(img.size, stops, box[1], box[3]))


# --------------------------------------------------------------------- crystals
CRYSTAL_R = (176, 210)   # 12 o'clock crystal spans these radii


def load_crystal(height):
    cr = Image.open(os.path.join(EMBLEMS, 'crystal.png')).convert('RGBA')
    return cr.resize((round(height * cr.width / cr.height), round(height)), Image.LANCZOS)


# Gem line drawing for the outline styles: outer outline, inner table, and facet
# lines joining them. Points are (x in widths, y in half-heights), mirrored left/right.
GEM_OUTER = [(0, -1), (0.34, -0.66), (0.5, -0.12), (0.47, 0.42), (0.3, 0.84), (0, 1)]
GEM_TABLE = [(0, -0.6), (0.17, -0.38), (0.25, -0.06), (0.23, 0.3), (0.14, 0.58), (0, 0.7)]


def crystal_lines(img, bright=1.0, color=(236, 242, 255)):
    """The 12 o'clock crystal as white minimal line art (more detailed than plain markers)."""
    h = s(CRYSTAL_R[1] - CRYSTAL_R[0])
    w = h * 0.43
    cx, cy = C, C - s((CRYSTAL_R[0] + CRYSTAL_R[1]) / 2)

    def ring(pts):
        right = [(cx + x * w, cy + y * h / 2) for x, y in pts]
        left = [(cx - x * w, cy + y * h / 2) for x, y in pts[-2:0:-1]]
        return right + left
    outer, table = ring(GEM_OUTER), ring(GEM_TABLE)
    col = tuple(int(c * bright) for c in color)
    thin = tuple(int(c * bright * 0.75) for c in color)
    d = ImageDraw.Draw(img)
    d.polygon(outer, fill=(0, 0, 0, 255))
    n = len(outer)
    for i in range(n):   # facets: each table corner to its outer corner and the next one
        d.line([table[i], outer[i]], fill=thin, width=round(s(0.8)))
        d.line([table[i], outer[(i + 1) % n]], fill=thin, width=round(s(0.6)))
    d.line([table[0], table[n // 2]], fill=thin, width=round(s(0.6)))
    d.line(table + table[:1], fill=col, width=round(s(1.0)), joint='curve')
    d.line(outer + outer[:1], fill=col, width=round(s(1.4)), joint='curve')


def crystal12(style, k):
    """The 12 o'clock crystal for one weekday, on its own transparent canvas (an overlay)."""
    tones = ELEMENT_TONES[k]
    size = (s(N), s(N))
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    if style == 'dark':
        crystal_lines(img, 1.0, ELEMENT_LINE[k])
        return img
    big = style == 'classic'
    h, top = (s(CRYSTAL_R[1] - CRYSTAL_R[0]), CRYSTAL_R[1]) if big else (s(26), 208)
    cr = colorize(load_crystal(h), tones)
    if big:   # glow in the element's colour
        glow = Image.new('RGBA', size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([C - s(16), C - s(213), C + s(16), C - s(173)], fill=ELEMENT_LINE[k] + (170,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s(9))))
    layer = Image.new('RGBA', size, (0, 0, 0, 0))
    layer.paste(cr, (round(C - cr.width / 2), round(C - s(top))))
    drop_shadow(img, layer.getchannel('A'), blur=1.8 if big else 1.2, alpha=0.7 if big else 0.5)
    img.alpha_composite(layer)
    return img


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
    """Sub-dial centre per nation, from LAYOUT (same in every style, as on the real watch)."""
    centres = {key: POSITIONS[pos] for pos, key in LAYOUT.items()}
    centres['jeuno'] = VANA_POS
    return centres


def position_of(key):
    return 'top' if key == 'jeuno' else next(pos for pos, k in LAYOUT.items() if k == key)


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
    elif key == 'windurst':  # green star tree; yellow stars
        star = (r > 170) & (g > 170) & (b < 110)
        fig = keep((g > r + 25) & ~star, 300)
        acc = keep(star, 30)
    else:                   # jeuno: the sunburst bright, the triangle's coloured bands as linework
        yy = np.mgrid[0:a.shape[0], 0:a.shape[1]][0]
        sun = (r > 190) & (g < 215) & (b < 120) & (r > b + 80)
        bands = (((a.max(2) - a.min(2)) > 50) | (a.max(2) < 120)) & ~sun & (yy < a.shape[0] * 0.86)
        fig = np.zeros(a.shape[:2], bool)
        acc = keep(sun, 40)
        detail = keep(bands, 60)
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
    else:   # solid black face so the world map doesn't show through
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(0, 0, 0, 255), outline=(110, 110, 110), width=round(s(1.2)))
    draw_emblem(img, key, cx, cy, ambient, bright)
    d = ImageDraw.Draw(img)

    draw_scale(d, POSITION_SCALE[position_of(key)], cx, cy, R, fg)


def draw_scale(d, kind, cx, cy, R, fg, fs=1.0):
    """Ticks and labels of a sub-dial: 'days', 'battery', '24h', '30min' or 'seconds'."""
    small = font(FONT_LABEL, 9 * fs)
    num = font(FONT_NUM, 9.5 * fs)
    tick_r0, tick_r1, lab_r = R - s(3), R - s(6.5), R - s(13.5)
    if kind == 'days':
        days = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA']
        for i, lab in enumerate(days):
            a = i * 360 / 7
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1, a, cx, cy)], fill=fg, width=round(s(1.4)))
            text_c(d, polar(lab_r, a, cx, cy), lab, small, fg)
    elif kind == 'battery':
        for i in range(11):
            a = -150 + i * 30
            long_ = i % 5 == 0
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1 - (s(1) if long_ else 0), a, cx, cy)],
                   fill=fg, width=round(s(1.6 if long_ else 1)))
        for val, a in (('E', -150), ('½', 0), ('F', 150)):
            text_c(d, polar(lab_r, a, cx, cy), val, num, fg)
    elif kind == '30min':
        for i in range(30):
            a = i * 12
            long_ = i % 5 == 0
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1 - (s(1.5) if long_ else s(-1)), a, cx, cy)],
                   fill=fg, width=round(s(1.4 if long_ else 0.6)))
        for val, a in (('30', 0), ('10', 120), ('20', 240)):
            text_c(d, polar(lab_r - s(1), a, cx, cy), val, num, fg)
        text_c(d, (cx, cy + R * 0.42), 'MIN', font(FONT_LABEL, 6.5 * fs), fg)
    elif kind == 'seconds':
        for i in range(60):
            a = i * 6
            long_ = i % 5 == 0
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1 - (s(1.5) if long_ else s(-1)), a, cx, cy)],
                   fill=fg, width=round(s(1.2 if long_ else 0.5)))
        for val, a in (('60', 0), ('20', 120), ('40', 240)):
            text_c(d, polar(lab_r - s(1), a, cx, cy), val, num, fg)
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


def make_dial(ambient=False, bright=0.6, crystal=True):
    """ambient=False: classic dial. ambient=True: outline dial; bright=1 is the
    Dark style (active), bright=0.6 the always-on version of both styles."""
    size = (s(N), s(N))
    if ambient:
        img = Image.new('RGBA', size, (0, 0, 0, 255))
        if bright >= 1:   # Dark style only; always-on stays plain black
            draw_world(img, (40, 46, 60, 50), (120, 128, 146, 255), width=0.9)
    else:
        img = sunburst(size)
        draw_world(img, (200, 215, 255, 14), (200, 215, 255, 46))
        # chapter ring: dark gunmetal, stepped down from the dial with a bright chamfer
        metal_ring(img, C, C, s(226), s(213), (10, 13, 19), (58, 64, 78))
        inner_shadow(img, ring_mask(size, C, C, s(226), s(213)), depth=1.2, blur=1.0, alpha=0.5)
        metal_ring(img, C, C, s(213.5), s(211.5), (60, 66, 80), (210, 216, 228), recessed=True)
    d = ImageDraw.Draw(img)

    for i in range(60):
        a = i * 6
        five = i % 5 == 0
        if ambient and not five:
            continue
        col = (120, 120, 120) if ambient else ((240, 240, 240) if five else (170, 176, 186))
        d.line([polar(s(224), a), polar(s(216 if five else 220), a)], fill=col, width=round(s(2.2 if five else 1)))

    # 12 = crystal, 11 = "XI"
    if crystal:   # active dials leave it out: weekday-coloured overlays (crystal12_*) carry it
        place_crystal(img, ambient, bright)
    d = ImageDraw.Draw(img)

    pos = polar(s(188), 330)
    xi = xi_mask(size, pos)
    if ambient:   # solid crystal-blue numeral
        k = 0.6 + 0.4 * bright
        fill_mask(img, xi, tuple(int(c * k) for c in XI_BLUE) + (255,))
        d = ImageDraw.Draw(img)
    else:
        # applied (raised) gold numeral and wordmark; small print stays flat like pad printing
        applied_text(img, xi)
        d = ImageDraw.Draw(img)

    for key in NATIONS:
        draw_subdial(img, key, ambient, bright)

    # date window frame (number drawn live by the watch face)
    if ambient and bright >= 1:
        x, y = s(DATE_POS[0]), s(DATE_POS[1])
        w, h = s(DATE_SIZE[0]), s(DATE_SIZE[1])
        ImageDraw.Draw(img).rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=s(3),
                                              fill=(0, 0, 0, 255), outline=(150, 150, 150), width=round(s(1.2)))
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


# --------------------------------------------------------------------- light style
# After the real Seiko piece: silver-white dial with a faint Vana'diel world map,
# blue inner ring, applied lume batons, white sub-dials with printed crests and
# nation-coloured rings and hands.
NATION_INK = {'sandoria': (196, 32, 44), 'windurst': (40, 150, 70), 'bastok': (40, 70, 190), 'jeuno': (150, 110, 40)}
LIGHT_BLUE_RING = ((24, 40, 104), (66, 96, 178))


def light_sunburst(size):
    base = np.asarray(radial_gradient(size, (248, 249, 251), (214, 218, 226), r=s(225)).convert('RGB'), float)
    th = angle_map(size, C, C)
    sheen = 1 + 0.035 * np.cos(2 * (th - math.radians(LIGHT_DEG)))
    out = np.clip(base * sheen[..., None], 0, 255)
    return Image.fromarray(out.astype(np.uint8), 'RGB').convert('RGBA')


def draw_world(img, fill, line, width=1.0, diameter=330):
    """Rough outline of Vana'diel behind the dial furniture: land mask from
    tools/emblems/worldmap_land.png (cut from worldmap_source.png), filled and outlined."""
    from scipy import ndimage
    m = Image.open(WORLD_LAND).convert('L')
    k = s(diameter) / max(m.size)
    m = m.resize((round(m.width * k), round(m.height * k)), Image.LANCZOS)
    land = Image.new('L', img.size, 0)
    land.paste(m, (round(C - m.width / 2), round(C - m.height / 2 + s(6))))
    a = np.asarray(land) > 127
    edge = a & ~ndimage.binary_erosion(a, iterations=max(1, round(s(width))))
    if fill[3]:
        fill_mask(img, Image.fromarray((a * fill[3]).astype(np.uint8)).filter(ImageFilter.GaussianBlur(SS / 2)), fill[:3] + (255,))
    fill_mask(img, Image.fromarray((edge * line[3]).astype(np.uint8)).filter(ImageFilter.GaussianBlur(SS / 3)), line[:3] + (255,))


def lume_baton(img, deg, r0=182, r1=207, w=7.5):
    """Applied silver baton with a lume insert, long axis radial."""
    L = s(r1 - r0)
    pad = s(4)
    tile = Image.new('RGBA', (round(s(w)) + 2 * pad, L + 2 * pad), (0, 0, 0, 0))
    m = Image.new('L', tile.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([pad, pad, pad + s(w), pad + L], radius=s(w) / 2, fill=255)
    fill_mask(tile, m, lgrad(tile.size, (pad, 0), (pad + s(w), 0), [(0, (250, 252, 255)), (0.5, (196, 202, 212)), (1, (130, 138, 152))]))
    lm = Image.new('L', tile.size, 0)
    inset = s(w) * 0.27
    ImageDraw.Draw(lm).rounded_rectangle([pad + inset, pad + inset, pad + s(w) - inset, pad + L - inset], radius=(s(w) - 2 * inset) / 2, fill=255)
    fill_mask(tile, lm, vgrad(tile.size, [(0, (236, 246, 240)), (1, (214, 230, 222))]))
    tile = tile.rotate(-deg, resample=Image.BICUBIC, expand=True)
    cx, cy = polar(s((r0 + r1) / 2), deg)
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    layer.paste(tile, (round(cx - tile.width / 2), round(cy - tile.height / 2)))
    drop_shadow(img, layer.getchannel('A'), blur=1.0, alpha=0.45)
    img.alpha_composite(layer)


def light_crest(key, size):
    """Crest as see-through grey ink for a white sub-dial (the outline-style art, inverted)."""
    v = np.asarray(crest_art(key, size).convert('L')).astype(float)
    img = Image.new('RGBA', size, (40, 44, 52, 0))
    img.putalpha(Image.fromarray(np.clip(v * 0.95, 0, 255).astype(np.uint8)))
    return img


def light_subdial(img, key, centre, scale, sub_r=None, emblem_r=None, fs=1.0):
    cx, cy = (s(v) for v in centre)
    R = s(sub_r or SUB_R)
    g = radial_gradient((2 * R, 2 * R), (252, 252, 253), (232, 234, 238))
    rings = Image.new('RGBA', g.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rings)
    for rr in range(s(2), R, round(s(2.2))):     # fine azurage
        rd.ellipse([R - rr, R - rr, R + rr, R + rr], outline=(0, 0, 0, 10), width=SS)
    g.alpha_composite(rings)
    img.paste(g, (int(cx - R), int(cy - R)), circle_mask((2 * R, 2 * R), R, R, R))
    inner_shadow(img, circle_mask(img.size, cx, cy, R), depth=1.6, blur=1.4, alpha=0.35)
    r = s(emblem_r or EMBLEM_R)
    em = light_crest(key, (2 * r, 2 * r))
    em.putalpha(Image.fromarray(np.minimum(np.asarray(em.getchannel('A')), np.asarray(circle_mask(em.size, r, r, r)))))
    img.alpha_composite(em, (int(cx - r), int(cy - r)))
    d = ImageDraw.Draw(img)
    for i in range(60):   # fine outer track
        a = i * 6
        d.line([polar(R - s(1.5), a, cx, cy), polar(R - s(3.2), a, cx, cy)], fill=(120, 124, 132), width=round(s(0.5)))
    draw_scale(d, scale, cx, cy, R, (54, 58, 66), fs)
    # thin printed ring in the nation's colour
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=NATION_INK[key], width=round(s(1.8)))


def make_light_dial():
    size = (s(N), s(N))
    img = light_sunburst(size)
    draw_world(img, (120, 128, 142, 26), (110, 118, 132, 90))
    # blue inner ring (rehaut) with fine white ticks
    metal_ring(img, C, C, s(226), s(212), *LIGHT_BLUE_RING)
    d = ImageDraw.Draw(img)
    for i in range(240):
        a = i * 1.5
        major, five = i % 4 == 0, i % 20 == 0
        r1 = 216 if five else (219 if major else 221.5)
        d.line([polar(s(224), a), polar(s(r1), a)], fill=(236, 240, 250), width=round(s(1.4 if five else (0.8 if major else 0.5))))
    d.ellipse([C - s(212), C - s(212), C + s(212), C + s(212)], outline=(20, 24, 34), width=round(s(1)))
    inner_shadow(img, circle_mask(size, C, C, s(212)), depth=1.6, blur=1.6, alpha=0.35)
    # applied lume batons, small blue crystal at 12, gold XI at 11
    for h in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        lume_baton(img, h * 30)
    applied_text(img, xi_mask(size, polar(s(188), 330)))
    for pos in POSITIONS:
        light_subdial(img, LAYOUT[pos], POSITIONS[pos], POSITION_SCALE[pos])
    light_subdial(img, 'jeuno', VANA_POS, '24h')
    # date window (number drawn live by the watch face)
    x, y = s(DATE_POS[0]), s(DATE_POS[1])
    w, h = s(DATE_SIZE[0]), s(DATE_SIZE[1])
    frame = Image.new('L', size, 0)
    ImageDraw.Draw(frame).rounded_rectangle([x - w / 2 - s(2.2), y - h / 2 - s(2.2), x + w / 2 + s(2.2),
                                             y + h / 2 + s(2.2)], radius=s(4), fill=255)
    win = Image.new('L', size, 0)
    ImageDraw.Draw(win).rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=s(3), fill=255)
    fill_mask(img, frame, lgrad(size, (x - w / 2, y - h / 2), (x + w / 2, y + h / 2),
                                [(0, (120, 126, 140)), (0.5, (190, 196, 208)), (1, (246, 248, 252))]))
    fill_mask(img, win, (255, 255, 255, 255))
    inner_shadow(img, win, depth=1.6, blur=1.2, alpha=0.4)
    img.putalpha(circle_mask(size, C, C, s(225)))
    return img


def star_cap(r=8, pad=None):
    """Bronze four-point star hub, after the real watch's chronograph hand."""
    pad = HAND_PAD if pad is None else pad
    size = s(2 * (r + pad))
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c = size / 2
    pts = []
    for i in range(8):
        a = math.radians(i * 45)
        rr = s(r) if i % 2 == 0 else s(r * 0.38)
        pts.append((c + rr * math.sin(a), c - rr * math.cos(a)))
    m = Image.new('L', img.size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    fill_mask(img, m, lgrad(img.size, (c - s(r), c - s(r)), (c + s(r), c + s(r)),
                            [(0, (238, 198, 120)), (0.5, (184, 132, 58)), (1, (120, 80, 30))]))
    d = ImageDraw.Draw(img)
    d.polygon(pts, outline=(96, 64, 24), width=round(s(0.5)))
    d.ellipse([c - s(2.2), c - s(2.2), c + s(2.2), c + s(2.2)], fill=(214, 172, 96), outline=(96, 64, 24), width=round(s(0.5)))
    return with_shadow(img, blur=0.9, alpha=0.5)


# --------------------------------------------------------------------- vana'diel time style
# A parchment map of Vana'diel with Earth time on ink hands, plus live Vana'diel time
# (25x Earth time) and today's elemental weekday, computed on the watch from UTC.
PARCHMENT = ((246, 233, 200), (206, 172, 116))
INK = (92, 58, 26)
ELEMENTS = [  # weekday order: (name, crystal colour)
    ('Firesday', (226, 64, 40)), ('Earthsday', (196, 150, 52)), ('Watersday', (52, 110, 214)),
    ('Windsday', (64, 166, 76)), ('Iceday', (120, 196, 232)), ('Lightningday', (150, 84, 206)),
    ('Lightsday', (250, 248, 236)), ('Darksday', (44, 40, 52)),
]
# Per-element tones (shadow, mid, highlight) for recolouring the crystal and hands by weekday,
# plus the colour used for lines on black (Darksday's mid is too dark there).
ELEMENT_TONES = [
    ((96, 12, 0), (232, 64, 30), (255, 214, 150)),     # Fire
    ((74, 48, 10), (204, 154, 52), (255, 236, 160)),   # Earth
    ((6, 26, 92), (52, 112, 232), (196, 228, 255)),    # Water
    ((6, 62, 22), (62, 172, 82), (206, 255, 206)),     # Wind
    ((20, 72, 104), (122, 202, 238), (242, 252, 255)), # Ice
    ((52, 10, 84), (152, 82, 214), (236, 204, 255)),   # Lightning
    ((132, 120, 88), (242, 238, 216), (255, 255, 250)),# Light
    ((10, 8, 22), (64, 52, 86), (176, 164, 206)),      # Dark
]
ELEMENT_LINE = [tones[1] for tones in ELEMENT_TONES[:7]] + [ELEMENT_TONES[7][2]]


def colorize(img, tones):
    """Recolour an RGBA image by luminance through a shadow-mid-highlight ramp (keeps facets)."""
    a = np.asarray(img.convert('RGBA')).astype(float)
    lum = a[..., :3] @ [0.3, 0.5, 0.2] / 255
    lum = np.clip((lum - lum[a[..., 3] > 0].min()) / max(1e-6, np.ptp(lum[a[..., 3] > 0])), 0, 1) if (a[..., 3] > 0).any() else lum
    stops = [0, 0.55, 1]
    rgb = np.stack([np.interp(lum, stops, [t[i] for t in tones]) for i in range(3)], -1)
    return Image.fromarray(np.dstack([rgb, a[..., 3]]).astype(np.uint8), 'RGBA')


VANA_BOX = (77, 309, 161, 353)     # 7:30 cartouche: Vana'diel time and weekday


def parchment(size):
    img = np.asarray(radial_gradient(size, *PARCHMENT, r=s(240)).convert('RGB'), float)
    rng = np.random.default_rng(7)
    grain = ndimage_blur(rng.normal(0, 1, (size[1] // 4, size[0] // 4)), 1.2)
    grain = np.asarray(Image.fromarray(((grain - grain.min()) / np.ptp(grain) * 255).astype(np.uint8)).resize(size, Image.BICUBIC), float) / 255
    img = img * (0.94 + 0.08 * grain[..., None])
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'RGB').convert('RGBA')


def ndimage_blur(a, sigma):
    from scipy import ndimage
    return ndimage.gaussian_filter(a, sigma)


def compass_rose(img, cx, cy, r, color):
    d = ImageDraw.Draw(img)
    for i in range(8):
        a = i * 45
        rr = r if i % 2 == 0 else r * 0.55
        tip = polar(rr, a, cx, cy)
        side_l, side_r = polar(r * 0.16, a - 45, cx, cy), polar(r * 0.16, a + 45, cx, cy)
        d.polygon([tip, side_l, (cx, cy)], fill=color + (255,))
        d.polygon([tip, side_r, (cx, cy)], fill=tuple(int(c * 0.6 + 255 * 0.4) for c in color) + (255,))
    d.ellipse([cx - r * 0.12, cy - r * 0.12, cx + r * 0.12, cy + r * 0.12], fill=(170, 40, 30, 255))
    text_c(d, polar(r + s(6), 0, cx, cy), 'N', font(FONT_SERIF, 7), color)


def cartouche(img, box, fill, line):
    x0, y0, x1, y1 = (s(v) for v in box)
    m = Image.new('L', img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([x0, y0, x1, y1], radius=s(8), fill=255)
    drop_shadow(img, m, blur=1.4, alpha=0.35)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], radius=s(8), fill=fill + (255,), outline=line + (255,), width=round(s(1.4)))
    d.rounded_rectangle([x0 + s(3), y0 + s(3), x1 - s(3), y1 - s(3)], radius=s(6), outline=line + (255,), width=round(s(0.6)))


def parchment_subdial(img, key, centre, scale, ambient=False):
    """Sub-dial for the parchment face: inked rings, crest in sepia, ink labels."""
    cx, cy = (s(v) for v in centre)
    R = s(SUB_R)
    d = ImageDraw.Draw(img)
    ink = (130, 118, 96) if ambient else INK
    if ambient:
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(0, 0, 0, 255), outline=ink, width=round(s(1.0)))
        r = s(EMBLEM_R)
        em = crest_art(key, (2 * r, 2 * r), 0.55)
        img.paste(em, (int(cx - r), int(cy - r)), circle_mask((2 * r, 2 * r), r, r, r))
    else:
        g = radial_gradient((2 * R, 2 * R), (252, 244, 222), (232, 214, 172))
        img.paste(g, (int(cx - R), int(cy - R)), circle_mask((2 * R, 2 * R), R, R, R))
        inner_shadow(img, circle_mask(img.size, cx, cy, R), depth=1.4, blur=1.4, alpha=0.3)
        r = s(EMBLEM_R)
        v = np.asarray(crest_art(key, (2 * r, 2 * r)).convert('L')).astype(float)
        em = Image.new('RGBA', (2 * r, 2 * r), INK + (0,))
        em.putalpha(Image.fromarray(np.minimum(np.clip(v * 0.9, 0, 255), np.asarray(circle_mask(em.size, r, r, r))).astype(np.uint8)))
        img.alpha_composite(em, (int(cx - r), int(cy - r)))
        d = ImageDraw.Draw(img)
        for rr, w in ((R, 1.5), (R - s(3), 0.5)):
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=INK + (255,), width=round(s(w)))
    for i in range(60):
        a = i * 6
        d.line([polar(R - s(4), a, cx, cy), polar(R - s(5.6), a, cx, cy)], fill=ink + (255,), width=round(s(0.5)))
    draw_scale(d, scale, cx, cy, R - s(1), ink)


def make_vana_dial(ambient=False):
    size = (s(N), s(N))
    if ambient:
        img = Image.new('RGBA', size, (0, 0, 0, 255))
        draw_world(img, (0, 0, 0, 0), (96, 84, 62, 255), width=0.8, diameter=380)
        ink = (130, 118, 96)
    else:
        img = parchment(size)
        d = ImageDraw.Draw(img)
        for rr in range(60, 220, 40):   # faint map graticule
            d.ellipse([C - s(rr), C - s(rr), C + s(rr), C + s(rr)], outline=INK + (34,), width=round(s(0.6)))
        for a in range(0, 180, 30):
            d.line([polar(s(210), a), polar(s(210), a + 180)], fill=INK + (28,), width=round(s(0.6)))
        draw_world(img, (214, 172, 104, 150), INK + (210,), width=0.9, diameter=380)
        compass_rose(img, s(334), s(118), s(17), INK)
        ink = INK
    d = ImageDraw.Draw(img)
    # inked chapter ring with Earth hours
    for rr, w in ((219, 1.6), (212, 0.7)):
        d.ellipse([C - s(rr), C - s(rr), C + s(rr), C + s(rr)], outline=ink + (255,), width=round(s(w)))
    for i in range(60):
        a = i * 6
        d.line([polar(s(219), a), polar(s(215 if i % 5 else 212), a)], fill=ink + (255,), width=round(s(1.2 if i % 5 == 0 else 0.6)))
    numerals = ['XII', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI']
    for h, num in enumerate(numerals):
        text_c(d, polar(s(196), h * 30), num, font(FONT_SERIF, 15 if h % 3 == 0 else 11), ink)
    for pos in POSITIONS:
        parchment_subdial(img, LAYOUT[pos], POSITIONS[pos], POSITION_SCALE[pos], ambient)
    parchment_subdial(img, 'jeuno', VANA_POS, '24h', ambient)
    if not ambient:   # date window and the Vana'diel cartouche (text drawn live)
        x, y = s(DATE_POS[0]), s(DATE_POS[1])
        w, h = s(DATE_SIZE[0]), s(DATE_SIZE[1])
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=s(4), fill=(250, 241, 216, 255),
                            outline=INK + (255,), width=round(s(1.2)))
        cartouche(img, VANA_BOX, (250, 241, 216), INK)
        d = ImageDraw.Draw(img)
        text_c(d, (s((VANA_BOX[0] + VANA_BOX[2]) / 2), s(VANA_BOX[1] + 9)), "VANA'DIEL", font(FONT_LABEL, 6.5), INK)
    img.putalpha(circle_mask(size, C, C, s(225)))
    return img


def element_crystal(color, h=22):
    """Small elemental crystal icon: gem outline filled with the element's colour."""
    w = h * 0.5
    img = Image.new('RGBA', (round(s(w + 4)), round(s(h + 4))), (0, 0, 0, 0))
    cx, cy = img.width / 2, img.height / 2

    def ring(pts, k=1.0):
        right = [(cx + x * s(w) * k, cy + y * s(h) / 2 * k) for x, y in pts]
        left = [(cx - x * s(w) * k, cy + y * s(h) / 2 * k) for x, y in pts[-2:0:-1]]
        return right + left
    outer, table = ring(GEM_OUTER), ring(GEM_TABLE)
    d = ImageDraw.Draw(img)
    hi = tuple(min(255, int(c * 0.55 + 255 * 0.45)) for c in color)
    d.polygon(outer, fill=color + (255,))
    d.polygon(table, fill=hi + (255,))
    for i in range(len(outer)):
        d.line([table[i], outer[i]], fill=(255, 255, 255, 110), width=round(s(0.5)))
    d.line(outer + outer[:1], fill=(60, 38, 18, 255), width=round(s(0.9)), joint='curve')
    return img


def ink_hand(tip, tail, w, color=INK, pad=3, inlay=None):
    """Slim solid ink hand for the parchment face; `inlay` adds a coloured centre stripe."""
    img, px, py = hand_canvas(w, tip, tail, pad)
    half = s(w) / 2
    pts = [(px, py - s(tip)), (px + half, py - s(tip) * 0.22), (px + half * 0.4, py + s(tail)),
           (px - half * 0.4, py + s(tail)), (px - half, py - s(tip) * 0.22)]
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=color + (255,))
    if inlay:
        lw = half * 0.42
        d.polygon([(px, py - s(tip) * 0.86), (px + lw, py - s(tip) * 0.24), (px, py - s(tip) * 0.08),
                   (px - lw, py - s(tip) * 0.24)], fill=inlay + (255,))
    return with_shadow(img, blur=1.0, alpha=0.35)


def ink_cap(r=5, pad=3):
    size = s(2 * (r + pad))
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c = size / 2
    d = ImageDraw.Draw(img)
    d.ellipse([c - s(r), c - s(r), c + s(r), c + s(r)], fill=INK + (255,))
    d.ellipse([c - s(1.8), c - s(1.8), c + s(1.8), c + s(1.8)], fill=(214, 172, 96, 255))
    return with_shadow(img, blur=0.8, alpha=0.4)


# --------------------------------------------------------------------- we are vana'diel
# A replica of the Seiko x FFXI "WE ARE VANA'DIEL" chronograph: steel tachymeter bezel,
# blue inner ring, silver-white dial with the world map, crystal-shaped lume markers,
# SEIKO, gold XI, three white sub-dials (San d'Oria 30-min counter at 9, Windurst 24h at 3,
# Bastok running seconds at 6), lume hands and a gold chronograph hand resting at 12.
SEIKO_SUB_R = 50
SEIKO_EMBLEM_R = 30
SEIKO_POS = {'left': (225 - 92, 225), 'right': (225 + 92, 225), 'bottom': (225, 225 + 92)}
SEIKO_LAYOUT = {'left': ('sandoria', '30min'), 'right': ('windurst', '24h'), 'bottom': ('bastok', 'seconds')}
SEIKO_DATE = (319, 319)
SEIKO_DIAL_R = 181        # dial surface; the blue ring and bezel sit outside it
TACHY = [400, 300, 250, 200, 180, 160, 140, 120, 100, 90, 80, 75, 70, 65, 60]
FONT_BEZEL = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_SEIKO = '/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf'


def glyph(text, f, color, deg):
    """Text rendered on its own tile and rotated `deg` clockwise (for bezel engraving)."""
    w, h = f.getbbox(text)[2] + SS * 2, f.getbbox(text)[3] + SS * 2
    tile = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((w / 2, h / 2), text, font=f, fill=color, anchor='mm')
    return tile.rotate(-deg, resample=Image.BICUBIC, expand=True)


def put(img, tile, xy):
    img.alpha_composite(tile, (round(xy[0] - tile.width / 2), round(xy[1] - tile.height / 2)))


def tachy_bezel(img, ambient=False):
    size = img.size
    ink = (120, 120, 120) if ambient else (34, 36, 42)
    if not ambient:   # brushed, polished steel
        metal_ring(img, C, C, s(226), s(197), (128, 134, 146), (246, 248, 252))
        rings = Image.new('RGBA', size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(rings)
        for rr in range(197, 226):
            rd.ellipse([C - s(rr), C - s(rr), C + s(rr), C + s(rr)], outline=(0, 0, 0, 10 if rr % 2 else 0), width=SS)
        img.alpha_composite(rings)
        d = ImageDraw.Draw(img)
        d.ellipse([C - s(225), C - s(225), C + s(225), C + s(225)], outline=(96, 100, 110), width=round(s(1)))
    d = ImageDraw.Draw(img)
    f = font(FONT_BEZEL, 11)
    for v in TACHY:
        a = 6 * 3600 / v % 360
        put(img, glyph(str(v), f, ink, a if a <= 90 or a >= 270 else a + 180), polar(s(211), a))
    for v0, v1 in zip(TACHY, TACHY[1:]):   # engraved dots between the numbers
        a = 6 * 3600 / ((v0 + v1) / 2) % 360
        x, y = polar(s(211), a)
        d.ellipse([x - s(1.1), y - s(1.1), x + s(1.1), y + s(1.1)], fill=ink)
    fl = font(FONT_BEZEL, 9)
    letters = 'TACHYMETER'
    for i, ch in enumerate(letters):   # arced between 60 and 400
        a = 11 + i * (32 / (len(letters) - 1))
        put(img, glyph(ch, fl, ink, a), polar(s(211), a))
    d.ellipse([C - s(197), C - s(197), C + s(197), C + s(197)], outline=(14, 16, 22) if not ambient else (90, 90, 90),
              width=round(s(1.6)))


def crystal_index(img, deg, r0=150, r1=176, w=9.5, ambient=False):
    """Applied crystal-shaped lume marker: polished silver elongated hexagon, lume inside."""
    L, half = s(r1 - r0), s(w) / 2
    pad = s(4)
    tile = Image.new('RGBA', (round(2 * half) + 2 * pad, L + 2 * pad), (0, 0, 0, 0))
    cx = tile.width / 2

    def hexa(k):
        hw, inset = half * k, (1 - k) * half
        return [(cx, pad + inset), (cx + hw, pad + inset + hw * 1.1), (cx + hw, pad + L - inset - hw * 1.1),
                (cx, pad + L - inset), (cx - hw, pad + L - inset - hw * 1.1), (cx - hw, pad + inset + hw * 1.1)]
    d = ImageDraw.Draw(tile)
    if ambient:
        d.polygon(hexa(1), outline=(150, 150, 150, 255), width=round(s(1)))
    else:
        m = Image.new('L', tile.size, 0)
        ImageDraw.Draw(m).polygon(hexa(1), fill=255)
        fill_mask(tile, m, lgrad(tile.size, (cx - half, 0), (cx + half, 0), [(0, (252, 253, 255)), (0.5, (190, 196, 206)), (1, (120, 128, 142))]))
        lm = Image.new('L', tile.size, 0)
        ImageDraw.Draw(lm).polygon(hexa(0.5), fill=255)
        fill_mask(tile, lm, vgrad(tile.size, [(0, (240, 248, 244)), (1, (214, 232, 224))]))
    tile = tile.rotate(-deg, resample=Image.BICUBIC, expand=True)
    x, y = polar(s((r0 + r1) / 2), deg)
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    layer.paste(tile, (round(x - tile.width / 2), round(y - tile.height / 2)))
    if not ambient:
        drop_shadow(img, layer.getchannel('A'), blur=0.9, alpha=0.45)
    img.alpha_composite(layer)


def make_seiko_dial(ambient=False):
    size = (s(N), s(N))
    if ambient:
        img = Image.new('RGBA', size, (0, 0, 0, 255))
    else:
        img = light_sunburst(size)
        draw_world(img, (120, 128, 142, 30), (110, 118, 132, 96), diameter=310)
        # blue inner ring with fine white ticks
        metal_ring(img, C, C, s(197), s(SEIKO_DIAL_R), *LIGHT_BLUE_RING)
        d = ImageDraw.Draw(img)
        for i in range(240):
            a = i * 1.5
            five, major = i % 20 == 0, i % 4 == 0
            r1 = 186 if five else (189 if major else 191.5)
            d.line([polar(s(195), a), polar(s(r1), a)], fill=(236, 240, 250), width=round(s(1.3 if five else (0.8 if major else 0.5))))
        d.ellipse([C - s(SEIKO_DIAL_R), C - s(SEIKO_DIAL_R), C + s(SEIKO_DIAL_R), C + s(SEIKO_DIAL_R)], outline=(20, 24, 34), width=round(s(0.8)))
        inner_shadow(img, circle_mask(size, C, C, s(SEIKO_DIAL_R)), depth=1.4, blur=1.4, alpha=0.3)
    tachy_bezel(img, ambient)
    for h in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        crystal_index(img, h * 30, ambient=ambient)
    # small blue crystal at 12, gold XI, SEIKO
    cr = load_crystal(s(24))
    if ambient:
        cr = colorize(cr, ((10, 20, 50), (40, 70, 140), (110, 150, 230)))
    layer = Image.new('RGBA', size, (0, 0, 0, 0))
    layer.paste(cr, (round(C - cr.width / 2), round(C - s(178))))
    if not ambient:
        drop_shadow(img, layer.getchannel('A'), blur=1.0, alpha=0.5)
    img.alpha_composite(layer)
    xi = xi_mask(size, polar(s(160), 330), height=24)
    if ambient:
        fill_mask(img, xi, (150, 126, 70, 255))
    else:
        applied_text(img, xi)

    def seiko_word(dd, f):
        x = C - s(27)
        for ch in 'SEIKO':   # letter-spaced, as on the dial
            dd.text((x, C - s(118)), ch, font=font(FONT_SEIKO, 19), fill=f, anchor='mm')
            x += s(13.5)
    if ambient:
        seiko_word(ImageDraw.Draw(img), (150, 150, 150))
    else:
        applied_text(img, seiko_word, stops=[(0, (236, 240, 246)), (0.45, (150, 156, 168)), (0.55, (96, 102, 114)), (1, (200, 204, 214))])
    for pos, (key, scale) in SEIKO_LAYOUT.items():
        if ambient:
            cx, cy = (s(v) for v in SEIKO_POS[pos])
            R = s(SEIKO_SUB_R)
            ImageDraw.Draw(img).ellipse([cx - R, cy - R, cx + R, cy + R], outline=(110, 110, 110), width=round(s(1)))
        else:
            light_subdial(img, key, SEIKO_POS[pos], scale, SEIKO_SUB_R, SEIKO_EMBLEM_R, fs=0.82)
    if not ambient:   # date window
        x, y = s(SEIKO_DATE[0]), s(SEIKO_DATE[1])
        w, h = s(28), s(20)
        win = Image.new('L', size, 0)
        ImageDraw.Draw(win).rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=s(2), fill=255)
        frame = win.filter(ImageFilter.MaxFilter(round(s(1.6)) * 2 + 1))
        fill_mask(img, frame, lgrad(size, (x - w / 2, y - h / 2), (x + w / 2, y + h / 2),
                                    [(0, (120, 126, 140)), (0.5, (196, 202, 212)), (1, (248, 250, 252))]))
        fill_mask(img, win, (255, 255, 255, 255))
        inner_shadow(img, win, depth=1.2, blur=1.0, alpha=0.4)
    img.putalpha(circle_mask(size, C, C, s(225)))
    return img


def lume_hand(tip, tail, w, pad=None):
    """Polished silver hand with a lume fill, after the real watch's hands."""
    pad = HAND_PAD if pad is None else pad
    img, px, py = hand_canvas(w, tip, tail, pad)
    half = s(w) / 2
    outer = [(px, py - s(tip)), (px + half, py - s(tip) * 0.16), (px + half * 0.55, py + s(tail)),
             (px - half * 0.55, py + s(tail)), (px - half, py - s(tip) * 0.16)]
    m = poly_mask(img.size, outer)
    fill_mask(img, m, lgrad(img.size, (px - half, 0), (px + half, 0), [(0, (252, 253, 255)), (0.5, (186, 192, 204)), (1, (118, 126, 140))]))
    lw = half * 0.55
    lume = [(px, py - s(tip) * 0.9), (px + lw, py - s(tip) * 0.2), (px + lw * 0.5, py - s(tip) * 0.06),
            (px - lw * 0.5, py - s(tip) * 0.06), (px - lw, py - s(tip) * 0.2)]
    fill_mask(img, poly_mask(img.size, lume), vgrad(img.size, [(0, (242, 250, 244)), (1, (216, 234, 224))]))
    ImageDraw.Draw(img).polygon(outer, outline=(70, 76, 90, 255), width=round(s(0.5)))
    return with_shadow(img, 1.6, 0.6)


def chrono_hand(tip=166, tail=36, pad=3):
    """Gold chronograph seconds hand with a round counterweight (rests at 12)."""
    img, px, py = hand_canvas(10, tip, tail, pad)
    d = ImageDraw.Draw(img)
    gold = (206, 160, 76, 255)
    d.polygon([(px, py - s(tip)), (px - s(0.9), py), (px + s(0.9), py)], fill=gold)
    d.rectangle([px - s(1.4), py, px + s(1.4), py + s(tail - 8)], fill=gold)
    d.ellipse([px - s(4.5), py + s(tail - 13), px + s(4.5), py + s(tail - 4)], fill=gold, outline=(120, 84, 30, 255), width=round(s(0.5)))
    return with_shadow(img, 1.0, 0.5)


# --------------------------------------------------------------------- hands
HAND_PAD = 5   # room around each hand for its soft shadow


def hand_canvas(w, tip, tail, pad=HAND_PAD):
    """Canvas for a hand whose pivot is at (w/2 + pad, tip + pad)."""
    img = Image.new('RGBA', (round(s(w + 2 * pad)), round(s(tip + tail + 2 * pad))), (0, 0, 0, 0))
    return img, s(w / 2 + pad), s(tip + pad)


def with_shadow(img, blur=1.8, alpha=0.55, color=(0, 0, 0)):
    """Soft halo under a rotating hand (no offset, so it reads right at any angle);
    a colour turns the shadow into a glow."""
    sh = img.getchannel('A').filter(ImageFilter.GaussianBlur(s(blur))).point(lambda v: int(v * alpha))
    out = Image.new('RGBA', img.size, color + (0,))
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


def photo_hand(name, tip, thin=1.0, pad=HAND_PAD, blur=1.8, alpha=0.55, outline=False, edge=(58, 62, 72), glow=None):
    """A photographed hand on a padded canvas, pivot centred, with a soft shadow.
    outline=True adds a thin edge (colour `edge`) and deepens the steel so it holds up on a
    white dial; `glow` swaps the shadow for a halo of that colour."""
    src, sx, sy = prepare_photo(name, tip, thin)
    w, tail = photo_geom(name, tip, thin)
    img, px, py = hand_canvas(w, tip, tail, pad)
    if outline:
        r, g, b, a = src.split()
        src = Image.merge('RGBA', [ch.point(lambda v: int(v * 0.86)) for ch in (r, g, b)] + [a])
        placed = Image.new('RGBA', img.size, (0, 0, 0, 0))
        placed.paste(src, (round(px - sx), round(py - sy)))
        k = round(s(0.6)) * 2 + 1
        ring = placed.getchannel('A').filter(ImageFilter.MaxFilter(k))
        img.alpha_composite(Image.merge('RGBA', [Image.new('L', img.size, v) for v in edge] + [ring]))
    img.alpha_composite(src, (round(px - sx), round(py - sy)))
    if glow:
        return with_shadow(with_shadow(img, blur, alpha), blur * 1.6, 0.75, glow)
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


def needle_hand(tip, tail, stroke=1.3, ring=3.2, pad=2, color=(225, 225, 225), ring_fill=(0, 0, 0, 255)):
    """Minimal Dark-style sub-dial hand: a hairline with a hollow pivot ring."""
    img, px, py = hand_canvas(8, tip, tail, pad)
    d = ImageDraw.Draw(img)
    d.line([(px, py - s(tip)), (px, py - s(ring))], fill=color, width=round(s(stroke)))
    d.line([(px, py + s(ring)), (px, py + s(tail))], fill=color, width=round(s(stroke)))
    d.ellipse([px - s(ring), py - s(ring), px + s(ring), py + s(ring)], fill=ring_fill,
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
    'cap_light': (lambda: star_cap(8), 8 + HAND_PAD),
    'cap_vana': (lambda: ink_cap(5), 5 + 3),
    'cap_seiko': (lambda: star_cap(7), 7 + HAND_PAD),
}


def _photo(name, tip, thin=1.0, pad=HAND_PAD, **kw):
    w, tail = photo_geom(name, tip, thin)
    return (lambda: photo_hand(name, tip, thin, pad, **kw), w, tip, tail, pad)


HANDS = {
    # name: (builder, visual width, tip length, tail length, shadow padding)
    'hand_sub': _photo('sub', 54, pad=3, blur=1.0, alpha=0.6),
    # Dark style: thin outline hands
    'hand_hour_dark': (lambda: outline_hand(112, 16, 10), 10, 112, 16, 2),
    'hand_minute_dark': (lambda: outline_hand(180, 20, 8), 8, 180, 20, 2),
    'hand_sub_dark': (lambda: needle_hand(52, 12, color=XI_BLUE), 8, 52, 12, 2),
    # Light style: steel hands with a firmer shadow on the white dial; nation-coloured needles
    'hand_sub_red': (lambda: with_shadow(needle_hand(52, 12, 1.5, 2.6, color=NATION_INK['sandoria'] + (255,),
                                                     ring_fill=NATION_INK['sandoria'] + (255,)), 0.8, 0.4), 8, 52, 12, 2),
    'hand_sub_green': (lambda: with_shadow(needle_hand(52, 12, 1.5, 2.6, color=NATION_INK['windurst'] + (255,),
                                                       ring_fill=NATION_INK['windurst'] + (255,)), 0.8, 0.4), 8, 52, 12, 2),
    'hand_sub_blue': (lambda: with_shadow(needle_hand(52, 12, 1.5, 2.6, color=NATION_INK['bastok'] + (255,),
                                                      ring_fill=NATION_INK['bastok'] + (255,)), 0.8, 0.4), 8, 52, 12, 2),
    # Vana'diel Time style: ink hands
    'hand_sub_ink': (lambda: needle_hand(52, 12, 1.4, 2.6, color=INK + (255,), ring_fill=INK + (255,)), 8, 52, 12, 2),
}
VANA_HAND = (12, 54, 12, 2)   # visual width, tip, tail, pad


def vana_hand(color):
    """Vana'diel 24h hand: a steel needle whose tip is today's elemental crystal."""
    w, tip, tail, pad = VANA_HAND
    img, px, py = hand_canvas(w, tip, tail, pad)
    d = ImageDraw.Draw(img)
    shaft = [(px - s(0.9), py - s(tip - 12)), (px - s(1.8), py), (px - s(1.3), py + s(tail)),
             (px + s(1.3), py + s(tail)), (px + s(1.8), py), (px + s(0.9), py - s(tip - 12))]
    d.polygon(shaft, fill=(236, 238, 242, 255), outline=(40, 44, 54, 255), width=round(s(0.6)))
    d.ellipse([px - s(3.2), py - s(3.2), px + s(3.2), py + s(3.2)], fill=(236, 238, 242, 255), outline=(40, 44, 54, 255), width=round(s(0.6)))
    d.ellipse([px - s(1.2), py - s(1.2), px + s(1.2), py + s(1.2)], fill=color + (255,))
    cr = element_crystal(color, h=15)
    at = (round(px - cr.width / 2), round(py - s(tip) - s(1.5)))
    halo = Image.new('L', img.size, 0)   # light rim so dark elements (Darksday) read on dark dials
    halo.paste(cr.getchannel('A').filter(ImageFilter.MaxFilter(round(s(0.7)) * 2 + 1)), at)
    fill_mask(img, halo.point(lambda v: v * 0.85), (240, 240, 244, 255))
    img.alpha_composite(cr, at)
    return with_shadow(img, blur=0.9, alpha=0.5)


for _k, (_name, _color) in enumerate(ELEMENTS):
    HANDS[f'hand_vana_{_k}'] = ((lambda c=_color: vana_hand(c)),) + VANA_HAND
    # main hands per weekday: steel with an element-coloured edge and glow (Classic, Light),
    # element-coloured outlines (Dark)
    _line, _tones = ELEMENT_LINE[_k], ELEMENT_TONES[_k]
    HANDS[f'hand_hour_classic_{_k}'] = _photo('hour', 118, thin=0.48, outline=True, edge=_line, glow=_line)
    HANDS[f'hand_minute_classic_{_k}'] = _photo('minute', 182, thin=0.5, outline=True, edge=_line, glow=_line)
    HANDS[f'hand_hour_light_{_k}'] = _photo('hour', 118, thin=0.48, alpha=0.6, outline=True, edge=_tones[0], glow=_tones[1])
    HANDS[f'hand_minute_light_{_k}'] = _photo('minute', 182, thin=0.5, alpha=0.6, outline=True, edge=_tones[0], glow=_tones[1])
    HANDS[f'hand_hour_dark_{_k}'] = (lambda c=_line: outline_hand(112, 16, 10, color=c), 10, 112, 16, 2)
    HANDS[f'hand_hour_vana_{_k}'] = (lambda c=_tones[1]: ink_hand(110, 18, 10, inlay=c), 10, 110, 18, 3)
    HANDS[f'hand_minute_vana_{_k}'] = (lambda c=_tones[1]: ink_hand(176, 22, 8, inlay=c), 8, 176, 22, 3)
    HANDS[f'hand_minute_dark_{_k}'] = (lambda c=_line: outline_hand(180, 20, 8, color=c), 8, 180, 20, 2)
HANDS.update({
    'hand_hour_seiko': (lambda: lume_hand(98, 18, 12), 12, 98, 18, HAND_PAD),
    'hand_minute_seiko': (lambda: lume_hand(152, 22, 10), 10, 152, 22, HAND_PAD),
    'hand_chrono_seiko': (chrono_hand, 10, 166, 36, 3),
})
for _key, _ink in (('sandoria', 'red'), ('windurst', 'green'), ('bastok', 'blue')):
    HANDS[f'hand_sub_{_ink}_seiko'] = (lambda c=NATION_INK[_key]: with_shadow(needle_hand(40, 10, 1.4, 2.4, color=c + (255,), ring_fill=c + (255,)), 0.8, 0.4),
                                       8, 40, 10, 2)
LIGHT_NEEDLE = {'sandoria': 'hand_sub_red', 'windurst': 'hand_sub_green', 'bastok': 'hand_sub_blue'}


def hand_geom(name):
    """(canvas width, pivot-from-top, canvas height) in 450px units."""
    _, w, tip, tail, pad = HANDS[name]
    return w + 2 * pad, tip + pad, tip + tail + 2 * pad


def patch_xml(overlays=None):
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
        assert n >= 1, pattern

    setattrs(r'<HourHand resource="hand_hour_dark" [^>]*>', 225, 225, 'hand_hour_dark')
    setattrs(r'<MinuteHand resource="hand_minute_dark" [^>]*>', 225, 225, 'hand_minute_dark')
    for style in ('classic', 'dark', 'light', 'vana'):
        for k in range(8):
            setattrs(rf'<HourHand resource="hand_hour_{style}_{k}" [^>]*>', 225, 225, f'hand_hour_{style}_{k}')
            setattrs(rf'<MinuteHand resource="hand_minute_{style}_{k}" [^>]*>', 225, 225, f'hand_minute_{style}_{k}')
    for name, (x, y, w, h) in (overlays or {}).items():
        xml, n = re.subn(rf'(<PartImage name="{name}" )[^>]*>', rf'\g<1>x="{x}" y="{y}" width="{w}" height="{h}">', xml)
        assert n == 1, name
    for sfx in ('', '_dark'):
        for pos, (cx, cy) in POSITIONS.items():
            setattrs(rf'<PartImage name="sub_{pos}{sfx}" [^>]*>', cx, cy, 'hand_sub' + sfx)
    for pos, (cx, cy) in POSITIONS.items():
        setattrs(rf'<PartImage name="sub_{pos}_light" [^>]*>', cx, cy, LIGHT_NEEDLE[LAYOUT[pos]])
    setattrs(r'<PartImage name="vana_hand_\d_\w+" [^>]*>', *VANA_POS, 'hand_vana_0')
    for pos, (cx, cy) in POSITIONS.items():
        setattrs(rf'<PartImage name="sub_{pos}_vana" [^>]*>', cx, cy, 'hand_sub_ink')
    for pos, (cx, cy) in SEIKO_POS.items():
        ink = {'sandoria': 'red', 'windurst': 'green', 'bastok': 'blue'}[SEIKO_LAYOUT[pos][0]]
        setattrs(rf'<PartImage name="sub_{pos}_seiko" [^>]*>', cx, cy, f'hand_sub_{ink}_seiko')
    setattrs(r'<PartImage name="chrono_seiko" [^>]*>', 225, 225, 'hand_chrono_seiko')
    setattrs(r'<HourHand resource="hand_hour_seiko" [^>]*>', 225, 225, 'hand_hour_seiko')
    setattrs(r'<MinuteHand resource="hand_minute_seiko" [^>]*>', 225, 225, 'hand_minute_seiko')
    for name, (_, half) in CAPS.items():
        xml, n = re.subn(rf'(<PartImage name="{name}" )[^>]*>',
                         rf'\g<1>x="{225 - half:g}" y="{225 - half:g}" width="{2 * half:g}" height="{2 * half:g}">', xml)
        assert n >= 1, name
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


PREVIEW_UTC = 1793270400   # sample moment for the previews


def place_vana_hand(img, hands_hi, utc=PREVIEW_UTC):
    vh, vm, wd = vana_now(utc)
    place(img, hands_hi[f'hand_vana_{wd}'], f'hand_vana_{wd}', *VANA_POS, (vh + vm / 60) * 15)


def preview(dial_hi, hands_hi, caps_hi, glass_hi, hh=10, mm=8, ss=32, dow=5, day=29, batt=78, ambient=False, dark=False,
            crystals=None, utc=PREVIEW_UTC):
    img = dial_hi.copy()
    sfx = '_dark' if dark else ''
    wd = vana_now(utc)[2]
    style = 'dark' if dark else 'classic'
    if crystals and not (ambient and not dark):
        img.alpha_composite(crystals[(style, wd)])
    cap_hi = caps_hi['cap' + sfx]
    sub = hands_hi['hand_sub' + sfx]
    angle = {'left': (dow - 1) * 360 / 7, 'right': -150 + batt * 3, 'bottom': (hh + mm / 60) * 15}
    for pos, (cx, cy) in POSITIONS.items():
        place(img, sub, 'hand_sub' + sfx, cx, cy, angle[pos])
    place_vana_hand(img, hands_hi, utc)
    if not ambient or dark:
        d = ImageDraw.Draw(img)
        text_c(d, (s(DATE_POS[0]), s(DATE_POS[1])), str(day), font(FONT_SERIF, 15),
               (190, 190, 190) if dark else (20, 20, 20))
    hset = f'{style}_{wd}' if crystals and not (ambient and not dark) else 'dark'
    hour, minute = (f'hand_hour_{hset}', f'hand_minute_{hset}') if hset != 'dark' else ('hand_hour_dark', 'hand_minute_dark')
    if ambient and not dark:   # always-on keeps the classic steel look of the chosen style
        hour, minute = f'hand_hour_classic_{wd}', f'hand_minute_classic_{wd}'
    place(img, hands_hi[hour], hour, 225, 225, (hh % 12 + mm / 60) * 30)
    place(img, hands_hi[minute], minute, 225, 225, mm * 6 + ss / 10)
    img.alpha_composite(cap_hi, (round(C - cap_hi.width / 2), round(C - cap_hi.height / 2)))
    if not ambient and not dark:
        img.alpha_composite(glass_hi)
    return finish(img)


def preview_light(dial_hi, hands_hi, caps_hi, glass_hi, hh=10, mm=8, dow=5, day=29, batt=78, crystals=None, utc=PREVIEW_UTC):
    img = dial_hi.copy()
    wd = vana_now(utc)[2]
    img.alpha_composite(crystals[('light', wd)])
    angle = {'left': (dow - 1) * 360 / 7, 'right': -150 + batt * 3, 'bottom': (hh + mm / 60) * 15}
    for pos, (cx, cy) in POSITIONS.items():
        name = LIGHT_NEEDLE[LAYOUT[pos]]
        place(img, hands_hi[name], name, cx, cy, angle[pos])
    place_vana_hand(img, hands_hi, utc)
    text_c(ImageDraw.Draw(img), (s(DATE_POS[0]), s(DATE_POS[1])), str(day), font(FONT_SERIF, 15), (20, 20, 20))
    place(img, hands_hi[f'hand_hour_light_{wd}'], f'hand_hour_light_{wd}', 225, 225, (hh % 12 + mm / 60) * 30)
    place(img, hands_hi[f'hand_minute_light_{wd}'], f'hand_minute_light_{wd}', 225, 225, mm * 6)
    cap = caps_hi['cap_light']
    img.alpha_composite(cap, (round(C - cap.width / 2), round(C - cap.height / 2)))
    img.alpha_composite(glass_hi)
    return finish(img)


def vana_now(t):
    """Vana'diel (hour, minute, weekday index) for a UTC timestamp: same maths as watchface.xml."""
    v = (t - 1024844400) * 25 + (898 * 360 + 30) * 86400
    return int(v % 86400 // 3600), int(v % 3600 // 60), int(v // 86400) % 8


def preview_vana(dial_hi, hands_hi, caps_hi, hh=10, mm=8, dow=5, day=29, batt=78, utc=PREVIEW_UTC):
    img = dial_hi.copy()
    vh, vm, wd = vana_now(utc)
    angle = {'left': (dow - 1) * 360 / 7, 'right': -150 + batt * 3, 'bottom': (hh + mm / 60) * 15}
    for pos, (cx, cy) in POSITIONS.items():
        place(img, hands_hi['hand_sub_ink'], 'hand_sub_ink', cx, cy, angle[pos])
    place_vana_hand(img, hands_hi, utc)
    d = ImageDraw.Draw(img)
    text_c(d, (s(DATE_POS[0]), s(DATE_POS[1])), str(day), font(FONT_SERIF, 15), INK)
    x0, y0, x1, y1 = VANA_BOX
    text_c(d, (s((x0 + x1) / 2), s(y0 + 22)), f'{vh:02d}:{vm:02d}', font(FONT_SERIF, 17), INK)
    text_c(d, (s((x0 + x1) / 2), s(y0 + 36)), ELEMENTS[wd][0].upper(), font(FONT_SERIF, 7.5), ELEMENT_TONES[wd][0] if wd != 6 else INK)
    place(img, hands_hi[f'hand_hour_vana_{wd}'], f'hand_hour_vana_{wd}', 225, 225, (hh % 12 + mm / 60) * 30)
    place(img, hands_hi[f'hand_minute_vana_{wd}'], f'hand_minute_vana_{wd}', 225, 225, mm * 6)
    cap = caps_hi['cap_vana']
    img.alpha_composite(cap, (round(C - cap.width / 2), round(C - cap.height / 2)))
    return finish(img)


def preview_seiko(dial_hi, hands_hi, caps_hi, glass_hi, hh=10, mm=8, ss=32, day=29):
    img = dial_hi.copy()
    angle = {'left': (mm % 30) * 12, 'right': (hh + mm / 60) * 15, 'bottom': ss * 6}
    for pos, (cx, cy) in SEIKO_POS.items():
        ink = {'sandoria': 'red', 'windurst': 'green', 'bastok': 'blue'}[SEIKO_LAYOUT[pos][0]]
        place(img, hands_hi[f'hand_sub_{ink}_seiko'], f'hand_sub_{ink}_seiko', cx, cy, angle[pos])
    text_c(ImageDraw.Draw(img), (s(SEIKO_DATE[0]), s(SEIKO_DATE[1])), str(day), font(FONT_SANS_BOLD, 12.5), (16, 16, 16))
    place(img, hands_hi['hand_hour_seiko'], 'hand_hour_seiko', 225, 225, (hh % 12 + mm / 60) * 30)
    place(img, hands_hi['hand_minute_seiko'], 'hand_minute_seiko', 225, 225, mm * 6)
    place(img, hands_hi['hand_chrono_seiko'], 'hand_chrono_seiko', 225, 225, 0)
    cap = caps_hi['cap_seiko']
    img.alpha_composite(cap, (round(C - cap.width / 2), round(C - cap.height / 2)))
    img.alpha_composite(glass_hi)
    return finish(img)


def main():
    os.makedirs(OUT, exist_ok=True)
    dial_hi = make_dial(crystal=False)
    amb_hi = make_dial(ambient=True)
    dark_hi = make_dial(ambient=True, bright=1.0, crystal=False)
    finish(dial_hi).save(os.path.join(OUT, 'dial.png'))
    finish(amb_hi).save(os.path.join(OUT, 'dial_ambient.png'))
    finish(dark_hi).save(os.path.join(OUT, 'dial_dark.png'))
    light_hi = make_light_dial()
    finish(light_hi).save(os.path.join(OUT, 'dial_light.png'))
    seiko_hi = make_seiko_dial()
    finish(seiko_hi).save(os.path.join(OUT, 'dial_seiko.png'))
    finish(make_seiko_dial(ambient=True)).save(os.path.join(OUT, 'dial_seiko_ambient.png'))
    vana_hi = make_vana_dial()
    finish(vana_hi).save(os.path.join(OUT, 'dial_vana.png'))
    finish(make_vana_dial(ambient=True)).save(os.path.join(OUT, 'dial_vana_ambient.png'))
    for name, color in ELEMENTS:
        finish(element_crystal(color)).save(os.path.join(OUT, 'crystal_' + name.lower() + '.png'))
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
    crystals, overlays = {}, {}
    for style in ('classic', 'dark', 'light'):
        for k in range(8):
            crystals[(style, k)] = full = crystal12(style, k)
            small = finish(full)
            x, y, x1, y1 = small.getchannel('A').getbbox()
            x, y, x1, y1 = x - x % 2, y - y % 2, x1 + x1 % 2, y1 + y1 % 2
            small.crop((x, y, x1, y1)).save(os.path.join(OUT, f'crystal12_{style}_{k}.png'))
            overlays[f'crystal12_{style}_{k}'] = (x, y, x1 - x, y1 - y)
    patch_xml(overlays)
    active = preview(dial_hi, hands_hi, cap_hi, glass_hi, crystals=crystals)
    active.save(os.path.join(OUT, 'preview.png'))
    docs = os.path.join(os.path.dirname(__file__), '..', 'docs')
    os.makedirs(docs, exist_ok=True)
    active.save(os.path.join(docs, 'preview_active.png'))
    preview(amb_hi, hands_hi, cap_hi, glass_hi, ambient=True).save(os.path.join(docs, 'preview_ambient.png'))
    dark = preview(dark_hi, hands_hi, cap_hi, glass_hi, ambient=True, dark=True, crystals=crystals)
    dark.save(os.path.join(docs, 'preview_dark.png'))
    light = preview_light(light_hi, hands_hi, cap_hi, glass_hi, crystals=crystals)
    light.save(os.path.join(docs, 'preview_light.png'))
    vana = preview_vana(vana_hi, hands_hi, cap_hi)
    vana.save(os.path.join(docs, 'preview_vana.png'))
    seiko = preview_seiko(seiko_hi, hands_hi, cap_hi, glass_hi)
    seiko.save(os.path.join(docs, 'preview_wearevanadiel.png'))
    # weekday showcase: the same faces on four Vana'diel days
    days = [(1, 'Firesday'), (3, 'Watersday'), (4, 'Windsday'), (6, 'Lightningday')]
    show = Image.new('RGB', (4 * 300 + 20, 3 * 300 + 50), (18, 18, 22))
    sd = ImageDraw.Draw(show)
    for col, (n, label) in enumerate(days):
        utc = PREVIEW_UTC + n * 3456
        sd.text((10 + col * 300 + 150, 22), label, font=ImageFont.truetype(FONT_LABEL, 20), fill=(230, 230, 230), anchor='mm')
        faces = (preview(dial_hi, hands_hi, cap_hi, glass_hi, crystals=crystals, utc=utc),
                 preview(dark_hi, hands_hi, cap_hi, glass_hi, ambient=True, dark=True, crystals=crystals, utc=utc),
                 preview_light(light_hi, hands_hi, cap_hi, glass_hi, crystals=crystals, utc=utc))
        for row, face in enumerate(faces):
            show.paste(face.resize((290, 290), Image.LANCZOS), (15 + col * 300, 45 + row * 300))
    show.save(os.path.join(docs, 'weekday_colors.png'))
    styles = Image.new('RGB', (4 * 460 + 20, 500), (18, 18, 22))
    sd = ImageDraw.Draw(styles)
    for i, (label, im) in enumerate((('Classic', active), ('Dark', dark), ('Light', light), ("Vana'diel Time", vana))):
        styles.paste(im, (15 + i * 460, 40), im)
        sd.text((15 + i * 460 + 225, 20), label, font=ImageFont.truetype(FONT_LABEL, 22), fill=(230, 230, 230), anchor='mm')
    styles.save(os.path.join(docs, 'styles.png'))
    print('assets written to', os.path.abspath(OUT))


if __name__ == '__main__':
    main()
