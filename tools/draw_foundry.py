"""Draw five room overlays, the articulated bellkeeper and the seal cast at native scale."""
import json
import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.foundry import ROOMS, CAST_TICKS
from draw_bellkeeper import SIZE as BELL_SIZE, SOLE as BELL_SOLE, keeper
from draw_structures import structures
from draw_walker import draw_frame
from draw_flame import bake_flame

OUT = ROOT / "assets/foundry"
INK = "#202d39"
BRONZE = "#9f7659"
GOLD = "#dfac73"
TEAL = "#83c8bb"


def bell(d, x, y, r, body, edge):
    """A flared bronze shell with shoulder bands, lip, crown and clapper."""
    p = lambda u, v: (round(x + r * u), round(y + r * v))
    d.ellipse((*p(-0.16, 0.60), *p(0.16, 0.97)), fill=edge, outline=INK)
    d.polygon(
        [
            p(-0.98, 0.64),
            p(-0.72, 0.31),
            p(-0.50, -0.43),
            p(-0.30, -0.69),
            p(-0.13, -0.75),
            p(0.16, -0.75),
            p(0.42, -0.60),
            p(0.56, -0.33),
            p(0.73, 0.32),
            p(0.98, 0.64),
            p(0.91, 0.76),
            p(-0.90, 0.76),
        ],
        fill=body,
        outline=INK,
    )
    for v, w in ((-0.40, 0.49), (0.33, 0.72), (0.57, 0.89)):
        d.line([p(-w, v), p(0, v + 0.07), p(w, v)], fill=edge, width=max(1, r // 18))
    d.line([p(-0.45, -0.26), p(-0.53, 0.11)], fill=edge, width=max(1, r // 20))
    if r >= 23:
        # Broad cast facets, salt streaks and a stamped tide-height scale.
        shade = tuple(max(0, c - 13) for c in bytes.fromhex(body[1:]))
        d.polygon([p(0.21, -0.55), p(0.42, -0.40), p(0.55, 0.25), p(0.29, 0.31)], fill=shade)
        for n in range(3):
            u = -0.22 + n * 0.22
            d.line(
                [
                    p(u - 0.085, -0.12),
                    p(u, -0.23),
                    p(u + 0.08, -0.12),
                    p(u, 0.03),
                    p(u - 0.085, -0.12),
                ],
                fill=edge,
            )
        for n in range(7):
            u = -0.69 + n * 0.23
            d.ellipse((*p(u - 0.014, 0.47), *p(u + 0.018, 0.50)), fill=edge)
        d.line([p(-0.87, 0.66), p(-0.28, 0.70), p(0.27, 0.71)], fill=edge, width=max(1, r // 35))
    d.arc((*p(-0.23, -1.07), *p(0.24, -0.56)), 180, 360, fill=edge, width=max(1, r // 10))


def room_image(i, room):
    im = Image.new("RGBA", (1280, 360))
    d = ImageDraw.Draw(im)
    if i:
        # Far stone vaults frame open views of the saltworks.
        fill = ("#404d59", "#394f58", "#343e4f", "#413e48")[i - 1]
        spandrel = Image.new("RGBA", (1280, 266), fill)
        arch = ImageDraw.Draw(spandrel)
        stone = tuple(bytes.fromhex(fill[1:]))
        for y in range(266):
            shade = round(5 * math.cos(y / 27) - 10 * y / 266)
            arch.line((0, y, 1280, y), fill=tuple(c + shade for c in stone))
        for row in range(0, 266, 21):
            for joint in range(-41 + row % 2 * 35, 1280, 72):
                arch.line((joint, row, joint + 69, row), fill=tuple(c - 5 for c in stone))
                arch.line((joint, row, joint, row + 19), fill=tuple(c - 7 for c in stone))
        for x in range(-65, 1280, 183 if i != 4 else 224):
            width = 145 if i != 4 else 178
            arch.rounded_rectangle(
                (x, 68 + i * 3, x + width, 369), radius=width // 2, fill=(0, 0, 0, 0)
            )
            arch.arc(
                (x - 4, 63 + i * 3, x + width + 4, 63 + i * 3 + width),
                180,
                360,
                fill="#667071",
                width=3,
            )
            arch.rectangle((x - 11, 142, x - 2, 264), fill="#475761")
            # A fanlight of sea glass framed by individual copper-tipped arch stones.
            r = width / 2
            cx, cy = x + r, 68 + i * 3 + r
            def polar(radius, degrees):
                a = math.radians(degrees)
                return round(cx + radius * math.cos(a)), round(cy + radius * math.sin(a))

            for n in range(15):
                a = 180 + 12 * n
                arch.polygon([polar(r + 2, a), polar(r + 9, a + 0.7),
                              polar(r + 9, a + 11.3), polar(r + 2, a + 12)],
                             fill=("#646e70", "#54646a", "#5d686a")[n % 3], outline="#43535b")
                arch.line((polar(r + 8, a + 2), polar(r + 8, a + 8)), fill="#978777")
            for n in range(12):
                a = 180 + 15 * n
                pane = [(63, 133, 139, 162), (82, 124, 155, 155), (112, 135, 145, 137),
                        (151, 128, 104, 152)][(n + i) % 4]
                arch.polygon([polar(r - 2, a), polar(r - 2, a + 15),
                              polar(r - 15, a + 15), polar(r - 21, a + 7), polar(r - 15, a)],
                             fill=pane, outline="#54676d")
            arch.line((cx, cy - r - 9, cx - 4, cy - r - 2, cx, cy - r + 7,
                       cx + 4, cy - r - 2, cx, cy - r - 9), fill="#b49d77", width=2)
            # A tide-height rose carved into the pier above the springing line.
            px, py = x - 18, 85
            for radius, color in ((15, "#495963"), (12, "#938474"), (9, "#536c72")):
                arch.ellipse((px-radius, py-radius, px+radius, py+radius), outline=color)
            arch.polygon([(px, py-11), (px+4, py), (px, py+11), (px-4, py)], fill="#839997")
            arch.line((px, py+16, px, 167), fill="#707779")
        im.alpha_composite(spandrel)
        for y in (26, 33, 50):
            d.line((0, y, 1280, y), fill="#626665", width=2)
        for x in range(18, 1280, 26):
            d.rectangle((x, 30, x + 2, 32), fill="#898071")
    if i == 0:
        for x in (171, 592, 996):
            d.line((x, 260, x, 125), fill="#4a5b5f", width=4)
            d.line((x - 7, 150, x + 8, 150), fill="#87877c")
    elif i == 1:
        for x in (195, 638, 1042):
            d.rounded_rectangle(
                (x - 38, 113, x + 38, 218), 14, fill="#42565e", outline="#30444d", width=4
            )
            d.ellipse((x - 24, 123, x + 23, 168), fill="#304651", outline="#89918a", width=3)
            d.arc((x - 17, 130, x + 16, 160), 197, 341, fill="#c3af83", width=2)
            d.line((x + 38, 188, x + 64, 188, x + 70, 195, x + 70, 249), fill="#69736e", width=6)
            for k in range(3):
                d.line((x - 28, 180 + k * 7, x + 26, 180 + k * 7), fill="#617675", width=2)
    elif i == 2:
        for x in (183, 470, 736, 1028):
            d.rectangle((x - 35, 71, x + 35, 192), fill="#334953", outline="#64736f", width=3)
            for y in range(83, 187, 13):
                d.line((x - 29, y, x + 29, y - 2), fill="#6a7773", width=4)
            for a in (-42, 42):
                d.line((x + a, 53, x + a, 250), fill="#596967", width=5)
            d.line((x - 56, 194, x + 57, 194), fill="#9c8d70", width=3)
    elif i == 3:
        for x, h in ((194, 129), (598, 96), (908, 152), (1124, 111)):
            for k in (-10, 10):
                d.line((x + k, 0, x + k, h - 24), fill="#344853", width=3)
                for y in range(8, h - 24, 9):
                    d.point((x + k + 1, y), fill="#989385")
            bell(d, x, h, 23, "#576568", "#998b70")
    else:
        for x, r in ((277, 41), (524, 54), (807, 81), (1070, 45)):
            d.line((x, 0, x, 73), fill="#887257", width=6)
            d.line((x - 12, 20, x + 12, 20), fill="#a48b68", width=3)
            bell(d, x, 109, r, "#484e54", "#6b7071")
            d.line((x - 3, 109 + r, x + 4, 244), fill="#594f4a", width=2)
    return im


def room_front(room):
    im = structures(room.surfaces)
    d = ImageDraw.Draw(im)
    for x, y in [room.door]:
        base = 360 - y
        d.rounded_rectangle(
            (x - 27, base - 83, x + 27, base + 1),
            radius=21,
            fill="#364751",
            outline="#958873",
            width=3,
        )
        d.rounded_rectangle(
            (x - 21, base - 76, x + 21, base + 4),
            radius=18,
            fill="#1d303d",
            outline="#596b6e",
            width=2,
        )
        for k in (-15, -7, 0, 7, 15):
            d.line((x + k, base - 51, x + k, base - 4), fill="#3e5259", width=2)
        d.polygon(
            [(x - 8, base - 58), (x, base - 68), (x + 8, base - 58), (x, base - 48)],
            fill="#c09a63",
            outline=INK,
        )
        for side in (-1, 1):
            d.rectangle(
                (x + side * 29 - 2, base - 40, x + side * 29 + 2, base - 31), fill="#e2b57a"
            )
    if room.valve:
        x, y = room.valve
        y = 360 - y
        d.rectangle((x - 6, y - 21, x + 5, y - 1), fill="#50636b", outline=INK)
        d.ellipse((x - 13, y - 39, x + 13, y - 13), fill="#364955", outline=GOLD, width=3)
        for a in range(0, 360, 60):
            d.line(
                (
                    x,
                    y - 26,
                    x + int(11 * math.cos(math.radians(a))),
                    y - 26 + int(11 * math.sin(math.radians(a))),
                ),
                fill=BRONZE,
                width=2,
            )
    return im


def effects():
    sheet = Image.new("RGBA", (144 * 6, 112 * 4))
    for i in range(6):
        for row in range(4):
            im = Image.new("RGBA", (144, 112))
            d = ImageDraw.Draw(im)
            if row == 0:
                for side in (-1, 1):
                    h = side * (8 + i)
                    d.polygon(
                        [
                            (2, 15),
                            (37, 15 + h),
                            (64, 15 + h),
                            (95, 15 + h // 2),
                            (142, 15),
                            (80, 14 + h // 2),
                            (43, 13 + h),
                        ],
                        fill="#7fddc7",
                    )
                    d.line([(22, 15), (54, 16 + h // 2), (102, 15), (136, 15)], fill="#d3f4db")
                d.line((131, 7 + i % 3, 142, 15, 130, 23 - i % 3), fill="#e5f6cb", width=2)
            elif row in (1, 2):
                width = (111, 134)[row - 1]
                for k in (0, 1, 2):
                    y = 27 - k * 7
                    d.polygon(
                        [
                            (1, y),
                            (width // 4, y - 2 - i),
                            (width * 3 // 4, y - 8 + i // 2),
                            (width - 1, y - 4),
                            (width - 7, y),
                            (width // 3, y + 1),
                        ],
                        fill=(243, 167 + k * 15, 105, 185),
                    )
                # The rim travels out along the floor while the full danger strip stays visible.
                nose = min(width-4, 16 + i * (width-20)//5)
                d.polygon([(nose-15,26),(nose-9,20),(nose-5,21),(nose,12),
                           (nose-1,22),(nose+3,25),(nose-4,28)], fill=(225,191,151,215))
                d.line([(nose-10,24),(nose-5,22),(nose,15)], fill="#f8dba5",width=2)
                for offset, rise in ((11,8),(21,4)):
                    x = max(1,nose-offset)
                    d.polygon([(x,26),(x+2,26-rise),(x+5,25-rise),(x+4,26)],
                              fill=(139,156,151,170))
            else:
                for j in range(5):
                    x = 5 + j * 8
                    bend = (i * 2 + j) % 7 - 3
                    d.polygon(
                        [
                            (x - 3, 111),
                            (x + 4, 111),
                            (x + 4 + bend, 53),
                            (x + 1, 3 + j % 3 * 8),
                            (x - 3 + bend, 48),
                        ],
                        fill=(239, 169 + 8 * j, 108, 210),
                    )
                    d.line((x, 106, x + 1 + bend, 65), fill="#ffe6a7")
                # Split jets leave sightlines through the middle of the eruption.
                for j in (1,3):
                    x=5+j*8
                    d.polygon([(x-1,104),(x-1,70),(x+1,37+i*3),(x+2,81)],
                              fill=(100,130,128,70))
            sheet.paste(im, (144 * i, 112 * row))
    return sheet


def generate_rooms():
    from game.routes import ALTERNATES

    fronts = Image.new("RGBA", (1280, 360 * len(ROOMS)))
    for i, room in enumerate(ROOMS):
        room_image(i, room).save(OUT / f"room-{i+1}.png")
        fronts.paste(room_front(room), (0, i * 360))
    fronts.save(OUT / "room-fronts.png")
    alternate_fronts = Image.new("RGBA", (1280, 360 * len(ALTERNATES)))
    for i, template in enumerate(ALTERNATES):
        alternate_fronts.paste(room_front(template.room), (0, i * 360))
    alternate_fronts.save(OUT / "route-fronts.png")


def generate():
    OUT.mkdir(exist_ok=True)
    effects().save(OUT / "effects.png")
    generate_rooms()
    clips = {}

    def bake(name, size, anchor, cells, ticks, events):
        sheet = Image.new("RGBA", (size[0] * len(cells), size[1]))
        frames = []
        for i, ((im, wrist), span) in enumerate(zip(cells, ticks)):
            x = i * size[0]
            sheet.paste(im, (x, 0))
            frames.append(
                dict(
                    region=[x, 0, *size],
                    anchor=anchor,
                    weapon_socket=wrist,
                    ticks=span,
                    events=events.get(i, []),
                )
            )
        sheet.save(OUT / (name + ".png"))
        clips[name] = dict(sheet=name + ".png", frames=frames)

    for name, tide in (("bell", False), ("bell_tide", True)):
        sweep = 64 if tide else 82
        vent = 90 if tide else 108
        recovery = 67 if tide else 89
        bake(name, BELL_SIZE, BELL_SOLE, [keeper(i, tide) for i in range(19)],
             (15,15,15,15,sweep//2,sweep//2-8,9,recovery,vent//2,vent//2,18,
              recovery,58,12,12,21,8,9,22),
             {4:["sweep_warn"], 6:["sweep"], 8:["vent_warn"], 10:["vent"],
              12:["phase"], 13:["death"]})
        clips[name]["trim_transparent"] = True
    cells = []
    for i, (hand, bob, lean) in enumerate(
        [
            ((52, 49), 3, -2),
            ((46, 39), 6, -5),
            ((69, 40), 1, 4),
            ((73, 44), 4, 6),
            ((65, 47), 5, 4),
            ((56, 52), 1, 1),
        ]
    ):
        pose = ((55 + lean, 65 + bob), (58 + lean, 79), (41, 65), (36, 79), hand, bob, lean, -i)
        im, wrist = draw_frame("seal", i, pose=pose, armed=False)
        d = ImageDraw.Draw(im)
        x, y = wrist
        d.polygon([(x - 4, y), (x, y - 5), (x + 5, y), (x, y + 4)], fill=TEAL, outline=INK)
        cells.append((im, wrist))
    bake("cast", (96, 96), (48, 80), cells, CAST_TICKS, {2: ["release"]})
    bake_flame(bake)
    (OUT / "clips.json").write_text(json.dumps(clips, indent=2), encoding="utf-8")


if __name__ == "__main__":
    generate()
