"""Paint the braced body, incandescent blade and torn flame ribbons as two layers."""
import math
import random
from PIL import Image, ImageDraw
from draw_combat import SOLE, at_body, weapon
from draw_walker import draw_frame
from game.flame import BLADE, DURATIONS, READY_TICKS, RELEASE_FRAME, ray

FX_SIZE = (256, 232)
FX_SOLE = (86, 199)
# Torso lean, hip drop, stance width. Bracing loads the rear leg before the forward cut.
STANCE = (
    (0, 2, 2),
    (-3, 4, 3),
    (-6, 7, 5),
    (-7, 8, 6),
    (-6, 7, 6),
    (-7, 8, 6),
    (1, 3, 7),
    (7, 1, 9),
    (10, 5, 11),
    (9, 8, 10),
    (7, 8, 9),
    (5, 6, 7),
    (3, 3, 4),
    (1, 1, 2),
)


def body(i):
    gx, gy, angle, _ = BLADE[i]
    lean, drop, spread = STANCE[i]
    wrist = (48 + gx, 80 - gy)
    pose = (
        (54 + spread, 66 + drop // 2),
        (54 + spread, 79),
        (42 - spread // 2, 64 + drop // 2),
        (37 - spread, 79),
        wrist,
        drop,
        lean,
        -spread,
    )
    silhouette, _ = draw_frame("firecut", i, pose=pose, armed=False)
    im = Image.new("RGBA", (160, 128))
    x, y = SOLE[0] + gx, SOLE[1] - gy
    a = math.radians(angle)
    weapon(im, (x, y), (round(x + 32 * math.cos(a)), round(y - 32 * math.sin(a))), False)
    im.alpha_composite(at_body(silhouette))
    return im, (x, y)


def blade_fire(i, *, ignition=False):
    im = Image.new("RGBA", FX_SIZE)
    d = ImageDraw.Draw(im)
    gx, gy, degrees, length = BLADE[i]
    x, y = FX_SOLE[0] + gx, FX_SOLE[1] - gy
    angle = math.radians(degrees)

    def along(u, v):
        return round(x + u * math.cos(angle) - v * math.sin(angle)), round(
            y - u * math.sin(angle) - v * math.cos(angle)
        )

    rng = random.Random(933 + i)

    def poly(pts, col):
        d.polygon([along(u, v) for u, v in pts], fill=col)

    if i >= RELEASE_FRAME:
        sweep(d, i, rng)
    # The metal edge remains visible inside a flame envelope with a broken leading fringe.
    width = (2, 3, 4, 11, 10, 11, 11, 10, 9, 8, 6, 4, 2, 1)[i]
    for factor, rgba in (
        (1.65, (250, 103, 42, 42)),
        (1, (211, 61, 32, 244)),
        (0.64, (255, 150, 46, 255)),
        (0.30, (255, 234, 144, 255)),
    ):
        h = width * factor
        poly(
            [
                (6, 0),
                (18, h * 0.55),
                (0.6 * length, h),
                (0.79 * length, h * 0.61),
                (length, 0),
                (0.75 * length, -h * 0.5),
                (0.47 * length, -h * 0.73),
                (17, -h * 0.29),
            ],
            rgba,
        )
    if 3 <= i <= 10:
        for k in range(4):
            u = length * (0.29 + 0.13 * k)
            h = width * (1.1 + 0.4 * ((i + k) % 3))
            poly([(u, 2), (u + 8, 5), (u + 17, h), (u + 12, h * 0.25), (u + 21, 3)], "#ff9d39")
        for _ in range(3 if i < RELEASE_FRAME else 7):
            u, v = rng.uniform(18, length), rng.choice((-1, 1)) * rng.uniform(width + 4, width + 14)
            px, py = along(u, v)
            d.line((px, py, px + 2, py - 2), fill=rng.choice(("#ffc766", "#ed7939")))
    if 3 <= i < RELEASE_FRAME:
        # On full charge, two bands turn around the hot blade. The far half disappears
        # behind the metal, leaving a readable silhouette on a held three-frame loop.
        for band in range(2):
            path = []
            for j in range(27):
                turn = (j / 26 + (i - 3) / 3 + band / 2) * math.tau
                u = length * (0.24 + 0.66 * j / 26)
                v = (10 + 4 * math.sin(math.pi * j / 26)) * math.sin(turn)
                if math.cos(turn) < 0 and abs(v) < width * 0.92:
                    path = []
                    continue
                path.append(along(u, v))
                if len(path) >= 2:
                    d.line(path[-2:], fill="#ffc86b" if band else "#ed843e", width=2)
    if ignition:
        # A hot seam shoots up the edge, opens into two broken rings and cools.
        phase = i - 3
        u = length * (0.82, 0.89, 0.96)[phase]
        radius = (16, 23, 27)[phase]
        color = ("#fff2bd", "#ffd484", "#db935b")[phase]
        for side in (-1, 1):
            points = [along(u - radius * 0.47, side * radius * 0.45),
                      along(u - radius * 0.14, side * radius),
                      along(u + radius * 0.24, side * radius * 0.81)]
            d.line(points, fill="#ac653e", width=4 if phase < 2 else 2)
            d.line(points, fill=color, width=2 if phase < 2 else 1)
        if phase == 0:
            poly([(u - 19, 0), (u, -3), (length, 0), (u, 3)], "#fff5c5")
            for side in (-1, 1):
                poly([(u - 3, side * 3), (u + 1, side * 16), (u + 3, side * 4)], "#fff5c5")
    return im, (x, y)


def sweep(d, i, rng):
    # Trace the preceding blade tips. Separate filaments and curling tongues leave
    # holes inside the wake, so the contact edge reads through the red-orange body.
    end = min(i, 9)
    start = max(6, end - 2)
    path = []
    for frame in range(start, end + 1):
        for k in range(13):
            (gx, gy), (tx, ty) = ray(frame, k / 12)
            if path and k == 0:
                continue
            path.append((gx, gy, tx - gx, ty - gy))
    fade = 1 if i <= 9 else (0.67, 0.38, 0.18, 0.06)[i - 10]
    trim = max(0, i - 9) * len(path) // 8
    path = path[trim:]

    def pt(j, r, up=0):
        gx, gy, dx, dy = path[j]
        return (round(FX_SOLE[0] + gx + dx * r), round(FX_SOLE[1] - gy - dy * r - up))

    n = len(path)
    for inner, outer, col in (
        (0.73, 1.048, (171, 53, 45, 105)),
        (0.79, 1.015, (196, 66, 35, 220)),
        (0.81, 0.995, (252, 128, 42, 245)),
        (0.92, 0.98, (255, 206, 90, 255)),
    ):
        edge = []
        inside = []
        for j in range(n):
            t = j / (n - 1)
            width = (outer - inner) * math.sin(math.pi * t / 2) ** 0.85
            width *= 0.78 + 0.22 * math.sin(t * 14 + 0.6 * i)
            wav = (0.025 * math.sin(19 * t + i) + 0.018 * math.sin(41 * t)) * (1 - t)
            edge.append(pt(j, outer + wav))
            inside.append(pt(j, outer - width + wav))
        d.polygon(edge + inside[::-1], fill=(*col[:3], round(col[3] * fade)))
    # Long tongues fold back along the sweep. Hollow centres interrupt the bright band.
    for fraction, height, span in ((0.24, 17, 4), (0.53, 8, 2), (0.76, 22, 5), (0.91, 6, 2)):
        j = min(n - 2, max(1, round(fraction * (n - 1))))
        tail, neck = max(0, j - span), max(0, j - span // 2)
        curl = height + max(0, i - 9) * 2
        points = [
            pt(tail, 0.94),
            pt(j, 0.90),
            pt(j + 1, 0.98),
            pt(j, 1.025, curl // 2),
            pt(neck, 1.06, curl),
            pt(tail, 1.055, curl + 2),
            pt(neck, 1.025, curl // 2),
            pt(neck, 0.995, curl // 4),
        ]
        d.polygon(points, fill=(249, 131, 47, round(225 * fade)))
        d.line(
            [pt(j, 0.96), pt(j, 1.015, curl // 3), pt(neck, 1.04, curl - 3)],
            fill=(255, 216, 113, round(230 * fade)),
            width=2,
        )
        d.polygon(
            [pt(tail, 0.92), pt(neck, 0.952), pt(j, 0.946), pt(neck, 0.965)], fill=(0, 0, 0, 0)
        )
    for j in range(2, n - 2, 7):
        d.line(
            [pt(k, 0.975) for k in range(j, min(j + 5, n))],
            fill=(255, 236, 161, round(245 * fade)),
            width=2,
        )
    # Open the wake *inside* the orange band, tapering each hole at both ends.
    # The leading edge at the blade tip stays continuous as the cut turns downward.
    for lo, hi in ((0.15, 0.52), (0.57, 0.96)):
        first, last = round(lo*(n-1)), round(hi*(n-1))
        outer, inner = [], []
        for j in range(first, last+1):
            taper = math.sin(math.pi * (j-first) / max(1, last-first))
            lip = 0.943 + 0.014 * math.sin(12*j/(n-1) + i)
            outer.append(pt(j, lip))
            inner.append(pt(j, lip - taper * (0.12 if i < 10 else 0.16)))
        d.polygon(outer + inner[::-1], fill=(0,0,0,0))
    for radius in (0.68, 1.06):
        for j in range(0, n - 3, 9):
            d.line(
                [pt(k, radius) for k in range(j, min(n, j + 5))],
                fill=(255, 194, 78, round(196 * fade)),
                width=1,
            )
    for j in range(1, n, 2):
        px, py = pt(j, rng.uniform(0.64, 1.14), rng.randrange(4, 18))
        d.line((px, py, px + 2, py - 3), fill=(255, 177, 75, round(220 * fade)))


def impact(i):
    im = Image.new("RGBA", (72, 64))
    d = ImageDraw.Draw(im)
    x, y = 28, 34
    # A compressed contact flash splits into a rim and forward-flying slag.
    for length, dy in ((26, -21), (27, -6), (18, 16), (-8, -14), (6, -25)):
        k = (0.54, 0.77, 1, 1.17)[i]
        tip = (x + round(length * k), y + round(dy * k))
        base = (x + round(length * 0.19 * i), y + round(dy * 0.19 * i))
        d.polygon(
            [base, (base[0] + 4, base[1] - 3), tip, (base[0] + 3, base[1] + 2)],
            fill=("#ffdc90", "#ffb253", "#f89542", "#d57549")[i],
        )
    r = 6 + 6 * i
    d.arc(
        (x - r, y - r, x + r, y + r),
        250,
        411,
        fill=("#fff9cf", "#ffd993", "#f49e59", "#c97449")[i],
        width=3 if i < 2 else 1,
    )
    if i == 0:
        d.polygon(
            [
                (x - 7, y),
                (x - 2, y - 2),
                (x, y - 11),
                (x + 3, y - 3),
                (x + 9, y),
                (x + 3, y + 2),
                (x, y + 8),
                (x - 2, y + 2),
            ],
            fill="#fff8db",
        )
    elif i == 1:
        d.line([(x+1,y-4),(x+5,y-2),(x+7,y+1)], fill="#ffe29b", width=2)
    return im, (x, y)


def bake_flame(bake):
    events = {3: ["ignite"], 6: ["release", "active_start"], 10: ["active_end"]}
    bake("firecut", (160, 128), SOLE, [body(i) for i in range(len(BLADE))], DURATIONS, events)
    bake(
        "firelight", FX_SIZE, FX_SOLE, [blade_fire(i) for i in range(len(BLADE))], DURATIONS,
        {6: ["release", "active_start"], 10: ["active_end"]}
    )
    bake("fire-ignite", FX_SIZE, FX_SOLE, [blade_fire(i, ignition=True) for i in range(3, 6)],
         READY_TICKS, {0: ["ignite"]})
    bake(
        "fire-impact", (72, 64), (28, 34), [impact(i) for i in range(4)], (3, 3, 3, 3), {0: ["hit"]}
    )
