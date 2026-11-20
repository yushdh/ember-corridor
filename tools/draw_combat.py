"""Bake the combat cast, motion and independent action trails at logical resolution."""
import json
import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.attacks import STRIKES
from game.combat import FORK_HEIGHT, FORK_REACH, TYPES
from draw_walker import draw_frame, draw_sabre, INK

OUT = ROOT / "assets/combat"
SIZE = (160, 128)
SOLE = (80, 102)
META = {}


def weapon(im, hand, tip, heavy):
    d = ImageDraw.Draw(im)
    dx, dy = tip[0] - hand[0], tip[1] - hand[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length

    def p(s, n):
        return round(hand[0] + ux * s - uy * n), round(hand[1] + uy * s + ux * n)

    def poly(coords, color):
        d.polygon([p(*v) for v in coords], fill=color, outline=INK)

    if heavy:
        poly([(-7, -2), (length - 7, -3), (length - 4, 2), (-7, 3)], "#977b5d")
        poly(
            [
                (length - 13, -7),
                (length - 9, -12),
                (length - 1, -12),
                (length + 4, -8),
                (length + 3, 7),
                (length - 1, 11),
                (length - 12, 8),
            ],
            "#657987",
        )
        d.line([p(length - 8, -10), p(length - 1, -10), p(length + 2, -7)], fill="#c3c7ad", width=2)
        poly(
            [
                (length - 13, -6),
                (length - 8, -10),
                (length - 6, -7),
                (length - 8, 7),
                (length - 13, 6),
            ],
            "#48525e",
        )
        d.line(
            [p(length - 7, 7), p(length - 4, 4), p(length - 5, 1), p(length - 2, -3)],
            fill="#f2bb73",
            width=2,
        )
        d.line([p(length + 2, -6), p(length + 1, 5)], fill="#a9c8c5", width=2)
        for s in (5, 10, 15):
            d.line([p(s, -2), p(s - 1, 2)], fill="#543c3b")
    else:
        draw_sabre(d, hand, tip)


def at_body(body):
    im = Image.new("RGBA", SIZE)
    im.alpha_composite(body, (SOLE[0] - 48, SOLE[1] - 80))
    return im


def strike_frame(name, i):
    rule = STRIKES[name]
    grip, tip = rule.blade(i)
    hx, hy = grip
    heavy = name == "breaker"
    # Load the back leg, drive over the lead knee, then gather the feet.
    poses = {
        "cut": ((-1, -4, -5, 5, 8, 4, 1), (1, 2, 3, 1, 4, 4, 1), (1, 2, 3, 5, 7, 5, 1)),
        "liftcut": ((2, 1, -3, 5, 7, 4, 1), (4, 6, 8, 4, -1, 0, 2), (3, 4, 5, 7, 5, 4, 1)),
        "thrust": ((1, -3, -6, 6, 9, 6, 1), (1, 3, 5, 2, 3, 4, 1), (2, 3, 3, 8, 10, 7, 2)),
        "breaker": ((1, -3, -6, 3, 8, 7, 2), (3, 4, 6, 1, 10, 9, 3), (2, 4, 5, 7, 9, 8, 3)),
    }
    lean, bob, spread = (values[i] for values in poses[name])
    # Pivot over the rear heel during preparation; transfer to the lead knee on contact.
    drive = (0, -2, -4, 3, 5, 2, 0)[i]
    pose = (
        (54 + spread + drive, 65 + bob // 2),
        (54 + spread + max(0, drive // 2), 79),
        (40 - spread // 2, 64 + bob // 2),
        (36 - spread, 79),
        (48 + hx, 80 - hy),
        bob,
        lean,
        -spread,
    )
    angle = math.radians(rule.angles[i])
    off = (
        (round(48 + hx + 8 * math.cos(angle)), round(80 - hy - 8 * math.sin(angle)))
        if heavy
        else None
    )
    body, _ = draw_frame("combat", i, pose=pose, armed=False, off_hand=off)
    hand = (SOLE[0] + hx, SOLE[1] - hy)
    im = Image.new("RGBA", SIZE)
    weapon(im, hand, (SOLE[0] + tip[0], SOLE[1] - tip[1]), heavy)
    im.alpha_composite(at_body(body))
    if off:
        x, y = off[0] + 32, off[1] + 22
        ImageDraw.Draw(im).polygon(
            [(x - 3, y - 1), (x, y - 3), (x + 3, y - 1), (x + 2, y + 2), (x - 2, y + 2)],
            fill="#a7835d",
            outline=INK,
        )
    return im, hand


def reaction(i, death):
    amount = i if death else (2, 1, 0)[i]
    bob = 2 + amount * 2
    pose = (
        (58 + amount, 66 + bob // 2),
        (54 + amount, 79),
        (37, 65 + bob // 2),
        (35, 79),
        (49 - amount, 49 + bob),
        bob,
        -3 - amount,
        -2 + amount,
    )
    body, hand = draw_frame("reaction", i, pose=pose, armed=False)
    im = at_body(body)
    hx, hy = hand[0] + 32, hand[1] + 22
    if death:
        angle = (0, 6, 16, 30, 47, 64, 79, 88)[i]
        im = im.rotate(angle, center=SOLE, resample=Image.Resampling.NEAREST)
        box = im.getbbox()
        dy = SOLE[1] - box[3]
        out = Image.new("RGBA", SIZE)
        out.paste(im, (0, dy))
        dx, dy0 = hx - SOLE[0], hy - SOLE[1]
        rad = math.radians(angle)
        hx = round(SOLE[0] + dx * math.cos(rad) + dy0 * math.sin(rad))
        hy = round(SOLE[1] - dx * math.sin(rad) + dy0 * math.cos(rad)) + dy
        im = out
    return im, (hx, hy)


def heavy_move(action, i):
    body, hand = draw_frame(action, i, armed=False)
    im = at_body(body)
    hand = (hand[0] + 32, hand[1] + 22)
    if action != "roll":
        back = Image.new("RGBA", SIZE)
        angles = {"idle": (56, 57, 58, 58, 57, 56), "run": (44, 41, 46, 54, 60, 62, 57, 49),
                  "jump": (44, 51, 57), "fall": (59, 51, 43), "land": (37, 43, 51)}
        angle = math.radians(angles[action][i])
        weapon(back, hand, (hand[0] + round(36*math.cos(angle)), hand[1] - round(36*math.sin(angle))), True)
        back.alpha_composite(im)
        im = back
    return im, hand


def save_rows(filename, rows, size, anchor):
    sw, sh = size
    sheet = Image.new("RGBA", (sw * max(len(frames) for _, frames, _ in rows), sh * len(rows)))
    for row, (name, frames, times) in enumerate(rows):
        entries = []
        for i, ((im, socket), ticks) in enumerate(zip(frames, times, strict=True)):
            sheet.paste(im, (i * sw, row * sh))
            events = []
            if name in STRIKES:
                if i == 3:
                    events = ["active_start"]
                if i == 5:
                    events = ["active_end"]
            entries.append(
                dict(
                    region=[i * sw, row * sh, sw, sh],
                    anchor=anchor,
                    weapon_socket=socket,
                    ticks=ticks,
                    events=events,
                )
            )
        META[name] = dict(sheet=filename, frames=entries)
    sheet.save(OUT / filename)


def tide_fork(i):
    im = Image.new("RGBA", (120, 96))
    d = ImageDraw.Draw(im)

    def pixel(point):
        x, y = point
        return (round(56 + x), round(81 - y))

    def plate(points, color):
        d.polygon([pixel(p) for p in points], fill=color, outline=INK)

    def stroke(points, color, width):
        d.line([pixel(p) for p in points], fill=color, width=width, joint="curve")

    # Torso, boot positions, lead grip and outer tine in sole-relative coordinates.
    x, h, back, front, hand, tip = (
        (0, 43, -9, 9, (11, 26), (26, 54)),
        (1, 42, -9, 9, (12, 25), (29, 52)),
        (2, 42, -14, 13, (13, 24), (33, 50)),
        (3, 44, -3, 5, (12, 27), (25, 55)),
        (-3, 39, -13, 12, (7, 22), (33, 17)),
        (-6, 35, -16, 13, (4, 17), (32, 9)),
        (8, 30, -18, 19, (25, 12), (FORK_REACH, FORK_HEIGHT)),
        (4, 34, -14, 16, (14, 15), (41, 21)),
        (-6, 38, -13, 7, (3, 27), (12, 54)),
        (-19, 14, -25, 13, (-1, 7), (31, 4)),
    )[i]
    for boot, side in ((back, -1), (front, 1)):
        leg = [(x + side * 3, h - 20), (boot + 4, max(7, h // 4)), (boot, 4)]
        stroke(leg, INK, 8)
        stroke(leg, "#586763" if side == 1 else "#39484d", 5)
        plate([(boot - 4, 7), (boot + 2, 7), (boot + 7, 2), (boot + 6, 0), (boot - 5, 0)], "#4b4943")
    plate([(x-9,h-7),(x+7,h-8),(x+9,h-21),(x+3,h-28),(x-3,h-24),(x-13,h-25)], "#60745c")
    stroke([(x-5,h-9),(x+3,h-19),(x-4,h-23)], "#d2b878", 2)
    plate([(x-6,h+1),(x+7,h+1),(x+8,h-7),(x+3,h-11),(x-5,h-7)], "#4a5551")
    stroke([(x+3,h-3),(x+7,h-3)], "#ffdc9a", 2)
    plate([(x-14,h),(x-7,h+5),(x-3,h+9),(x+4,h+8),(x+8,h+3),(x+13,h+1),(x+10,h-1),(x-10,h-2)], "#9c8758")
    stroke([(x-11,h),(x-2,h+3),(x+9,h+1)], "#dec58a", 1)
    hx, hy = hand
    tx, ty = tip
    length = math.hypot(tx-hx, ty-hy)
    ux, uy = (tx-hx)/length, (ty-hy)/length

    def along(distance, normal=0):
        return (tx + distance*ux - normal*uy, ty + distance*uy + normal*ux)

    shaft = [along(-length-20), along(-11)]
    stroke(shaft, INK, 5)
    stroke(shaft, "#ad8c63", 2)
    plate([along(-17, 1), along(-14, 4), along(0, 2), along(-10, 1),
           along(-11, -1), along(-1, -3), along(-14, -3)], "#a2bcb2")
    stroke([along(-13, 3), along(-1, 2)], "#e6edce", 1)
    for side, grip in ((-1, along(-length-10)), (1, hand)):
        arm = [(x + side*5, h-10), (x + side*7, h-18), grip]
        stroke(arm, INK, 6)
        stroke(arm, "#708578" if side == 1 else "#495955", 4)
        stroke([grip, (grip[0]+1,grip[1]+1)], "#e2bc87", 3)
    return im, pixel(hand)


def foe(kind, i):
    if kind == "fork":
        return tide_fork(i)
    im = Image.new("RGBA", (120, 96))
    d = ImageDraw.Draw(im)
    # All mobs face right. These offsets are relative to the sole and use y-up.
    ox, oy = 56, 81
    lean = (0, 1, 2, 3, -3, -5, 6, 3, -4, -7)[i]
    dip = (0, 1, 1, 2, 3, 5, 4, 3, 4, 15)[i]
    bulky = kind == "ram"
    slim = kind == "rivet"
    h = 59 if bulky else 46 if slim else 49
    w = 17 if bulky else 10

    def xy(x, y):
        return (round(ox + x), round(oy - y))

    def poly(points, fill, edge=INK):
        d.polygon([xy(*p) for p in points], fill=fill, outline=edge)

    def line(points, color, width):
        d.line([xy(*p) for p in points], fill=color, width=width, joint="curve")

    def limb(points, c, n):
        line(points, INK, n + 2)
        line(points, c, n)

    dark, metal, light = (
        ("#514b50", "#816b65", "#ceaa80") if not slim else ("#314b53", "#557674", "#adbea7")
    )
    if bulky:
        dark, metal, light = "#3d4351", "#666d75", "#b89d7a"
    shift = (0, 0, 4, -4, 2, 4, 7, 3, -2, 4)[i]
    hip = h * 0.43 - dip
    for side, k in [(-1, -1), (1, 1)]:
        end = side * (w - 2) + shift * k
        knee = end + 3 if k > 0 else end - 1
        limb(
            [(side * 4, hip), (knee, 11 - dip // 4), (end, 4)],
            metal if k > 0 else dark,
            8 if bulky else 6,
        )
        poly([(end - 4, 7), (end + 2, 7), (end + 6, 2), (end + 6, 0), (end - 5, 0)], dark)
        line([(end - 3, 5), (end + 1, 6)], light, 1)
    x = lean
    top = h - 14 - dip
    poly(
        [
            (x - w, top - 2),
            (x - 4, top + 3),
            (x + w, top),
            (w - 3, hip - 2),
            (4, hip - 4),
            (-w - 2, hip - 8),
            (-w + 1, hip + 1),
        ],
        metal,
    )
    if slim:
        poly(
            [(x - 10, top), (x + 4, top - 4), (x - 2, hip - 2), (-15, hip - 8), (-12, hip + 4)],
            "#406c73",
        )
        poly(
            [(x - 15, top - 2), (x - 11, top + 2), (x - 8, top), (x - 8, hip), (x - 15, hip - 2)],
            "#8d7461",
        )
        line([(x - 14, top - 5), (x - 9, top - 5)], "#e7be77", 2)
    if bulky:
        for z in range(3):
            yy = top - 5 - z * 4
            poly([(x - 12, yy + 2), (x + 7, yy + 3), (x + 11, yy), (x - 11, yy - 2)], "#838585")
        poly(
            [
                (x - 24, top + 3),
                (x - 18, top + 9),
                (x - 9, top + 7),
                (x - 6, top),
                (x - 16, top - 5),
            ],
            metal,
        )
        for q in (-19, -14):
            line([(x + q, top + 5), (x + q + 1, top + 5)], "#e8bc77", 2)
    else:
        line([(x - 5, top - 2), (x + 4, hip)], "#ba9271", 3)
    hy = h - dip
    if slim:
        poly(
            [
                (x - 8, hy - 4),
                (x - 5, hy + 1),
                (x + 2, hy + 2),
                (x + 9, hy - 4),
                (x + 12, hy - 7),
                (x + 6, hy - 9),
                (x + 4, hy - 15),
                (x - 4, hy - 15),
                (x - 7, hy - 9),
            ],
            "#567980",
        )
        poly([(x + 2, hy - 7), (x + 11, hy - 7), (x + 7, hy - 11), (x, hy - 10)], "#93ded0")
    elif bulky:
        poly(
            [
                (x - 11, hy - 5),
                (x - 7, hy + 2),
                (x + 5, hy + 3),
                (x + 12, hy - 3),
                (x + 11, hy - 15),
                (x + 3, hy - 18),
                (x - 8, hy - 14),
            ],
            "#7d8385",
        )
        poly([(x - 4, hy - 5), (x + 10, hy - 5), (x + 9, hy - 13), (x - 2, hy - 15)], "#393c47")
        for a in (0, 4, 8):
            line([(x + a, hy - 7), (x + a - 1, hy - 11)], "#f6ac72", 1)
    else:
        poly(
            [
                (x - 10, hy - 8),
                (x - 6, hy),
                (x + 2, hy + 2),
                (x + 8, hy - 1),
                (x + 9, hy - 8),
                (x + 5, hy - 15),
                (x - 3, hy - 14),
            ],
            "#916d64",
        )
        poly([(x - 3, hy - 5), (x + 10, hy - 5), (x + 8, hy - 9), (x, hy - 10)], "#493f4c")
        line([(x + 3, hy - 7), (x + 8, hy - 6)], "#ffd593", 2)
        line([(x - 8, hy - 1), (x - 12, hy + 5), (x - 11, hy + 9)], "#9e9582", 2)
    if kind == "hook":
        poly(
            [
                (x - 11, top + 3),
                (x - 4, top + 5),
                (x + 6, top + 2),
                (x + 3, top - 2),
                (x - 8, top - 3),
                (x - 14, top - 7),
            ],
            "#9d5f50",
        )
        hand = (22, 30) if i == 6 else ((0, 44) if i in (4, 5) else (12 + x, 24 - dip // 2))
        hx, hy = hand
        if i == 6:
            line([(hx - 4, hy), (45, 31), (48, 27), (44, 22)], INK, 5)
            line([(hx - 4, hy), (45, 31), (47, 27), (44, 23)], "#c7ada0", 3)
        else:
            line([(hx, hy - 5), (hx + 4, hy + 14), (hx + 9, hy + 18), (hx + 13, hy + 13)], INK, 5)
            line(
                [(hx, hy - 4), (hx + 4, hy + 14), (hx + 9, hy + 17), (hx + 12, hy + 13)],
                "#c1a78e",
                3,
            )
    elif slim:
        poly(
            [(x - 9, hy - 6), (x - 7, hy + 4), (x - 2, hy + 5), (x + 6, hy + 1), (x + 2, hy - 2)],
            "#437070",
        )
        hand = (15 + x // 2, 27 - dip // 3)
        y = 30 if i in (4, 5, 6) else 26
        poly(
            [
                (x - 1, y + 2),
                (12, y + 4),
                (24, y + 4),
                (27, y + 1),
                (25, y - 3),
                (11, y - 3),
                (6, y - 6),
            ],
            "#6a7880",
        )
        line([(17, y + 2), (25, y + 2)], "#b5f3df" if i in (4, 5, 6) else light, 2)
        line([(12, y + 8), (16, y + 2), (11, y - 7)], "#c3b994", 2)
    else:
        hand = (16 + x // 2, 27 - dip // 2)
        sx = 18 + (6 if i == 6 else 0)
        poly(
            [
                (sx - 7, 40 - dip),
                (sx + 4, 43 - dip),
                (sx + 9, 38 - dip),
                (sx + 7, 14 - dip // 2),
                (sx, 9 - dip // 2),
                (sx - 8, 16 - dip // 2),
            ],
            "#736565",
        )
        line([(sx + 4, 38 - dip), (sx + 3, 19 - dip // 2)], "#c6a582", 2)
        line([(sx - 4, 25 - dip // 2), (sx, 29 - dip // 2), (sx + 4, 25 - dip // 2)], "#e3a373", 2)
    limb([(x + w * 0.4, top), (x + w * 0.5 + 2, top - 9), hand], metal, 6 if bulky else 4)
    gx, gy = hand
    poly(
        [
            (gx - 3, gy + 1),
            (gx - 1, gy + 3),
            (gx + 2, gy + 2),
            (gx + 3, gy - 1),
            (gx, gy - 2),
            (gx - 2, gy - 2),
        ],
        light,
    )
    d.ellipse((ox + x - 6, oy - top - 4, ox + x + 3, oy - top + 3), fill=light, outline=INK)
    return im, xy(*hand)


def trail(name, i):
    im = Image.new("RGBA", SIZE)
    if not STRIKES[name].active(i):
        return im, SOLE
    d = ImageDraw.Draw(im)
    rule = STRIKES[name]
    gx, gy = rule.grips[i]
    center = (SOLE[0] + gx, SOLE[1] - gy)
    end = rule.angles[i]
    prior = rule.angles[i - 1]
    if name == "thrust":
        _, tip = rule.blade(i)
        tx, ty = SOLE[0] + tip[0], SOLE[1] - tip[1]
        for offset in (-1, 1):
            d.polygon(
                [
                    (center[0] + 9, center[1] + offset * 8),
                    (tx - 15, ty + offset * 6),
                    (tx, ty),
                    (tx - 12, ty + offset * 4),
                ],
                fill=(255, 210, 126, 180),
            )
        return im, SOLE
    heavy = name == "breaker"
    # Each taper follows the moving grip as well as the rotating weapon tip.
    # Leave air between the narrow filaments; keep the torso side of the arc clear.
    for start, stop, radius, width, color in [
        (0.02, 1, 0.98, 9 if heavy else 7, (207, 105, 52, 145)),
        (0.16, 1, 1.00, 3, (255, 202, 119, 225)),
        (0.34, 0.96, 0.84, 2, (234, 147, 71, 165)),
        (0.02, 0.37, 1.06, 1, (241, 189, 114, 156)),
        (0.50, 0.78, 1.06, 1, (255, 226, 162, 195)),
    ]:
        if heavy:
            color = (134, 204, 204, color[3]) if width > 1 else (198, 233, 225, color[3])

        def point(t, r):
            u = start + (stop - start) * t
            a = math.radians(prior + (end - prior) * u)
            px, py = rule.grips[i - 1]
            return (
                round(center[0] + (px - gx) * (1 - u) + r * math.cos(a)),
                round(center[1] - (py - gy) * (1 - u) - r * math.sin(a)),
            )

        radius *= rule.length
        d.polygon(
            [point(j / 20, radius) for j in range(21)]
            + [
                point(
                    j / 20,
                    radius
                    - width
                    * math.sin(math.pi * j / 38) ** 1.3
                    * (0.45 if j in (7, 8, 14) and width > 3 else 1),
                )
                for j in range(20, -1, -1)
            ],
            fill=color,
        )
    return im, SOLE


def generate():
    OUT.mkdir(exist_ok=True)
    rows = []
    fx = []
    for name, rule in STRIKES.items():
        rows.append((name, [strike_frame(name, i) for i in range(7)], rule.ticks))
        fx.append(("trail_" + name, [trail(name, i) for i in range(7)], rule.ticks))
    for name, spans in [("hurt", (7, 8, 8)), ("death", (6, 6, 6, 6, 7, 7, 7, 10))]:
        rows.append((name, [reaction(i, name == "death") for i in range(len(spans))], spans))
    old = json.loads((ROOT / "assets/walker/clips.json").read_text(encoding="utf-8"))
    for name, clip in old.items():
        times = [f["duration_ms"] * 0.12 for f in clip["frames"]]
        rows.append(("hammer_" + name, [heavy_move(name, i) for i in range(len(times))], times))
    save_rows("walker.png", rows, SIZE, SOLE)
    save_rows("trails.png", fx, SIZE, SOLE)
    enemies = []
    for kind, spec in TYPES.items():
        first = spec.windup // 2
        spans = (34, 34, 11, 11, first, spec.windup - first, spec.active, spec.recovery, 24, 45)
        enemies.append((kind, [foe(kind, i) for i in range(10)], spans))
    save_rows("watch.png", enemies, (120, 96), (56, 81))
    for kind in TYPES:
        for f, state in zip(
            META[kind]["frames"],
            ("idle", "idle", "walk", "walk", "warn", "warn", "active", "recover", "hurt", "dead"),
        ):
            f["state"] = state
    (OUT / "clips.json").write_text(json.dumps(META, indent=2), encoding="utf-8")


if __name__ == "__main__":
    generate()
