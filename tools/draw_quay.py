"""Original 640 x 360 foundry panorama. All measurements are logical pixels."""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "assets" / "quay"
W, H = 640, 360


def sky():
    rng = random.Random(417)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    stops = (
        (0, (29, 37, 57)),
        (60, (57, 65, 82)),
        (116, (96, 107, 114)),
        (152, (151, 143, 129)),
        (209, (106, 137, 140)),
        (360, (75, 104, 115)),
    )
    for (lo, a), (hi, b) in zip(stops, stops[1:]):
        for y in range(lo, hi):
            d.line(
                (0, y, W, y),
                fill=tuple(round(v + (w - v) * (y - lo) / (hi - lo)) for v, w in zip(a, b)),
            )
    # Moon behind long wind-sheared clouds.
    veil = Image.new("RGBA", im.size)
    halo = ImageDraw.Draw(veil)
    for r, alpha in ((51, 5), (44, 8), (36, 13), (30, 20)):
        halo.ellipse((302 - r, 66 - r, 302 + r, 66 + r), fill=(226, 185, 139, alpha))
    im.paste(veil, (0, 0), veil)
    d.ellipse((275, 39, 328, 92), fill="#bcb9aa")
    d.polygon(
        [(281, 60), (286, 52), (293, 51), (297, 54), (292, 59), (289, 64), (283, 65)],
        fill="#afb1a7",
    )
    d.polygon([(304, 76), (310, 69), (319, 70), (322, 73), (318, 79), (312, 82)], fill="#b2b4a7")
    for _ in range(98):
        x, y = rng.randrange(-70, 640), rng.randrange(16, 138)
        v = im.getpixel((0, y))
        color = tuple(min(255, n + 5) for n in v)
        width = rng.randrange(18, 74)
        d.polygon(
            [
                (x, y + 3),
                (x + 9, y + 2),
                (x + 15, y),
                (x + width, y),
                (x + width + 9, y + 2),
                (x + width // 2, y + 3),
            ],
            fill=color,
        )
    # A distant furnace dome breaks up the repeated rectangular roofs.
    d.ellipse((178, 94, 241, 147), fill="#798c91")
    d.rectangle((177, 119, 242, 177), fill="#798c91")
    d.rectangle((203, 88, 216, 99), fill="#788990")
    d.polygon([(201, 88), (209, 78), (219, 88)], fill="#77858b")
    d.line((209, 78, 209, 71), fill="#839195")
    for x in (186, 196, 208, 221, 231):
        d.line((209, 96, x, 118), fill="#8c9c9a")
    for depth, (base, body, lit) in enumerate(
        [(193, "#829698", "#95a6a0"), (214, "#637e87", "#79918f")]
    ):
        x = -7
        while x < W:
            w = rng.randrange(12, 48)
            y = rng.randrange(112, 171) + depth * 10
            d.rectangle((x, y, x + w, base), fill=body)
            d.polygon(
                [(x - 3, y), (x + w // 4, y - 7), (x + w - 6, y - 7), (x + w + 4, y)], fill=body
            )
            if rng.random() < 0.58:
                ax = x + w // 2
                top = y - rng.randrange(16, 49)
                d.polygon([(ax - 4, y), (ax - 2, top), (ax + 2, top), (ax + 4, y)], fill=body)
                d.line((ax - 3, top, ax + 2, top), fill=lit)
            for wx in range(x + 4, x + w - 1, 8):
                d.line((wx, y + 6, wx, y + 10), fill=lit)
            x += w + rng.randrange(1, 8)
    # Mist at the waterline and broken horizontal reflections.
    d.rectangle((0, 210, W, 289), fill="#476573")
    for i in range(275):
        x, y = rng.randrange(W), rng.randrange(212, 289)
        d.line(
            (x, y, x + rng.randrange(2, 19), y), fill=rng.choice(("#506e79", "#5c7880", "#415e6c"))
        )
    return im


def midground():
    rng = random.Random(49)
    im = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(im)

    def pipe(points, width, main, edge):
        d.line(points, fill=edge, width=width + 3, joint="curve")
        d.line(points, fill=main, width=width, joint="curve")

    # Ruined tide engine with an exposed spoked wheel.
    cx, cy, r = 492, 166, 69
    for i in range(32):
        a = i * math.tau / 32

        def radial(dist, offset):
            return (
                round(cx + dist * math.cos(a + offset)),
                round(cy + dist * math.sin(a + offset)),
            )

        d.polygon(
            [
                radial(r - 3, -0.066),
                radial(r + 5, -0.047),
                radial(r + 5, 0.047),
                radial(r - 3, 0.066),
            ],
            fill="#394f59",
        )
    for width, inset, color in [(8, 0, "#364953"), (2, 1, "#58666c"), (3, 9, "#465761")]:
        d.ellipse(
            (cx - r + inset, cy - r + inset, cx + r - inset, cy + r - inset),
            outline=color,
            width=width,
        )
    for i in range(12):
        a = i * math.tau / 12 + 0.16
        u, v = round(cx + math.cos(a) * 61), round(cy + math.sin(a) * 61)
        pipe([(cx, cy), (u, v)], 4, "#52616a", "#41525e")
    d.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill="#485860", outline="#636e71", width=2)
    d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill="#78817b")
    # Stone pumping house with a flared stack, ridges and arched furnace mouths.
    for offset, height in [(565, 35), (603, 57)]:
        x = offset
        d.polygon([(x - 13, 160), (x - 5, height), (x + 3, height), (x + 12, 160)], fill="#434e60")
        d.polygon([(x - 6, height), (x - 4, height), (x - 8, 153), (x - 12, 153)], fill="#717477")
        for y in range(height, 141, 21):
            d.rectangle(
                (x - 7 - (y - height) // 32, y, x + 5 + (y - height) // 34, y + 2), fill="#354c59"
            )
        d.rectangle((x - 8, height - 2, x + 6, height + 2), fill="#67747a")
    d.polygon(
        [(535, 145), (549, 130), (607, 130), (635, 150), (640, 151), (640, 239), (535, 239)],
        fill="#3a4c59",
    )
    for x in range(546, 637, 20):
        d.rounded_rectangle((x, 156, x + 12, 186), radius=6, fill="#293f4e")
        d.rectangle((x + 2, 167, x + 9, 182), fill="#814f46")
        d.rectangle((x + 3, 172, x + 8, 182), fill="#bd7955")
        d.rectangle((x + 3, 178, x + 8, 182), fill="#e2a167")
        d.line((x + 6, 165, x + 6, 183), fill="#45606a")
    for y in (143, 149):
        d.line((545, y, 605, y), fill="#596971")
    pipe([(589, 154), (589, 146), (616, 146), (623, 153), (623, 190)], 3, "#776e66", "#344a56")
    for x in (550, 558, 566):
        d.line((x, 134, x + 3, 131), fill="#74807d")
    # Cast-iron viaduct. Punch actual transparent archways.
    bridge = Image.new("RGBA", (W, H))
    b = ImageDraw.Draw(bridge)
    b.rectangle((0, 190, 640, 252), fill="#415b65")
    for x in range(-28, 640, 79):
        b.rounded_rectangle((x, 198, x + 59, 272), radius=28, fill=(0, 0, 0, 0))
        b.arc((x - 2, 196, x + 61, 254), 180, 360, fill="#6b7e7e", width=2)
    b.rectangle((0, 188, 640, 191), fill="#738481")
    for x in range(0, 640, 16):
        b.line((x, 181, x, 187), fill="#455d65")
    b.line((0, 181, W, 181), fill="#526971")
    im.alpha_composite(bridge)
    # Old hoist on the left; a hanging ladle, cable and chipped pennant.
    d = ImageDraw.Draw(im)
    dark, edge = "#304452", "#61727a"
    for x, y, w in [(32, 80, 12), (87, 136, 10)]:
        d.rectangle((x, y, x + w, 246), fill=dark)
        for yy in range(y + 8, 242, 20):
            d.line((x, yy, x + w, yy - 6), fill=edge)
    pipe([(13, 140), (58, 79), (173, 92)], 6, "#51616b", dark)
    pipe([(31, 144), (67, 97), (164, 98)], 4, "#526771", dark)
    for x in range(67, 156, 15):
        d.line((x, 84 + (x - 67) // 12, x + 8, 97, x + 15, 85 + (x - 67) // 12), fill=dark, width=2)
    d.line((162, 96, 162, 148), fill=dark)
    d.arc((158, 144, 166, 153), 0, 270, fill=dark, width=2)
    d.line((162, 151, 151, 163, 173, 163, 162, 151), fill=dark)
    d.polygon([(148, 162), (176, 162), (172, 173), (163, 178), (153, 174)], fill=dark)
    d.line((149, 163, 174, 163), fill="#81918b")
    d.line((152, 166, 159, 173, 169, 171), fill="#766c66", width=2)
    d.line((157, 164, 168, 164), fill="#af8b66")
    for x, y in [(34, 100), (34, 118), (89, 154), (89, 175)]:
        d.rectangle((x - 3, y, x + 10, y + 2), fill="#54656a")
        d.point((x, y + 1), fill="#999686")
    for x in [32, 43]:
        d.line((x, 81, 55, 62), fill=dark, width=2)
    d.polygon([(54, 61), (74, 64), (82, 63), (75, 68), (62, 67), (54, 68)], fill="#936e60")
    for ax, ay, bx, by, sag in [
        (0, 64, 55, 62, 13),
        (53, 79, 234, 132, 22),
        (364, 127, 564, 104, 20),
    ]:
        pts = [
            (ax + (bx - ax) * i / 30, ay + (by - ay) * i / 30 + sag * math.sin(math.pi * i / 30))
            for i in range(31)
        ]
        d.line(pts, fill="#50616b")
    # Brackish stains follow arch joints. Ripples break up the submerged piers.
    for x in range(41, 640, 79):
        for j in range(8):
            u, v = x + rng.randrange(-6, 7), rng.randrange(195, 202)
            d.line((u, v, u, v + rng.randrange(3, 15)), fill=rng.choice(("#485f65", "#506a6b")))
        for j in range(5):
            u = x + rng.randrange(-11, 9)
            v = 251 + rng.randrange(-1, 4)
            d.line((u, v, u + rng.randrange(5, 17), v), fill="#648389")
    return im


def deck():
    rng = random.Random(927)
    im = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(im)
    # Survey lamp and enamel tide gauge stand behind the walking plane.
    for radius, alpha in ((27, 10), (20, 16), (14, 27), (9, 39)):
        d.ellipse(
            (81 - radius, 223 - radius, 81 + radius, 223 + radius), fill=(231, 166, 92, alpha)
        )
    d.polygon(
        [
            (62, 265),
            (65, 261),
            (66, 211),
            (69, 207),
            (80, 207),
            (83, 210),
            (83, 214),
            (80, 214),
            (79, 211),
            (70, 211),
            (70, 261),
            (74, 265),
        ],
        fill="#344751",
    )
    d.line((67, 214, 67, 260), fill="#74817b")
    for y in (220, 242, 258):
        d.rectangle((64, y, 71, y + 2), fill="#49575b")
    d.line((81, 211, 81, 216), fill="#39464f")
    d.polygon(
        [(76, 219), (79, 215), (83, 215), (87, 219), (85, 228), (81, 231), (77, 228)],
        fill="#34434c",
    )
    d.rectangle((78, 220, 84, 226), fill="#cba677")
    d.rectangle((80, 220, 82, 225), fill="#e8c896")
    d.line((81, 219, 81, 227), fill="#89785e")
    d.line((78, 228, 84, 228), fill="#a99d83")
    d.rectangle((564, 237, 570, 265), fill="#41535a", outline="#647776")
    for y in range(240, 263, 4):
        d.line((565, y, 568 if y % 8 == 0 else 566, y), fill="#a99f88")
    d.rectangle((0, 266, W, 359), fill="#192c37")
    # Quayside walk: worn limestone coping, courses of wet ashlar.
    d.rectangle((0, 267, W, 274), fill="#626b6e")
    x = -10
    while x < W:
        w = rng.randrange(20, 51)
        d.rectangle((x, 266, x + w - 2, 267), fill=rng.choice(("#a0a199", "#a6a08c", "#969c92")))
        d.line((x + w - 2, 268, x + w - 5, 272), fill="#334653")
        d.line((x + 4, 271, x + 12, 271), fill="#747c7a")
        x += w
    for row in range(4):
        x = -rng.randrange(42)
        top = 275 + row * 17
        while x < W:
            w = rng.randrange(23, 59)
            c = rng.choice(("#394955", "#3b4b56", "#42515a", "#354752")) if row < 2 else "#2c414c"
            d.polygon(
                [
                    (x + 1, top + 1),
                    (x + w - 4, top),
                    (x + w - 1, top + 3),
                    (x + w - 2, top + 13),
                    (x + 4, top + 16),
                    (x, top + 12),
                ],
                fill=c,
            )
            d.line((x + 3, top + 1, x + w - 6, top), fill="#516068" if row < 2 else "#394c55")
            if rng.random() < 0.65:
                d.line((x + 7, top + 4, x + 16, top + 4), fill="#47595f")
            if row == 0 and rng.random() < 0.48:
                for j in range(rng.randrange(4, 10)):
                    u = x + rng.randrange(1, w - 3)
                    v = top + rng.randrange(0, 3)
                    d.line(
                        (u, v, u - 1, v + rng.randrange(1, 6)),
                        fill=rng.choice(("#64736d", "#506660")),
                    )
            x += w
    pipe_y = 318
    d.rectangle((0, pipe_y, W, pipe_y + 9), fill="#223741")
    d.line((0, pipe_y + 1, W, pipe_y + 1), fill="#536261", width=2)
    for x in range(14, 640, 53):
        d.rectangle((x, pipe_y - 2, x + 5, pipe_y + 10), fill="#293a44", outline="#4d5a59")
    d.rectangle((0, 335, W, 359), fill="#213e49")
    for j in range(140):
        x, y = rng.randrange(640), rng.randrange(336, 360)
        d.line(
            (x, y, x + rng.randrange(3, 22), y), fill=rng.choice(("#2a4b56", "#35565e", "#294651"))
        )
    return im


def foreground():
    im = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(im)
    for x, y in [(8, 264), (627, 264)]:
        d.polygon(
            [
                (x - 6, y),
                (x - 4, y - 4),
                (x - 3, y - 17),
                (x - 5, y - 19),
                (x - 3, y - 22),
                (x + 5, y - 22),
                (x + 7, y - 19),
                (x + 4, y - 16),
                (x + 5, y - 4),
                (x + 8, y),
            ],
            fill="#263640",
        )
        d.line((x - 3, y - 21, x + 4, y - 21), fill="#988d77")
    for x, y in [(0, 279), (634, 280)]:
        for i in range(8):
            d.line((x + i, y, x - 5 + i, y + 6, x - 8 + i, y + 17 + i % 3), fill="#536c64")
    return im


def atmosphere():
    """Three fixed-origin loops: rising exhaust, furnace tongues, spreading foam."""
    sheet = Image.new("RGBA", (48 * 12, 40 * 3))
    for i in range(12):
        smoke, fire, foam = [Image.new("RGBA", (48, 40)) for _ in range(3)]
        d = ImageDraw.Draw(smoke)
        for phase in (8, 4, 0):
            age = (i + phase) % 12
            x, y = 14 + age + age * age // 14, 38 - age * 3
            x += (phase - 4) * age // 17
            r = 2 + age // 2 + phase * age // 47
            alpha = min(116, (age + 1) * 34, (12 - age) * 19)
            d.polygon(
                [
                    (x - r - 2, y),
                    (x - r, y - 2),
                    (x - 1, y - r),
                    (x + r, y - r + 1),
                    (x + r + 2, y - 2),
                    (x + r, y + 1),
                    (x + 1, y + 2),
                ],
                fill=(109, 122, 129, alpha),
            )
            d.line((x - r, y, x - 1, y + 1, x + 2, y), fill=(164, 162, 155, alpha // 2))
        d = ImageDraw.Draw(fire)
        for dx, phase in ((-2, 0), (2, 5)):
            age = (i + phase) % 12
            h = (4, 6, 8, 7, 10, 9, 7, 5, 4, 6, 5, 3)[age]
            x = 24 + dx
            d.polygon(
                [(x - 1, 22), (x - 1, 19), (x + (age // 3) % 2, 22 - h), (x + 1, 19), (x + 1, 22)],
                fill="#e6a05d",
            )
            d.line((x, 21, x, 20 - h // 3), fill="#f0c481")
        if i % 6 > 1:
            d.point((22 + i // 6, 15 - i % 6), fill="#ce915f")
        d = ImageDraw.Draw(foam)
        for phase, cx, cy in ((0, 17, 17), (6, 31, 22)):
            age = (i + phase) % 12
            radius = 2 + age
            color = (134, 168, 163, min(135, (age + 1) * 37, (12 - age) * 22))
            d.line((cx - radius, cy, cx - radius + age // 2 + 1, cy), fill=color)
            d.line((cx + 1, cy + 1, cx + radius, cy + 1), fill=color)
            if 2 < age < 9:
                d.line((cx - 2, cy - 1, cx + 2, cy - 1), fill=(190, 182, 150, 60))
        for row, cell in enumerate((smoke, fire, foam)):
            sheet.paste(cell, (48 * i, 40 * row))
    return sheet


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, paint in [("sky", sky), ("engine", midground), ("quay", deck), ("posts", foreground)]:
        paint().save(OUT / f"{name}.png")
    atmosphere().save(OUT / "atmosphere.png")
