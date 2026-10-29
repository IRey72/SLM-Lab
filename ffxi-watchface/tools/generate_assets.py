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

# Layout (in 450px units) -- keep in sync with watchface.xml
SUB_OFFSET = 100   # sub-dial centre distance from main centre
SUB_R = 56         # sub-dial radius
DATE_POS = (225 + 103, 225 + 103)  # date window centre (4:30)
DATE_SIZE = (34, 24)

NAVY_IN, NAVY_OUT = (30, 48, 84), (6, 11, 24)
GOLD, GOLD_DK = (222, 182, 84), (140, 104, 34)
SILVER, SILVER_DK = (226, 230, 236), (128, 136, 150)
LUME = (226, 244, 214)
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


def draw_crystal(d, r_in, r_out, w, deg, light, mid, dark, outline):
    P = crystal_pts(s(r_in), s(r_out), s(w), deg)
    d.polygon([P['out'], P['ol'], P['il'], P['in']], fill=light)
    d.polygon([P['out'], P['or'], P['ir'], P['in']], fill=dark)
    d.polygon([P['core_o'], P['cl'], P['core_i'], P['cr']], fill=mid)
    d.polygon([P['out'], P['ol'], P['il'], P['in'], P['ir'], P['or']], outline=outline, width=round(s(1)))


def crystal_outline(d, r_in, r_out, w, deg, color):
    P = crystal_pts(s(r_in), s(r_out), s(w), deg)
    d.polygon([P['out'], P['ol'], P['il'], P['in'], P['ir'], P['or']], outline=color, width=round(s(1.5)))


# --------------------------------------------------------------------- dial
def sub_centers():
    return {
        'sandoria': (225 - SUB_OFFSET, 225),   # 9 o'clock: day of week
        'bastok': (225 + SUB_OFFSET, 225),     # 3 o'clock: battery
        'windurst': (225, 225 + SUB_OFFSET),   # 6 o'clock: 24 hour
    }


def draw_subdial(img, key, ambient=False):
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
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=SILVER, width=round(s(2.2)))
        d.ellipse([cx - R + s(3), cy - R + s(3), cx + R - s(3), cy + R - s(3)],
                  outline=(0, 0, 0, 110), width=round(s(1)))
    else:
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(110, 110, 110), width=round(s(1.2)))

    small = font(FONT_LABEL, 8)
    num = font(FONT_NUM, 8.5)
    tiny = font(FONT_LABEL, 6.5)
    tick_r0, tick_r1, lab_r = R - s(3), R - s(8), R - s(16)
    if key == 'sandoria':
        days = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA']
        for i, lab in enumerate(days):
            a = i * 360 / 7
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1, a, cx, cy)], fill=fg, width=round(s(1.4)))
            text_c(d, polar(lab_r, a, cx, cy), lab, small, fg)
        name = "SAN D'ORIA"
    elif key == 'bastok':
        for i in range(11):
            a = -150 + i * 30
            long_ = i % 5 == 0
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1 - (s(2) if long_ else 0), a, cx, cy)],
                   fill=fg, width=round(s(1.6 if long_ else 1)))
        for val, a in (('E', -150), ('½', 0), ('F', 150)):
            text_c(d, polar(lab_r - s(2), a, cx, cy), val, num, fg)
        name = 'BASTOK'
    else:
        for i in range(24):
            a = i * 15
            long_ = i % 6 == 0
            d.line([polar(tick_r0, a, cx, cy), polar(tick_r1 - (s(2) if long_ else s(-2)), a, cx, cy)],
                   fill=fg, width=round(s(1.6 if long_ else 0.8)))
        for val, a in (('24', 0), ('6', 90), ('12', 180), ('18', 270)):
            text_c(d, polar(lab_r - s(2), a, cx, cy), val, num, fg)
        name = 'WINDURST'
    text_c(d, (cx, cy + s(20)), name, tiny, GOLD if not ambient else (120, 120, 120))


def make_dial(ambient=False):
    size = (s(N), s(N))
    if ambient:
        img = Image.new('RGBA', size, (0, 0, 0, 255))
    else:
        img = radial_gradient(size, NAVY_IN, NAVY_OUT, r=s(225))
        # sunburst texture
        sb = Image.new('RGBA', size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sb)
        for i in range(720):
            a = i * 0.5
            alpha = 16 if i % 2 else 0
            sd.line([(C, C), polar(s(230), a)], fill=(255, 255, 255, alpha), width=SS)
        img.alpha_composite(sb.filter(ImageFilter.GaussianBlur(SS * 0.6)))
    d = ImageDraw.Draw(img)

    # outer minute track ("bezel" ring)
    if not ambient:
        d.ellipse([C - s(225), C - s(225), C + s(225), C + s(225)], outline=(18, 22, 30), width=round(s(20)))
        d.ellipse([C - s(205), C - s(205), C + s(205), C + s(205)], outline=(90, 98, 112), width=round(s(1)))
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
            draw_crystal(d, 162, 200, 16, a, (246, 249, 255), (200, 214, 232), (120, 136, 160), (60, 70, 90))
    if ambient:
        crystal_outline(d, 145, 203, 28, 0, (110, 150, 255))
    else:
        glow = Image.new('RGBA', size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([C - s(26), C - s(208), C + s(26), C - s(140)], fill=(60, 130, 255, 150))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s(9))))
        d = ImageDraw.Draw(img)
        draw_crystal(d, 145, 203, 28, 0, (150, 200, 255), (70, 140, 255), (20, 60, 170), (10, 30, 90))
        # sparkle
        sx, sy = polar(s(186), -3)
        d.line([(sx - s(4), sy), (sx + s(4), sy)], fill=(255, 255, 255, 220), width=SS)
        d.line([(sx, sy - s(4)), (sx, sy + s(4))], fill=(255, 255, 255, 220), width=SS)

    xi = font(FONT_SERIF, 30)
    pos = polar(s(180), 330)
    if ambient:
        text_c(d, pos, 'XI', xi, (0, 0, 0), stroke_width=round(s(1)), stroke_fill=(150, 150, 150))
    else:
        text_c(d, (pos[0] + s(1), pos[1] + s(1.5)), 'XI', xi, (0, 0, 0, 160))
        text_c(d, pos, 'XI', xi, GOLD, stroke_width=round(s(0.6)), stroke_fill=GOLD_DK)

    # wordmark
    if not ambient:
        text_c(d, (C, C - s(121)), 'WE ARE', font(FONT_LABEL, 8), (200, 206, 218))
        text_c(d, (C, C - s(104)), "VANA'DIEL", font(FONT_SERIF, 18), GOLD)
        text_c(d, (C, C - s(87)), 'CHRONOGRAPH', font(FONT_LABEL, 6.5), (170, 178, 192))

    for key in NATIONS:
        draw_subdial(img, key, ambient)

    # date window frame (number drawn live by the watch face)
    if not ambient:
        d = ImageDraw.Draw(img)
        x, y = s(DATE_POS[0]), s(DATE_POS[1])
        w, h = s(DATE_SIZE[0]), s(DATE_SIZE[1])
        d.rounded_rectangle([x - w / 2 - s(2), y - h / 2 - s(2), x + w / 2 + s(2), y + h / 2 + s(2)],
                            radius=s(4), fill=SILVER_DK)
        d.rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=s(3), fill=(244, 242, 236))

    img.putalpha(circle_mask(size, C, C, s(225)))
    return img


# --------------------------------------------------------------------- hands
def hand_canvas(w, tip, tail):
    """Canvas for a hand whose pivot is at (w/2, tip)."""
    img = Image.new('RGBA', (s(w), s(tip + tail)), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), s(w) / 2, s(tip)


def dauphine(w, tip, tail, cap=0):
    img, d, px, py = hand_canvas(w, tip, tail)
    half = s(w) / 2 - SS
    tip_pt, tail_pt = (px, py - s(tip) + SS), (px, py + s(tail) - SS)
    wide_y = py - s(tip) * 0.12
    d.polygon([tip_pt, (px - half, wide_y), (px - half * 0.55, tail_pt[1]), tail_pt], fill=SILVER)
    d.polygon([tip_pt, (px + half, wide_y), (px + half * 0.55, tail_pt[1]), tail_pt], fill=SILVER_DK)
    d.polygon([tip_pt, (px - half, wide_y), (px - half * 0.55, tail_pt[1]),
               (px + half * 0.55, tail_pt[1]), (px + half, wide_y)], outline=(40, 44, 54), width=SS)
    # lume insert
    lw = half * 0.45
    d.polygon([(px, py - s(tip) * 0.88), (px - lw, py - s(tip) * 0.2),
               (px, py - s(tip) * 0.12), (px + lw, py - s(tip) * 0.2)], fill=LUME)
    if cap:
        d.ellipse([px - s(cap), py - s(cap), px + s(cap), py + s(cap)], fill=SILVER, outline=(60, 64, 74), width=SS)
        d.ellipse([px - s(2.5), py - s(2.5), px + s(2.5), py + s(2.5)], fill=(90, 96, 108))
    return img


def excalibur(w=40, tip=195, tail=50):
    """Seconds hand styled after Excalibur: blade to the tip, hilt as counterweight."""
    img, d, px, py = hand_canvas(w, tip, tail)
    guard_y = py - s(14)
    blade_w = s(3.6)
    taper_y = py - s(tip - 22)
    tip_y = py - s(tip) + SS
    # blade (two facets + fuller)
    d.polygon([(px, tip_y), (px - blade_w, taper_y), (px - blade_w, guard_y), (px, guard_y)], fill=(244, 246, 250))
    d.polygon([(px, tip_y), (px + blade_w, taper_y), (px + blade_w, guard_y), (px, guard_y)], fill=(150, 160, 176))
    d.line([(px, guard_y - s(4)), (px, taper_y)], fill=(110, 140, 220), width=round(s(1)))
    # crossguard: swept wings
    g = [(px - s(18), guard_y - s(7)), (px - s(14), guard_y - s(2)), (px - s(5), guard_y + s(1)),
         (px, guard_y + s(4)), (px + s(5), guard_y + s(1)), (px + s(14), guard_y - s(2)),
         (px + s(18), guard_y - s(7)), (px + s(12), guard_y - s(5)), (px, guard_y - s(4)),
         (px - s(12), guard_y - s(5))]
    d.polygon(g, fill=GOLD, outline=GOLD_DK, width=SS)
    d.ellipse([px - s(3), guard_y - s(3.5), px + s(3), guard_y + s(2.5)], fill=(50, 110, 255), outline=(200, 230, 255), width=SS)
    # grip with gold bands
    d.rectangle([px - s(2.6), guard_y + s(4), px + s(2.6), py + s(38)], fill=(28, 52, 130))
    for yy in range(int(guard_y + s(8)), int(py + s(38)), s(5)):
        d.line([(px - s(2.6), yy), (px + s(2.6), yy - s(1.5))], fill=GOLD, width=SS)
    # pommel
    pm = py + s(43)
    d.ellipse([px - s(6), pm - s(6), px + s(6), pm + s(6)], fill=GOLD, outline=GOLD_DK, width=SS)
    d.ellipse([px - s(3), pm - s(3), px + s(3), pm + s(3)], fill=(50, 110, 255))
    # pivot cap
    d.ellipse([px - s(6), py - s(6), px + s(6), py + s(6)], fill=GOLD, outline=GOLD_DK, width=SS)
    d.ellipse([px - s(2), py - s(2), px + s(2), py + s(2)], fill=(60, 40, 10))
    return img


def sub_hand(w=10, tip=46, tail=10):
    img, d, px, py = hand_canvas(w, tip, tail)
    d.polygon([(px, py - s(tip) + SS), (px - s(1.8), py), (px - s(1.2), py + s(tail) - SS),
               (px + s(1.2), py + s(tail) - SS), (px + s(1.8), py)], fill=(250, 250, 250), outline=(40, 40, 40), width=SS)
    d.ellipse([px - s(4), py - s(4), px + s(4), py + s(4)], fill=SILVER, outline=(40, 40, 40), width=SS)
    return img


HANDS = {
    # name: (builder, width, tip, tail)
    'hand_hour': (lambda: dauphine(22, 118, 22), 22, 118, 22),
    'hand_minute': (lambda: dauphine(18, 180, 26, cap=9), 18, 180, 26),
    'hand_second': (excalibur, 40, 195, 50),
    'hand_sub': (sub_hand, 10, 46, 10),
}


# --------------------------------------------------------------------- preview
def place(canvas, hand, w, tip, cx, cy, deg):
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    layer.paste(hand, (int(s(cx) - s(w) / 2), int(s(cy) - s(tip))))
    canvas.alpha_composite(layer.rotate(-deg, center=(s(cx), s(cy)), resample=Image.BICUBIC))


def preview(dial_hi, hands_hi, hh=10, mm=8, ss=32, dow=5, day=29, batt=78, ambient=False):
    img = dial_hi.copy()
    sub = hands_hi['hand_sub']
    centers = sub_centers()
    place(img, sub, 10, 46, *centers['sandoria'], (dow - 1) * 360 / 7)
    place(img, sub, 10, 46, *centers['bastok'], -150 + batt * 3)
    place(img, sub, 10, 46, *centers['windurst'], (hh + mm / 60) * 15)
    if not ambient:
        d = ImageDraw.Draw(img)
        text_c(d, (s(DATE_POS[0]), s(DATE_POS[1])), str(day), font(FONT_SERIF, 15), (20, 20, 20))
    place(img, hands_hi['hand_hour'], 22, 118, 225, 225, (hh % 12 + mm / 60) * 30)
    place(img, hands_hi['hand_minute'], 18, 180, 225, 225, mm * 6 + ss / 10)
    if not ambient:
        place(img, hands_hi['hand_second'], 40, 195, 225, 225, ss * 6)
    return finish(img)


def main():
    os.makedirs(OUT, exist_ok=True)
    dial_hi = make_dial()
    amb_hi = make_dial(ambient=True)
    finish(dial_hi).save(os.path.join(OUT, 'dial.png'))
    finish(amb_hi).save(os.path.join(OUT, 'dial_ambient.png'))
    hands_hi = {}
    for name, (build, *_rest) in HANDS.items():
        hands_hi[name] = build()
        finish(hands_hi[name]).save(os.path.join(OUT, name + '.png'))
    preview(dial_hi, hands_hi).save(os.path.join(OUT, 'preview.png'))
    docs = os.path.join(os.path.dirname(__file__), '..', 'docs')
    os.makedirs(docs, exist_ok=True)
    preview(dial_hi, hands_hi).save(os.path.join(docs, 'preview_active.png'))
    preview(amb_hi, hands_hi, ambient=True).save(os.path.join(docs, 'preview_ambient.png'))
    print('assets written to', os.path.abspath(OUT))


if __name__ == '__main__':
    main()
