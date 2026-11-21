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


def reaction(i, death, heavy=False):
    amount = i if death else (2, 1, 0)[i]
    if death:
        # Buckle the leading knee, pull the arm in, then let the forearm open on the floor.
        knee = [(56,65),(59,68),(62,70),(63,72),(60,73),(56,72),(54,70),(53,69)][i]
        boot = [(54,79),(56,79),(56,79),(58,78),(55,77),(52,75),(48,73),(46,72)][i]
        wrist = [(57,52),(54,49),(49,46),(45,47),(43,51),(44,57),(46,61),(48,64)][i]
        pose = (knee,boot,(37-i//2,65+min(i,4)),(35-i//2,79),wrist,
                (1,3,6,8,9,10,11,11)[i],-2-min(i,4),-2+i)
    else:
        pose = ((55+2*amount,66+amount),(54+amount,79),(38,64+amount),(35,79),
                (55-3*amount,53-3*amount),2+amount,-2-2*amount,2-3*amount)
    body, hand = draw_frame("reaction", i, pose=pose, armed=False)
    im = at_body(body)
    hx, hy = hand[0]+32, hand[1]+22
    held = Image.new("RGBA",SIZE)
    dx,dy = ((27-3*i,2+2*i) if death else (24-3*amount,-10-6*amount))
    if heavy:
        dy -= 10
    weapon(held,(hx,hy),(hx+dx,hy+dy),heavy)
    held.alpha_composite(im)
    body_bounds = im
    im = held
    if death:
        angle = (0, 6, 16, 30, 47, 64, 79, 88)[i]
        im = im.rotate(angle, center=SOLE, resample=Image.Resampling.NEAREST)
        floor = body_bounds.rotate(angle, center=SOLE, resample=Image.Resampling.NEAREST)
        dy = SOLE[1] - floor.getbbox()[3]
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
        if filename in ("watch.png", "walker.png"):
            META[name]["trim_transparent"] = True
    sheet.save(OUT / filename)


def tide_fork(i, passing=False):
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
        (-13, 32, -22, 12, (-1, 7), (31, 4)),
    )[i]
    if passing:
        x, h, back, front = x+1, h+2, back+5, front-4
        hand = (hand[0]+2, hand[1]+2)
        tip = (tip[0]-2, tip[1]+3)
    for boot, side in ((back, -1), (front, 1)):
        lift = 4 if passing and (side==1)==(i==2) else 0
        leg = [(x + side * 3, h - 20), (boot + 4, max(7, h // 4)), (boot, 4+lift)]
        stroke(leg, INK, 8)
        stroke(leg, "#586763" if side == 1 else "#39484d", 5)
        plate([(boot-4,7+lift),(boot+2,7+lift),(boot+7,2+lift),(boot+6,lift),(boot-5,lift)], "#4b4943")
    plate([(x-9,h-7),(x+7,h-8),(x+9,h-21),(x+3,h-28),(x-3,h-24),(x-13,h-25)], "#60745c")
    stroke([(x-5,h-9),(x+3,h-19),(x-4,h-23)], "#d2b878", 2)
    plate([(x-6,h+1),(x+7,h+1),(x+8,h-7),(x+3,h-11),(x-5,h-7)], "#4a5551")
    stroke([(x+3,h-3),(x+7,h-3)], "#ffdc9a", 2)
    plate([(x-14,h),(x-7,h+5),(x-3,h+9),(x+4,h+8),(x+8,h+3),(x+13,h+1),(x+10,h-1),(x-10,h-2)], "#9c8758")
    stroke([(x-11,h),(x-2,h+3),(x+9,h+1)], "#dec58a", 1)
    # Wide split oilskin collar, hanging reeds, dark kerchief underneath the brim.
    plate([(x-13,h-3),(x-4,h-7),(x+7,h-6),(x+8,h-12),(x+1,h-13),
           (x-8,h-10),(x-15,h-14)], "#58786e")
    stroke([(x-13,h-7),(x-8,h-5),(x-2,h-8)], "#9eac87", 2)
    stroke([(x-11,h+1),(x-5,h+4),(x+3,h+5)], "#eed6a3", 2)
    for n in (0,4):
        stroke([(x-10+n,h-10),(x-15+n,h-18-i%3)], "#9f935f", 2)
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


def chain_warden(i, passing=False):
    im = Image.new("RGBA", (120, 96))
    d = ImageDraw.Draw(im)
    # Sole-relative key poses: hood, far/near boot and winch gauntlet.
    x, h, far, near, hx, hy = (
        (0,48,-8,9,13,34), (1,47,-8,9,14,33),
        (2,46,-14,13,15,32), (-1,49,-3,5,11,36),
        (-4,47,-13,11,13,53), (4,43,-15,14,13,53),
        (-7,41,-16,12,13,53), (6,35,-12,15,16,16),
        (-6,43,-13,6,5,28), (-12,32,-20,13,1,16)
    )[i]

    def pt(xy):
        return (56 + xy[0], 81 - xy[1])

    def plate(points, fill):
        d.polygon([pt(p) for p in points], fill=fill, outline=INK)

    def seam(points, fill, width=1):
        d.line([pt(p) for p in points], fill=fill, width=width)

    if passing:
        x, h, far, near, hx, hy = x+1,h+2,far+4,near-3,hx-2,hy+3
    for foot, side, color in ((far,-1,"#445466"), (near,1,"#65727a")):
        lift = 4 if passing and (side==1)==(i==2) else 0
        leg = [(x+4*side,h-23),(foot+side*3,12+lift),(foot,4+lift)]
        seam(leg,INK,10)
        seam(leg,color,6)
        plate([(foot-5,7+lift),(foot+2,7+lift),(foot+8,2+lift),(foot+7,lift),(foot-5,lift)], "#795c50")
    plate([(x-10,h-9),(x+6,h-8),(x+11,h-19),(x+7,h-30),
           (x-1,h-27),(x-9,h-31),(x-13,h-23)], "#596574")
    seam([(x-8,h-13),(x+4,h-23),(x+8,h-21)], "#cda36d", 3)
    # Two concentric bronze flanges around the dark cable drum.
    cx, cy = pt((x-12,h-12))
    d.ellipse((cx-9,cy-9,cx+8,cy+9),fill="#ae7757",outline=INK,width=2)
    d.ellipse((cx-6,cy-6,cx+5,cy+6),fill="#41444f",outline="#dfaf77")
    # Exposed cable grooves and a crank arm distinguish the reel from a second head.
    for dy in (-3,0,3):
        d.line((cx-5,cy+dy+1,cx+3,cy+dy-1),fill="#987b65",width=1)
    crank = (cx+4, cy-4) if i in (4,5,6) else (cx-5,cy+4)
    d.line([(cx,cy),crank],fill="#f0c48b",width=2)
    d.rectangle((crank[0]-1,crank[1]-1,crank[0]+1,crank[1]+1),fill="#393e49")
    plate([(x-5,h-7),(x+3,h-8),(x+7,h-17),(x+3,h-24),(x-3,h-22)], "#555361")
    seam([(x-3,h-10),(x+2,h-20)], "#bf997c",2)
    plate([(x-7,h+2),(x-3,h+7),(x+5,h+8),(x+10,h+3),(x+12,h-3),
           (x+6,h-4),(x+5,h-10),(x-5,h-8)], "#82706a")
    seam([(x-4,h+3),(x+3,h+5),(x+8,h+2)], "#cca57e", 2)
    seam([(x+2,h-1),(x+10,h-2)], INK,4)
    seam([(x+4,h-1),(x+9,h-2)], "#bcf0db",2)
    plate([(x-8,h+2),(x-5,h+9),(x+1,h+12),(x+8,h+8),(x+4,h+6),
           (x-3,h+6)], "#895d51")
    seam([(x-4,h+8),(x+1,h+10),(x+5,h+8)], "#d0a37a",2)
    arm = [(x+3,h-10),(x+9,h-19 if i != 6 else h-6),(hx,hy)]
    seam(arm,INK,8)
    seam(arm,"#ab8168",5)
    plate([(hx-4,hy+2),(hx,hy+5),(hx+4,hy+3),(hx+4,hy-2),(hx-3,hy-3)], "#acc5bd")
    if i not in (4,5,6):
        seam([(hx+2,hy-1),(hx+6,hy-10),(hx+3,hy-14),(hx-1,hy-11)], INK, 5)
        seam([(hx+2,hy-1),(hx+5,hy-10),(hx+3,hy-12)], "#d4b38a", 2)
    return im, pt((hx,hy))


def foe(kind, i, passing=False):
    if kind == "chain":
        return chain_warden(i, passing)
    if kind == "fork":
        return tide_fork(i, passing)
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
    if passing:
        lean += 2
        dip -= 2
        shift = 1
    hip = max(9, h * 0.43 - dip)
    for side, k in [(-1, -1), (1, 1)]:
        end = side * (w - 2) + shift * k
        lift = 4 if passing and (side==1)==(i==2) else 0
        knee = end + 3 if k > 0 else end - 1
        limb(
            [(side * 4, hip), (knee, 11 - dip // 4 + lift), (end, 4+lift)],
            metal if k > 0 else dark,
            8 if bulky else 6,
        )
        poly([(end-4,7+lift),(end+2,7+lift),(end+6,2+lift),(end+6,lift),(end-5,lift)], dark)
        line([(end-3,5+lift),(end+1,6+lift)], light, 1)
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
        # A slag hood falls behind the shoulder. A broken tooth profiles the helmet.
        poly([(x-12,top+5),(x-1,top+6),(x+5,top+2),(x-4,top),
              (x-9,top-7),(x-18,top-10),(x-15,top-4),(x-20,top-5)],"#853f40")
        line([(x-15,top+1),(x-10,top+3),(x-5,top+3)],"#d4906d",2)
        poly([(x-9,hy-4),(x-8,hy+4),(x-14,hy+11),(x-7,hy+9),
              (x-2,hy+4),(x+4,hy+3),(x+7,hy)],"#846b58")
        line([(x-11,hy+9),(x-7,hy+7),(x-4,hy+3)],"#dbbd91",2)
        poly([(x-2,hy-4),(x+8,hy-3),(x+12,hy-5),(x+8,hy-6),
              (x-2,hy-7)],"#bf9679")
        poly([(x+1,hy-10),(x+8,hy-9),(x+5,hy-15),(x+1,hy-16)],"#737e80")
        hand = ((24,30) if i==6 else (-1,38) if i==4 else (-6,48) if i==5
                else (12+x,24-dip//2))
        hx, hy = hand
        if i == 6:
            poly([(hx+5,hy+2),(40,34),(48,32),(50,27),(43,20),
                  (43,25),(45,28),(39,29),(hx+5,hy-1)],"#a39485")
            line([(hx - 4, hy), (45, 31), (48, 27), (44, 22)], INK, 5)
            poly([(hx+5,hy+2),(40,34),(48,32),(50,27),(43,20),
                  (43,25),(45,28),(39,29),(hx+5,hy-1)],"#a39485")
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
        # Crossbow stock, visible returning string and a rear case of three iron bolts.
        poly([(x-18,top-8),(x-15,top+8),(x-7,top+8),(x-9,top-9)],"#614f47")
        for off in (0,4,8):
            line([(x-16+off,top+5),(x-15+off,top+13+(off==4)*3)],"#a9bdb6",2)
        poly([(x-10,hy-5),(x-7,hy+1),(x+3,hy+3),(x+11,hy-3),
              (x+3,hy-4),(x-6,hy-3)],"#637f7b")
        line([(x-4,hy-1),(x+2,hy+1),(x+7,hy-2)],"#adc7ba",2)
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
        line([(10,y+9),(4 if i in (4,5) else 12,y),(10,y-7)],"#82958a",1)
        line([(4,y+4),(22,y+4)],"#c5bc97",1)
        line([(12, y + 8), (16, y + 2), (11, y - 7)], "#c3b994", 2)
    else:
        # Furnace-door spaulder has a projecting hinge and cold top bevel.
        poly([(x-26,top+2),(x-23,top+10),(x-16,top+13),(x-9,top+11),
              (x-7,top+5),(x-13,top+1),(x-20,top-3)],"#536570")
        line([(x-24,top+5),(x-21,top+9),(x-15,top+11),(x-11,top+10)],"#bcc0aa",2)
        poly([(x-9,hy-3),(x-7,hy+3),(x+6,hy+4),(x+13,hy-1),
              (x+13,hy-4),(x+5,hy-2)],"#7d7774")
        line([(x-5,hy+2),(x+4,hy+3)],"#b8aaa0",2)
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
        poly([(sx-5,37-dip),(sx+1,40-dip),(sx+4,37-dip),
              (sx+2,21-dip//2),(sx-3,16-dip//2)],"#4e6268")
        line([(sx-4,33-dip),(sx+2,34-dip)],"#b89570",2)
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


def fallen(kind, settled):
    """Two low silhouettes after losing balance. Gear falls with the near hand."""
    im = Image.new("RGBA", (120,96))
    d = ImageDraw.Draw(im)
    def pt(x,y):
        return 56+x,81-y
    def panel(points, fill, outline=INK):
        d.polygon([pt(*q) for q in points],fill=fill,outline=outline)
    def rim(points, fill, width=2):
        d.line([pt(*q) for q in points],fill=fill,width=width,joint="curve")
    h = 10 if settled else 19
    x = -17 if settled else -11
    knee = 12 if settled else 19
    shell, helm = {"hook":("#75494b","#a98368"),"rivet":("#426362","#748f8b"),
                   "ram":("#5c656b","#96938a"),"fork":("#597160","#a99a71"),
                   "chain":("#595769","#9a7c71")}[kind]
    rim([(x+5,h-5),(9,knee-4),(22,4)],INK,9)
    rim([(x+5,h-5),(9,knee-4),(22,4)],"#47535d",6)
    panel([(16,5),(22,7),(24,4),(29,2),(28,0),(16,0)],"#667580")
    panel([(x-7,h+4),(x-4,h+9),(x+5,h+8),(x+15,h-1),
           (x+13,3),(x-8,3),(x-13,h-2)],shell)
    rim([(x-6,h+4),(x,h+6),(x+8,h+2)],helm)
    panel([(x-16,h-1),(x-14,h+6),(x-8,h+7),(x-4,h+2),(x-5,h-3),
           (x-11,h-6),(x-16,h-5)],helm)
    wrist = (0,3 if settled else 7)
    rim([(x-3,h+2),(x-3,6),wrist],INK,7)
    rim([(x-3,h+2),(x-3,6),wrist],"#937b66",4)
    hx,hy=wrist
    if kind=="ram":
        panel([(-3,hy+4),(17,hy+7),(24,hy+2),(20,1),(-2,1)],"#786d64")
        rim([(1,hy+3),(17,hy+5),(21,hy+2)],"#c5a580")
    elif kind=="chain":
        sx,sy=pt(x+9,h)
        d.ellipse((sx-8,sy-7,sx+8,sy+7),fill="#966c57",outline=INK)
        d.ellipse((sx-5,sy-4,sx+5,sy+4),fill="#454754",outline="#d0a572")
        rim([(0,hy),(11,2),(18,5),(20,8)],"#b8a18b")
    elif kind=="rivet":
        panel([(-3,hy+2),(6,hy+3),(24,hy),(22,hy-2),(3,hy-1)],"#8b8777")
        rim([(10,hy+7),(13,hy),(9,1)],"#c6b593")
    elif kind=="fork":
        rim([(-13,hy+4),(33,hy)],"#9e886a",3)
        rim([(28,hy),(40,hy+4),(34,hy+1),(42,hy)],"#c7c9ab")
        rim([(x-19,h+3),(x-12,h+7),(x-6,h+8),(x-1,h+5)],"#bdab7c",3)
    else:
        rim([(0,hy),(17,hy+3),(23,hy+8),(26,hy+7),(25,hy+2)],INK,5)
        rim([(0,hy),(17,hy+3),(23,hy+7),(25,hy+6)],"#cfac8d",2)
    return im,pt(*wrist)


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
        for heavy in (False, True):
            clip = ("hammer_" if heavy else "") + name
            rows.append((clip, [reaction(i, name == "death", heavy) for i in range(len(spans))], spans))
    old = json.loads((ROOT / "assets/walker/clips.json").read_text(encoding="utf-8"))
    for name, clip in old.items():
        times = [f["duration_ms"] * 0.12 for f in clip["frames"]]
        rows.append(("hammer_" + name, [heavy_move(name, i) for i in range(len(times))], times))
    save_rows("walker.png", rows, SIZE, SOLE)
    save_rows("trails.png", fx, SIZE, SOLE)
    enemies = []
    for kind, spec in TYPES.items():
        first = spec.windup // 2
        spans = (34, 34, 6, 6, first, spec.windup - first, spec.active, spec.recovery, 24, 9, 13, 23, 5, 5)
        enemies.append((kind, [foe(kind, i) for i in range(10)] + [fallen(kind, False), fallen(kind, True),
                                foe(kind,2,True), foe(kind,3,True)], spans))
    save_rows("watch.png", enemies, (120, 96), (56, 81))
    for kind in TYPES:
        for f, state in zip(
            META[kind]["frames"],
            ("idle", "idle", "walk", "walk", "warn", "warn", "active", "recover", "hurt", "dead", "dead", "dead", "walk", "walk"),
        ):
            f["state"] = state
    (OUT / "clips.json").write_text(json.dumps(META, indent=2), encoding="utf-8")


if __name__ == "__main__":
    generate()
