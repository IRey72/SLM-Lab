"""Render the FFXI "We Are Vana'diel" chronograph-style watch face assets.

Writes PNGs into app/src/main/res/drawable-nodpi/ plus a composited
preview. All art is drawn at SS x supersampling and downscaled.

    python3 tools/generate_assets.py
"""
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
def crystal_pts(r_in, r_out, w, deg):
    a = math.radians(deg)
    u = (math.sin(a), -math.cos(a))       # radial (outward)
    v = (math.cos(a), math.sin(a))        # perpendicular
    k = w * 0.75

    def p(r, off):
        return (C + u[0] * r + v[0] * off, C + u[1] * r + v[1] * off)
    return {
        'out': p(r_out, 0), 'in': p(r_in, 0),
        'ol': p(r_out - k, -w / 2), 'or': p(r_out - k, w / 2),
        'il': p(r_in + k * 0.6, -w / 2), 'ir': p(r_in + k * 0.6, w / 2),
        'core_o': p(r_out - k * 0.9, 0), 'core_i': p(r_in + k * 0.9, 0),
        'cl': p((r_in + r_out) / 2, -w / 5), 'cr': p((r_in + r_out) / 2, w / 5),
    }


def crystal_outline(d, r_in, r_out, w, deg, color):
    P = crystal_pts(s(r_in), s(r_out), s(w), deg)
    d.polygon([P['out'], P['ol'], P['il'], P['in'], P['ir'], P['or']], outline=color, width=round(s(1.5)))


CRYSTAL_R = (140, 204)   # 12 o'clock crystal spans these radii
MARKER_R = (160, 201)    # clear crystal hour markers span these radii


def load_crystal(height, clear=False):
    cr = Image.open(os.path.join(EMBLEMS, 'crystal.png')).convert('RGBA')
    cr = cr.resize((round(height * cr.width / cr.height), round(height)), Image.LANCZOS)
    if clear:   # rock-crystal version: desaturate, lift and cool the tone
        a = np.asarray(cr).astype(float)
        lum = (a[..., :3] @ [0.3, 0.45, 0.25])[..., None]
        lum = 255 * (np.clip(lum / 255, 0, 1) ** 0.6)
        rgb = lum * np.array([0.90, 0.95, 1.0]) * 0.85 + a[..., :3] * 0.15
        cr = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a[..., 3]]).astype(np.uint8), 'RGBA')
    return cr


def place_marker(img, deg):
    """Clear crystal hour marker, long axis radial, with a cast shadow."""
    r0, r1 = MARKER_R
    cr = load_crystal(s(r1 - r0), clear=True).rotate(-deg, resample=Image.BICUBIC, expand=True)
    cx, cy = polar(s((r0 + r1) / 2), deg)
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    layer.paste(cr, (round(cx - cr.width / 2), round(cy - cr.height / 2)))
    drop_shadow(img, layer.getchannel('A'), blur=1.2, alpha=0.65)
    img.alpha_composite(layer)


def place_crystal(img, ambient, bright=1.0):
    """The big blue crystal at 12, from tools/emblems/crystal.png (background already cut out)."""
    cr = load_crystal(s(CRYSTAL_R[1] - CRYSTAL_R[0]))
    if ambient:   # dim it so always-on stays mostly dark
        r, g, b, a = cr.split()
        cr = Image.merge('RGBA', [ch.point(lambda v: int(v * 0.6 * bright)) for ch in (r, g, b)] + [a])
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


def emblem_lines(em, bright=1.0):
    """Colour-edge line art of a crest (works where greyscale fails, e.g. black griffins on red)."""
    size = em.size
    a = np.asarray(em.resize((256, 256), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.2))).astype(float)
    gy = np.abs(np.diff(a, axis=0, prepend=a[:1])).sum(-1)
    gx = np.abs(np.diff(a, axis=1, prepend=a[:, :1])).sum(-1)
    e = np.clip((gx + gy - 40) * 1.6, 0, 210) * bright
    return Image.fromarray(e.astype(np.uint8)).resize(size, Image.LANCZOS).convert('RGB')


def draw_emblem(img, key, cx, cy, ambient, bright=1.0):
    """Nation crest in a round medallion at the sub-dial centre."""
    r = s(EMBLEM_R)
    em = Image.open(os.path.join(EMBLEMS, key + '.png')).convert('RGB').resize((2 * r, 2 * r), Image.LANCZOS)
    if ambient:   # engraved line art: readable on black and keeps few pixels lit
        em = emblem_lines(em, bright)
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

    # hour indices: crystals; 12 = blue crystal, 11 = "XI"
    for h in (1, 2, 4, 5, 7, 8, 10):
        a = h * 30
        if ambient:
            crystal_outline(d, 162, 200, 16, a, (150, 150, 150))
        else:
            place_marker(img, a)
    d = ImageDraw.Draw(img)
    if not ambient:
        glow = Image.new('RGBA', size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([C - s(24), C - s(208), C + s(24), C - s(136)], fill=(60, 110, 255, 150))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s(9))))
    place_crystal(img, ambient, bright)
    d = ImageDraw.Draw(img)

    pos = polar(s(180), 330)
    if ambient:
        text_ff(d, pos, 'XI', 34, (0, 0, 0), stroke=round(s(1)), stroke_fill=(150, 150, 150))
    else:
        # applied (raised) gold numeral and wordmark; small print stays flat like pad printing
        applied_text(img, lambda dd, f: text_ff(dd, pos, 'XI', 34, f))
        applied_text(img, lambda dd, f: text_ff(dd, (C, C - s(104)), "VANA'DIEL", 23, f))
        d = ImageDraw.Draw(img)
        text_c(d, (C, C - s(123)), 'WE ARE', font(FONT_LABEL, 8), (200, 206, 218))
        text_c(d, (C, C - s(85)), 'CHRONOGRAPH', font(FONT_LABEL, 6.5), (170, 178, 192))

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
    img = Image.new('RGBA', (s(w + 2 * pad), s(tip + tail + 2 * pad)), (0, 0, 0, 0))
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


def dauphine(w, tip, tail):
    """Polished faceted dauphine hand with a lume insert."""
    img, px, py = hand_canvas(w, tip, tail)
    half = s(w) / 2 - SS
    tip_pt, tail_pt = (px, py - s(tip) + SS), (px, py + s(tail) - SS)
    wide_y = py - s(tip) * 0.12
    left = [tip_pt, (px - half, wide_y), (px - half * 0.55, tail_pt[1]), tail_pt]
    right = [tip_pt, (px + half, wide_y), (px + half * 0.55, tail_pt[1]), tail_pt]
    along = ((px, tip_pt[1]), (px, tail_pt[1]))
    fill_mask(img, poly_mask(img.size, left), lgrad(img.size, *along, [(0, (255, 255, 255)), (0.6, (214, 220, 230)), (1, (176, 184, 198))]))
    fill_mask(img, poly_mask(img.size, right), lgrad(img.size, *along, [(0, (150, 158, 172)), (0.6, (96, 104, 120)), (1, (70, 76, 90))]))
    d = ImageDraw.Draw(img)
    d.line([tip_pt, tail_pt], fill=(255, 255, 255, 140), width=SS)          # polished ridge
    d.polygon(left[:-1] + right[-2:0:-1], outline=(36, 40, 50), width=SS)
    # lume insert set into the hand
    lw = half * 0.45
    lume = [(px, py - s(tip) * 0.88), (px - lw, py - s(tip) * 0.2), (px, py - s(tip) * 0.12), (px + lw, py - s(tip) * 0.2)]
    fill_mask(img, poly_mask(img.size, lume), lgrad(img.size, *along, [(0, (236, 250, 226)), (1, (198, 222, 190))]))
    d.polygon(lume, outline=(110, 118, 130), width=SS)
    return with_shadow(img)


def domed_cap(r, pad=HAND_PAD):
    """Static polished centre cap (drawn above the hands so its highlight never rotates)."""
    size = s(2 * (r + pad))
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c = size / 2
    m = circle_mask(img.size, c, c, s(r))
    hl = radial_gradient(img.size, (255, 255, 255), (96, 102, 116), cx=c - s(r * 0.35), cy=c - s(r * 0.45), r=s(r * 1.5))
    fill_mask(img, m, hl)
    ImageDraw.Draw(img).ellipse([c - s(r), c - s(r), c + s(r), c + s(r)], outline=(40, 44, 54), width=SS)
    ImageDraw.Draw(img).ellipse([c - s(1.6), c - s(1.6), c + s(1.6), c + s(1.6)], fill=(70, 76, 90))
    return with_shadow(img, blur=1.4, alpha=0.7)


def sub_hand(w=10, tip=46, tail=10):
    img, px, py = hand_canvas(w, tip, tail, pad=3)
    body = [(px, py - s(tip) + SS), (px - s(1.8), py), (px - s(1.2), py + s(tail) - SS),
            (px + s(1.2), py + s(tail) - SS), (px + s(1.8), py)]
    fill_mask(img, poly_mask(img.size, body), lgrad(img.size, (px - s(1.8), py), (px + s(1.8), py),
                                                     [(0, (255, 255, 255)), (0.5, (236, 238, 242)), (1, (150, 156, 168))]))
    d = ImageDraw.Draw(img)
    d.polygon(body, outline=(40, 40, 40), width=SS)
    cap = radial_gradient(img.size, (255, 255, 255), (120, 126, 138), cx=px, cy=py, r=s(4))   # symmetric: rotation-proof
    fill_mask(img, circle_mask(img.size, px, py, s(4)), cap)
    d.ellipse([px - s(4), py - s(4), px + s(4), py + s(4)], outline=(40, 40, 40), width=SS)
    return with_shadow(img, blur=1.0, alpha=0.6)


CAP_R = 8

HANDS = {
    # name: (builder, visual width, tip length, tail length, shadow padding)
    'hand_hour': (lambda: dauphine(22, 118, 22), 22, 118, 22, HAND_PAD),
    'hand_minute': (lambda: dauphine(18, 180, 26), 18, 180, 26, HAND_PAD),
    'hand_sub': (sub_hand, 10, 46, 10, 3),
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

    setattrs(r'<HourHand [^>]*>', 225, 225, 'hand_hour')
    setattrs(r'<MinuteHand [^>]*>', 225, 225, 'hand_minute')
    for key, (cx, cy) in sub_centers().items():
        setattrs(rf'<PartImage name="sub_{key}" [^>]*>', cx, cy, 'hand_sub')
    cw = 2 * (CAP_R + HAND_PAD)
    xml = re.sub(r'(<PartImage name="cap" )[^>]*>', rf'\g<1>x="{225 - cw / 2:g}" y="{225 - cw / 2:g}" width="{cw}" height="{cw}">', xml)
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


def preview(dial_hi, hands_hi, cap_hi, glass_hi, hh=10, mm=8, ss=32, dow=5, day=29, batt=78, ambient=False, dark=False):
    img = dial_hi.copy()
    sub = hands_hi['hand_sub']
    centers = sub_centers()
    place(img, sub, 'hand_sub', *centers['sandoria'], (dow - 1) * 360 / 7)
    place(img, sub, 'hand_sub', *centers['bastok'], -150 + batt * 3)
    place(img, sub, 'hand_sub', *centers['windurst'], (hh + mm / 60) * 15)
    if not ambient or dark:
        d = ImageDraw.Draw(img)
        text_c(d, (s(DATE_POS[0]), s(DATE_POS[1])), str(day), font(FONT_SERIF, 15),
               (190, 190, 190) if dark else (20, 20, 20))
    place(img, hands_hi['hand_hour'], 'hand_hour', 225, 225, (hh % 12 + mm / 60) * 30)
    place(img, hands_hi['hand_minute'], 'hand_minute', 225, 225, mm * 6 + ss / 10)
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
    cap_hi = domed_cap(CAP_R)
    finish(cap_hi).save(os.path.join(OUT, 'cap.png'))
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
