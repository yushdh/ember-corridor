"""Paint the animated tideworks at gameplay resolution. No external source images."""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.harbour import SKY, WHEEL, BAY, WORKS
from draw_quay import sky

OUT = ROOT / "assets/quay"
TAU = math.tau
sin, cos = math.sin, math.cos


def curtain(t):
    layer = Image.new("RGBA", (640, SKY.height))
    d = ImageDraw.Draw(layer)
    rng = random.Random(794)
    for _ in range(122):
        x, y, phase = rng.randrange(640), rng.randrange(2, 113), rng.random() * TAU
        alpha = round(83 + 64 * sin(t + phase))
        d.point((x, y), fill=(208, 221, 224, alpha))
        if alpha > 142 and y < 78 and x % 4 == 0:
            d.line((x - 1, y, x + 1, y), fill=(174, 211, 222, alpha))
            d.line((x, y - 2, x, y + 2), fill=(195, 219, 219, alpha))
    # Light pools along the lower folds. Fine vertical rays fan away from this edge.
    for band, (base, shade) in enumerate(((52, (162, 146, 213)), (74, (104, 209, 197)))):
        ribbon = Image.new("RGBA", layer.size)
        rays = ImageDraw.Draw(ribbon)
        for x in range(640):
            a = x / 103 + 0.36 * sin(t + x / 178) + band * 0.93 - 2.9
            foot = round(base + 23 * sin(a) + 11 * sin(2.2 * a + 0.32 * cos(t)) + 4 * sin(4 * a))
            veil = 0.72 + 0.24 * sin(x / 57 + 0.38 * cos(t) + band)
            length = round(13 + 15 * (1 + sin(1.8 * a)) + 5 * cos(x / 9 + t))
            ray = 0.79 + 0.12 * sin(x / 3.6 + cos(t)) + 0.09 * sin(x / 1.8 + sin(t))
            for h in range(length):
                strength = (1 - h / length) ** 1.65 * veil * ray
                alpha = round((156 if band else 95) * strength)
                if alpha:
                    rays.point((x, foot - h), fill=(*shade, alpha))
            if veil > 0.52:
                rays.point((x, foot), fill=(158, 223, 204, round(137 * veil)))
        layer.alpha_composite(ribbon)
    return sky(layer, t).crop((0, 0, SKY.width, SKY.height))


def wheel(t):
    im = Image.new("RGBA", (160, 160))
    d = ImageDraw.Draw(im)

    def polar(a, r):
        return round(80 + r * cos(a)), round(80 + r * sin(a))

    def ring(r, width, color):
        d.ellipse((80 - r, 80 - r, 80 + r, 80 + r), outline=color, width=width)

    ring(65, 6, "#3b515d")
    ring(62, 2, "#869694")
    ring(36, 3, "#566c74")
    for j in range(12):
        a = (j * TAU + t) / 12

        def p(r, offset=0):
            return polar(a + offset, r)

        d.polygon([p(10, -0.22), p(59, -0.082), p(60, 0.012), p(12, 0.16)], fill="#465e6b")
        d.line([p(13, -0.15), p(58, -0.075)], fill="#9a9481", width=2)
        d.line([p(31, 0.02), p(58, 0.38)], fill="#687d80", width=2)
        d.polygon(
            [p(61, -0.10), p(72, -0.14), p(77, -0.03), p(72, 0.095), p(63, 0.105)],
            fill="#3f5461",
            outline="#374b58",
        )
        d.polygon(
            [p(68, -0.10), p(73, -0.096), p(76, -0.026), p(71, 0.07), p(67, 0.072)],
            fill="#8d8174" if sin(a) < 0.4 else "#758687",
        )
        d.line([p(72, -0.12), p(76, -0.025), p(71, 0.079)], fill="#a59b86")
        d.point(p(62), fill="#c1af88")
        # Only paddles crossing the moonlit sector catch a wet edge. Each facet opens then narrows.
        glint = max(0, cos(a + 2.18)) ** 18
        if glint > 0.18:
            d.line([p(74, -0.077), p(76, -0.028), p(73, 0.055 * glint)],
                   fill=(147, 177, 172, round(65 + 120 * glint)), width=2)
    for r, color in ((16, "#394f60"), (13, "#9b8971"), (10, "#566975"), (5, "#a99a7a")):
        d.ellipse((80 - r, 80 - r, 80 + r, 80 + r), fill=color)
    for k in range(6):
        x, y = polar((2 * k * TAU + t) / 12, 11)
        d.point((x, y), fill="#c7b698")
    # Buckets shed chains of water into the bay on the ascending side.
    for k in range(10):
        age = (t / TAU + k * 0.31) % 1
        x = round(18 + k % 4 * 3 - 4 * age)
        y = round(113 + (k % 4) * 3 + 36 * age**1.5)
        d.line(
            (x, y, x, y + 1 + round(age * 2)), fill=(143, 182, 186, round(143 * sin(math.pi * age)))
        )
    return im


def moonwater(t):
    im = Image.new("RGBA", (BAY.width, BAY.height))
    d = ImageDraw.Draw(im)
    rng = random.Random(492)
    for center, color, rows in (
        (146, (186, 200, 185), 155),
        (235, (199, 149, 109), 42),
        (42, (121, 170, 175), 50),
    ):
        for _ in range(rows):
            y = rng.randrange(1, 50)
            side = rng.uniform(-1, 1)
            phase = rng.uniform(0, TAU)
            x = round(center + side * (10 + y * 0.83) + 3 * sin(t + phase))
            length = 1 + round((2 + y * 0.15) * (0.5 + 0.5 * cos(t + phase)))
            strength = (1 - abs(side) * 0.76) * (0.5 + 0.5 * sin(t + phase))
            d.line((x, y, x + length, y), fill=(*color, round(144 * strength)))
    return im


def flag(d, t):
    def cloth(u, v):
        wave = (3.3 * sin(u * 9 - t) + 2 * cos(u * 4 + t)) * u
        return round(8 + 55 * u - 2 * u * (1 + sin(t))), round(
            20 + wave + 3 * u + v * (15 - 1.9 * u)
        )

    edge = [k / 20 for k in range(21)]
    seam = [cloth(u, 0) for u in edge]
    for i in range(20):
        a, b = edge[i : i + 2]
        # A V-shaped cut in the trailing edge.
        depth = 1 if a < 0.70 else max(0.15, 1 - (a - 0.70) * 2.8)
        dark = round(13 * sin(a * 12 - t))
        d.polygon(
            [cloth(a, 0), cloth(b, 0), cloth(b, depth), cloth(a, depth)],
            fill=(146 + dark, 80 + dark, 70 + dark),
        )
    d.line(seam, fill="#cfa277")
    d.line(
        [cloth(u, 1) for u in edge[:14]] + [cloth(1, 0.15), cloth(0.90, 0.95), cloth(0.68, 1)],
        fill="#aa745e",
    )
    d.line(
        [
            cloth(0.23, 0.5),
            cloth(0.34, 0.14),
            cloth(0.46, 0.5),
            cloth(0.34, 0.84),
            cloth(0.23, 0.5),
        ],
        fill="#ebc892",
        width=2,
    )
    d.line([cloth(0.30, 0.50), cloth(0.56, 0.50)], fill="#e0b788")
    d.line((6, 17, 9, 17), fill="#b7b49d")


def gauge(d, t):
    cx, cy = 48, 40
    d.ellipse((29, 21, 67, 59), fill="#243f50")
    for x in range(-17, 18):
        depth = int(math.sqrt(17**2 - x * x))
        surface = max(-depth, round(3 + 3 * sin(t) + 1.6 * sin(x / 5 + t)))
        if surface < depth:
            d.line((cx + x, cy + surface, cx + x, cy + depth), fill="#3c767c")
            d.point((cx + x, cy + surface), fill="#82b9af")
    for k in range(7):
        a = 3.56 + k * 0.37
        d.line(
            (
                cx + round(18 * cos(a)),
                cy + round(18 * sin(a)),
                cx + round(15 * cos(a)),
                cy + round(15 * sin(a)),
            ),
            fill="#c2ac82",
        )
    a = 4.77 + 0.73 * sin(t)
    d.line((cx, cy, cx + round(13 * cos(a)), cy + round(13 * sin(a))), fill="#edcc8d", width=2)
    d.ellipse((46, 38, 50, 42), fill="#bda483")
    d.arc((30, 21, 66, 57), 207, 247, fill="#a9d1ca", width=2)
    for k in range(4):
        age = (t / TAU + k / 4) % 1
        x = 38 + k * 5 + round(sin(t + k))
        y = round(52 - 6 * age)
        d.point((x, y), fill="#91b8af")


def sluice(d, t):
    for j in range(4):
        x = 23 + j * 13
        width = (7, 10, 6, 8)[j]
        left = []
        right = []
        for h in range(0, 62, 2):
            s = h / 62
            bend = 2 * sin(s * 9 - t + j) * s
            drift = (j - 1.5) * 3 * s * s
            u = round(x + drift + bend)
            left.append((u, 8 + h))
            right.append((u + round(width * (1 - 0.48 * s)), 8 + h))
        d.polygon(left + right[::-1], fill=(80, 143, 153, 155))
        d.line(left, fill=(138, 191, 192, 190))
        for k in range(5):
            age = (t / TAU + k / 5 + j * 0.13) % 1
            idx = round(age**1.35 * (len(left) - 3))
            xx, yy = left[idx]
            d.line((xx + 2, yy, xx + 2, yy + round(1 + 5 * age)), fill=(173, 206, 200, 175))
        for k in range(4):
            age = (t / TAU + k / 4 + j * 0.17) % 1
            xx = round(x + 3 + (k - 1.5) * 7 * age)
            yy = round(68 - 19 * age * (1 - age))
            d.point((xx, yy), fill="#a0c5c1")
        d.arc((x - 8, 67, x + 11, 71), 190, 350, fill="#8eb4af")


def bell_lamp(d, t):
    # Sea-glass lamp in a bronze cage, with moths following separate orbits.
    x, y = 48, 44
    for r in range(22, 4, -2):
        d.ellipse((x - r, y - r, x + r, y + r), fill=(119, 201, 193, round((23 - r) * 1.6)))
    d.line((48, 25, 48, 33), fill="#9c9279")
    d.polygon(
        [(48, 32), (55, 39), (53, 50), (48, 55), (42, 50), (41, 39)],
        fill="#58666b",
        outline="#9f947a",
    )
    d.polygon([(48, 35), (52, 40), (50, 48), (48, 51), (45, 47), (44, 40)], fill="#90bfb9")
    # Swinging light refracts through one face of the glass onto the lower cage.
    wick = round(2 * sin(t))
    d.polygon([(46, 42), (48 + wick, 37), (50, 43), (47 + wick, 47)], fill="#bed7bf")
    d.line([(45 + wick, 49), (48 + wick, 51), (50 + wick, 49)], fill="#92b6ac")
    for k in range(3):
        spread = round((4 + k * 3) * (0.78 + 0.22 * cos(t + k)))
        yy = 57 + 3 * k
        d.line((x + wick - spread, yy, x + wick + spread, yy),
               fill=(130, 183, 169, 63 - 14 * k))
    for k in range(4):
        a = t + k * 1.56
        xx = round(x + (17 + k * 3) * cos(a))
        yy = round(y - 4 + (6 + k) * sin(2 * a + k))
        wing = 1 + round((1 + sin(4 * t + k)) * 0.7)
        d.line((xx - wing, yy - 1, xx, yy + 1, xx + wing, yy - 2), fill=(202, 195, 155, 185))


def casting_lamp(d, t):
    x, y = 48, 44
    for r in range(30, 4, -2):
        d.ellipse(
            (x - r, y - round(r * 0.86), x + r, y + round(r * 0.86)),
            fill=(226, 138, 74, round((31 - r) * 1.8)),
        )
    d.line((48, 19, 48, 32), fill="#ad8a69", width=2)
    d.polygon(
        [(37, 37), (42, 32), (54, 32), (59, 37), (56, 50), (50, 56), (45, 56), (40, 50)],
        fill="#613f42",
        outline="#ab8267",
    )
    for k in range(3):
        xx = 43 + k * 5
        height = round(6 + 3 * sin(t + k) + 2 * cos(2 * t + k))
        d.polygon(
            [
                (xx - 2, 49),
                (xx - 2, 44),
                (xx + round(2 * sin(t + k)), 48 - height),
                (xx + 2, 42),
                (xx + 2, 49),
            ],
            fill=("#bd7150", "#e2a762", "#cf8955")[k],
        )
    d.line((39, 38, 57, 38), fill="#c29e77", width=2)
    d.line((41, 51, 55, 51), fill="#ba946e", width=2)
    for k in range(6):
        age = (t / TAU + k / 6) % 1
        xx = round(x + (k - 2) * 2 + 6 * sin(age * 5 + k))
        yy = round(36 - 23 * age)
        d.point((xx, yy), fill=(224, 168, 111, round(140 * sin(math.pi * age))))


def atlas(spec, painters):
    rows = math.ceil(spec.count / spec.columns)
    sheet = Image.new("RGBA", (spec.width * spec.columns, spec.height * rows * len(painters)))
    for row, paint in enumerate(painters):
        for i in range(spec.count):
            angle = i * TAU / spec.count
            if spec == WORKS:
                cell = Image.new("RGBA", (spec.width, spec.height))
                paint(ImageDraw.Draw(cell), angle)
            else:
                cell = paint(angle)
            x, y, *_ = spec.box(i)
            sheet.paste(cell, (x, y + row * rows * spec.height))
    sheet.save(OUT / (spec.name + ".png"))


if __name__ == "__main__":
    atlas(SKY, [curtain])
    atlas(WHEEL, [wheel])
    atlas(BAY, [moonwater])
    atlas(WORKS, [flag, gauge, sluice, bell_lamp, casting_lamp])
