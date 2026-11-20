"""Individually articulated tumbles, drawn around the pelvis then sole-aligned."""
from math import sin, cos, radians
from PIL import Image, ImageDraw

# Torso angle, head offset, leading knee, toe, wrist and trailing cloth tip.
POSES = (
    (18, (4, -15), (10, 0), (8, 13), (13, -3), (-21, 0)),
    (58, (6, -11), (13, -3), (1, 9), (12, -8), (-23, 3)),
    (97, (6, -10), (11, -5), (2, 8), (11, -9), (-16, 7)),
    (143, (4, -11), (9, -7), (-1, 8), (10, -9), (-13, 8)),
    (190, (2, -12), (10, -6), (-3, 7), (10, -8), (-14, 6)),
    (239, (3, -10), (12, -7), (-3, 5), (12, -8), (-16, 5)),
    (296, (3, -12), (13, -1), (5, 11), (14, -3), (-20, 2)),
    (344, (5, -14), (13, 1), (11, 13), (14, 0), (-22, 0)),
)


def roll_frame(i, armed=True):
    angle, head, knee, toe, wrist, cape = POSES[i]
    c, s = cos(radians(angle)), sin(radians(angle))
    canvas = Image.new("RGBA", (140, 140))
    d = ImageDraw.Draw(canvas)
    ink = "#131c29"

    def pt(p):
        x, y = p
        return round(70 + c * x - s * y), round(70 + s * x + c * y)

    def shape(points, fill, outline=ink):
        d.polygon([pt(p) for p in points], fill=fill, outline=outline)

    def patch(at, offsets, fill, edge=ink):
        shape([(at[0] + x, at[1] + y) for x, y in offsets], fill, edge)

    def limb(points, fill, thick):
        joints = [pt(p) for p in points]
        d.line(joints, fill=ink, width=thick + 2, joint="curve")
        d.line(joints, fill=fill, width=thick, joint="curve")

    # Rear foot, overlapping front thigh and boot, segmented knee cap.
    limb([(-3, 0), (-8, 5), (-11 + i % 3, 9)], "#424e63", 6)
    shape([(-12, 6), (-7, 7), (-6, 11), (-13, 12), (-16, 10)], "#435364")
    shape([(-6, -10), (2, -12), (6, -7), (5, 2), (-3, 5), (-8, 1)], "#556477")
    limb([(1, 0), knee, toe], "#596377", 6)
    patch(toe, [(-4, -4), (1, -5), (3, -2), (8, 0), (7, 2), (-4, 2)], "#506475")
    patch(knee, [(-4, -1), (0, -4), (4, -2), (4, 1), (1, 4), (-3, 2)], "#bf9059")
    shape([(-6, -12), (1, -14), (3, -8), (-3, -5), cape, (-12, -6)], "#4d758a")
    shape([(-5, -12), (-2, -11), (-7, -7), cape], "#89afbc", None)
    hx, hy = head
    patch(
        head,
        [(-7, -3), (-5, -7), (0, -9), (5, -7), (8, -3), (6, 3), (2, 7), (-4, 5), (-7, 1)],
        "#81939b",
    )
    patch(head, [(-4, -6), (0, -8), (4, -7), (0, -6)], "#c0cfcd", None)
    patch(head, [(-1, -2), (8, -4), (9, -2), (5, 1), (0, 2)], ink)
    patch(head, [(2, -1), (7, -3), (6, -1), (2, 0)], "#ffe2a3", None)
    patch(head, [(-4, -4), (5, -6), (10, -4), (4, -3)], "#b18c5d")
    patch(head, [(1, -1), (8, -3), (7, -1), (2, 0)], "#ffcf7c", None)
    patch(head, [(0, 2), (7, -1), (5, 4), (2, 7), (-1, 6)], "#c3c8be")
    # Sabre lies along the forearm and clear of the rolled body.
    if armed:
        patch(
            wrist,
            [(2, 1), (-4, 0), (-16, 2), (-23, 0), (-19, 4), (-12, 5), (-3, 3), (2, 4)],
            "#d99c51",
        )
    else:
        limb([wrist, (-10, 4)], "#7c7771", 3)
        patch((-10, 4), [(-5, -4), (4, -4), (6, 0), (3, 5), (-5, 5), (-7, 1)], "#87999c")
    limb([(-3, -8), (3, 0), wrist], "#aa8056", 5)
    patch((-3, -8), [(-5, 0), (-3, -4), (2, -5), (5, -1), (4, 2), (-2, 3)], "#ba8b56")
    patch((-3, -8), [(-3, -3), (1, -4), (3, -2), (-2, -1)], "#eed09a", None)
    patch(wrist, [(-2, -2), (1, -3), (3, 0), (1, 3), (-2, 2)], "#736652")
    box = canvas.getbbox()
    dx = 48 - 70
    dy = 80 - box[3]
    out = Image.new("RGBA", (96, 96))
    out.paste(canvas, (dx, dy))
    wx, wy = pt(wrist)
    return out, (wx + dx, wy + dy)
