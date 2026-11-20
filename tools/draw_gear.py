"""Forge three inspectable inserts and their salvage case on a 32-pixel grid."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "assets" / "foundry" / "inserts.png"
INK, IRON, STEEL = "#182732", "#415561", "#8caca8"
COPPER, GOLD, LIGHT = "#ac6c49", "#e4a85d", "#ffdf9a"
SEA, FOAM = "#408779", "#ade0c5"


def atlas():
    sheet = Image.new("RGBA", (128, 32))
    for index in range(4):
        icon = Image.new("RGBA", (32, 32))
        d = ImageDraw.Draw(icon)
        if index == 0:
            d.polygon(
                [
                    (4, 23),
                    (7, 15),
                    (13, 13),
                    (16, 7),
                    (20, 10),
                    (27, 3),
                    (25, 14),
                    (19, 17),
                    (19, 21),
                    (9, 28),
                ],
                fill=COPPER,
                outline=INK,
                width=2,
            )
            d.line([(7, 22), (13, 17), (17, 16), (23, 10)], fill=GOLD, width=3)
            d.line([(17, 11), (20, 12), (26, 6)], fill=LIGHT)
            d.polygon([(4, 22), (9, 25), (7, 29), (2, 26)], fill=IRON, outline=INK)
            d.point((7, 24), fill=LIGHT)
        elif index == 1:
            d.ellipse((3, 3, 28, 28), fill=IRON, outline=INK, width=2)
            d.ellipse((6, 6, 25, 25), fill=SEA, outline=GOLD, width=2)
            for points in [
                [(15, 8), (20, 9), (19, 14), (16, 15)],
                [(23, 17), (21, 22), (16, 20), (16, 17)],
                [(13, 24), (8, 21), (11, 16), (14, 17)],
                [(8, 14), (10, 9), (14, 11), (14, 14)],
            ]:
                d.polygon(points, fill=FOAM)
            d.ellipse((12, 12, 19, 19), fill=COPPER, outline=INK)
            d.rectangle((14, 14, 16, 16), fill=LIGHT)
        elif index == 2:
            d.polygon(
                [(5, 6), (15, 3), (26, 7), (25, 18), (20, 24), (15, 29), (6, 21)],
                fill=IRON,
                outline=INK,
                width=2,
            )
            d.polygon([(8, 8), (15, 6), (22, 9), (21, 16), (15, 23), (9, 18)], fill=COPPER)
            d.line([(8, 9), (15, 7), (22, 10)], fill=LIGHT, width=2)
            for y in (13, 17, 21):
                d.line([(9, y - 2), (15, y + 1), (21, y - 2)], fill=GOLD)
            d.line((15, 8, 15, 23), fill=STEEL)
        else:
            d.polygon(
                [(1, 14), (7, 8), (24, 8), (30, 13), (29, 26), (24, 29), (4, 27)],
                fill=IRON,
                outline=INK,
                width=2,
            )
            d.polygon([(3, 14), (8, 10), (23, 10), (27, 14), (22, 17), (4, 16)], fill=STEEL)
            d.line([(3, 17), (23, 19), (29, 15)], fill=INK, width=2)
            for x in (7, 20):
                d.line([(x + 3, 10), (x, 15), (x, 25)], fill=COPPER, width=3)
                d.line((x + 1, 17, x + 1, 23), fill=GOLD)
            d.rectangle((12, 17, 16, 21), fill=INK)
            d.rectangle((13, 18, 15, 19), fill=FOAM)
        sheet.paste(icon, (index * 32, 0))
    return sheet


if __name__ == "__main__":
    atlas().save(OUT)
