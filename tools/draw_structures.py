"""Draw the playable sluice works from the same faces used by movement."""
from pathlib import Path
import random
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.terrain import FLOOR, SURFACES, WORLD_WIDTH, GROUND_Y


def engine_annex():
    """Continue the distant pump house eastwards along the viaduct."""
    im = Image.new("RGBA", (256, 360))
    d = ImageDraw.Draw(im)
    d.polygon([(0, 151), (25, 151), (43, 161), (54, 161), (54, 225), (0, 229)], fill="#3a4c59")
    for x in (6, 26):
        d.rounded_rectangle((x, 158, x + 11, 187), 5, fill="#2c424f")
        d.rectangle((x + 2, 175, x + 7, 181), fill="#a17d63")
    for x in (77, 99):
        d.polygon([(x, 111), (x + 4, 111), (x + 9, 225), (x + 5, 225)], fill="#435d67")
    d.line([(72, 131), (108, 161), (81, 185), (109, 210)], fill="#516b72", width=3)
    d.rounded_rectangle((66, 91, 109, 137), 7, fill="#4c606d", outline="#435562", width=2)
    d.polygon([(63, 96), (71, 85), (93, 83), (111, 91), (114, 96)], fill="#435766")
    for y in (102, 120, 131):
        d.line((66, y, 109, y), fill="#70807f")
    d.line([(107, 113), (120, 113), (127, 124), (127, 174), (156, 174)], fill="#4d616a", width=5)
    for x in range(139, 226, 29):
        d.rectangle((x, 167, x + 18, 220), fill="#4d626a")
        d.polygon([(x - 3, 167), (x + 6, 155), (x + 14, 156), (x + 20, 167)], fill="#546873")
    arches = Image.new("RGBA", im.size)
    b = ImageDraw.Draw(arches)
    b.rectangle((0, 190, 255, 252), fill="#415b65")
    for x in range(-36, 256, 79):
        b.rounded_rectangle((x, 198, x + 59, 272), 28, fill=(0, 0, 0, 0))
        b.arc((x - 2, 196, x + 61, 254), 180, 360, fill="#6b7e7e", width=2)
    b.rectangle((0, 188, 255, 191), fill="#738481")
    b.line((0, 181, 255, 181), fill="#526971")
    for x in range(0, 256, 16):
        b.line((x, 181, x, 187), fill="#455d65")
    im.alpha_composite(arches)
    im.save(ROOT / "assets/quay/annex.png")


def structures(surfaces):
    im = Image.new("RGBA", (WORLD_WIDTH, 360))
    d = ImageDraw.Draw(im)
    rng = random.Random(773)
    ink, steel, light = "#283b48", "#50656c", "#8c9a92"
    for s in surfaces:
        if s == FLOOR:
            continue
        x, end = s.left, s.right - 1
        y, bottom = 360 - s.top, 359 - s.bottom
        if s.one_way:
            # Cables and split timbers distinguish hanging, pass-through decking.
            beam_y = y - 60
            d.rectangle((x + 1, beam_y, end - 6, beam_y + 3), fill="#52656a")
            d.line((x + 1, beam_y, end - 6, beam_y), fill="#93a099")
            mast = x + 18
            d.rectangle((mast, beam_y - 3, mast + 3, 359 - GROUND_Y), fill="#566a70")
            d.line((mast + 2, beam_y + 26, mast + 31, beam_y + 3), fill="#71817c", width=2)
            d.line((mast - 1, beam_y + 9, mast + 5, beam_y + 9), fill="#9a9781")
            for px in (x + 8, end - 8):
                d.line((px - 6, y - 58, px, y - 1), fill="#50666b")
                d.line((px - 6, y - 58, px - 1, y - 58), fill=light)
                d.rectangle((px - 2, y - 4, px + 2, y - 1), fill=ink, outline="#a49e83")
            d.rectangle((x, y, end, bottom - 2), fill="#454c4f", outline=ink)
            for xx in range(x + 2, end - 1, 11):
                d.rectangle(
                    (xx, y + 1, min(xx + 8, end - 1), y + 4),
                    fill=rng.choice(("#998977", "#a99a82", "#847e70")),
                )
            d.line((x + 1, y, end - 1, y), fill="#d1bf97")
            for xx in range(x + 7, end - 9, 20):
                d.line((xx, y + 5, xx + 4, bottom, xx + 12, y + 5), fill="#71827c")
        elif s.bottom == GROUND_Y:
            d.rectangle((x, y, end, bottom), fill=ink)
            for row, yy in enumerate(range(y, bottom, 12)):
                for xx in range(x - (row % 2) * 14, end, 29):
                    left, right = max(x + 1, xx + 1), min(end - 1, xx + 27)
                    if right <= left:
                        continue
                    d.rectangle(
                        (left, yy + 1, right, min(yy + 10, bottom)),
                        fill=rng.choice(("#43555c", "#526268", "#4c5c65")),
                    )
                    d.line((left, yy + 1, right, yy + 1), fill="#74807d")
            d.rectangle((x, y, end, y + 3), fill="#8a8d80")
            d.line((x, y, end, y), fill="#c2b89b")
            # Bronze floodgate drain, recessed slats and a segmented tide scale.
            mid = (x + end) // 2
            d.rounded_rectangle(
                (mid - 16, y + 11, mid + 15, min(bottom, y + 37)), 4, fill=ink, outline="#89918a"
            )
            for xx in range(mid - 12, mid + 13, 5):
                d.line((xx, y + 15, xx, min(bottom - 1, y + 33)), fill="#68797b", width=2)
            for yy in range(y + 8, bottom - 2, 7):
                d.line((end - 7, yy, end - 4, yy), fill="#bdab86")
        else:
            # Cantilevered maintenance beam. Rear braces leave the low passage readable.
            for px in (x + 9, end - 9):
                d.rectangle((px, bottom, px + 2, 359 - GROUND_Y), fill="#596b70")
                d.line((px, bottom + 12, px + 8, bottom + 1), fill="#66777a")
            d.rectangle((x, y, end, bottom), fill="#394c58", outline=ink)
            d.rectangle((x, y, end, y + 2), fill=light)
            for xx in range(x + 4, end - 6, 12):
                d.line((xx, y + 4, xx + 7, bottom - 3), fill="#74807d", width=2)
                d.point((xx, y + 4), fill="#c1af85")
            d.line((x, bottom - 1, end, bottom - 1), fill="#ba9165")
    return im


if __name__ == "__main__":
    structures(SURFACES).save(ROOT / "assets/quay/structures.png")
    engine_annex()
