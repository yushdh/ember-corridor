"""Pixel cut-outs drawn in a right-facing, sole-anchored coordinate system."""
from pathlib import Path
import json
import math

from PIL import Image, ImageDraw
from roll_pose import roll_frame

ASSETS = Path(__file__).resolve().parents[1] / "assets"
INK = "#111925"
BRASS = "#bd8050"
GOLD = "#f3c781"
IRON = "#394959"
LIGHT = "#a7c1c8"
CLOTH = "#397388"
ICE = "#8dbfc8"

# Each stride poses the forward and trailing knee, ankle, wrist and cape tip.
# Coordinates describe the near leg first. The far leg is half a cycle ahead.
STRIDE = [
    ((54, 65), (66, 78), (48, 58), 0, -1),
    ((60, 67), (61, 79), (51, 59), 2, 1),
    ((55, 66), (45, 79), (55, 52), 1, 0),
    ((45, 67), (38, 76), (60, 52), -1, -2),
    ((41, 63), (31, 72), (61, 48), -2, -3),
    ((41, 64), (28, 62), (57, 46), 0, -1),
    ((62, 55), (39, 60), (50, 48), 1, 1),
    ((62, 59), (61, 70), (45, 52), -1, 0),
]


# Knee/sole pairs, wrist, torso drop, forward lean and mantle deflection.
AIR_POSES = {
    "jump": [
        ((56, 65), (53, 77), (40, 63), (32, 72), (61, 45), 2, 3, 0),
        ((64, 55), (56, 66), (39, 62), (26, 73), (62, 39), -1, 4, 4),
        ((63, 52), (55, 64), (40, 64), (29, 73), (59, 41), -2, 3, 6),
    ],
    "fall": [
        ((57, 58), (56, 70), (41, 61), (35, 69), (59, 47), -1, 1, -3),
        ((55, 62), (57, 74), (39, 63), (34, 73), (62, 49), 0, 1, -5),
        ((53, 65), (56, 78), (40, 65), (36, 75), (64, 51), 1, 2, -6),
    ],
    "land": [
        ((61, 69), (56, 79), (36, 69), (33, 79), (63, 61), 9, 5, 1),
        ((58, 67), (55, 79), (38, 68), (34, 79), (60, 58), 6, 4, 3),
        ((54, 66), (53, 79), (39, 65), (36, 79), (57, 55), 2, 2, 2),
    ],
}


def draw_sabre(d, hand, tip):
    """Forge the same recurved edge from the wrist to the gameplay tip in every pose."""
    dx, dy = tip[0] - hand[0], tip[1] - hand[1]
    length = math.hypot(dx, dy)
    def point(distance, across):
        return (round(hand[0] + (dx * distance - dy * across) / length),
                round(hand[1] + (dy * distance + dx * across) / length))

    def plate(points, fill):
        d.polygon([point(u, v) for u, v in points], fill=fill, outline=INK)

    mid, belly = length * .52, length * .76
    plate([(0, -2), (7, -2), (mid, 0), (belly, 0), (length, -1),
           (length - 4, 3), (belly, 6), (mid, 7), (8, 4), (0, 2)], "#96634d")
    d.line([point(7, 2), point(mid, 5), point(belly, 4), tip], fill="#f4c982", width=2)
    d.line([point(belly, 4), tip], fill="#fff0bc")
    plate([(6, -2), (mid, 0), (belly, 0), (length-4,-1), (belly, 3), (mid, 3)], "#bd7952")
    d.line([point(10, 2), point(mid, 3), point(belly, 2)], fill="#fbb968")
    plate([(1, -5), (5, -7), (5, -4), (3, -2), (2, 4), (-2, 6), (-3, 4)], "#d49a5e")


def draw_frame(action, i, *, pose=None, armed=True, off_hand=None):
    if action == "roll":
        return roll_frame(i, armed)
    im = Image.new("RGBA", (96, 96))
    d = ImageDraw.Draw(im)
    run = action == "run"
    if pose is not None:
        knee, ankle, far_knee, far_ankle, hand, bob, lean, flutter = pose
    elif run:
        knee, ankle, hand, bob, flutter = STRIDE[i]
        far_knee, far_ankle = STRIDE[(i + 4) % 8][:2]
        lean = (4, 5, 6, 5, 4, 3, 3, 4)[i]
    elif action in AIR_POSES:
        knee, ankle, far_knee, far_ankle, hand, bob, lean, flutter = AIR_POSES[action][i]
    else:
        bob = (0, -1, -1, 0, 1, 1)[i]
        flutter = (0, -1, -2, 0, 1, 2)[i]
        knee, ankle = (51 + (i in (3, 4)), 65 + bob), (52, 79)
        far_knee, far_ankle = (39 - (i in (1, 2)), 64 + bob), (37, 79)
        hand = (55 + (i in (2, 3)), 55 + bob)
        lean = 0

    def poly(points, color, edge=None):
        d.polygon(points, fill=color, outline=edge)

    def part(points, color, edge=None):
        poly([(x + lean, y + bob) for x, y in points], color, edge)

    def bar(a, b, width, color):
        x, y = a
        u, v = b
        length = math.hypot(u - x, v - y) or 1
        dx, dy = (v - y) * width / (2 * length), (x - u) * width / (2 * length)
        poly(
            [
                (round(x + dx), round(y + dy)),
                (round(u + dx), round(v + dy)),
                (round(u - dx), round(v - dy)),
                (round(x - dx), round(y - dy)),
            ],
            color,
            INK,
        )

    def leg(hip, k, a, far):
        bar(hip, k, 9 if far else 11, "#293749" if far else "#565771")
        bar(k, (a[0], a[1] - 2), 7, "#31394b" if far else "#616879")
        if not far:
            d.line((k[0] + 2, k[1] + 2, a[0] + 1, a[1] - 5), fill="#b6c4bf", width=2)
        x, y = k
        poly(
            [(x - 4, y - 2), (x + 2, y - 4), (x + 4, y), (x + 1, y + 4), (x - 3, y + 2)],
            "#665748" if far else BRASS,
            INK,
        )
        if not far:
            d.line((x-2, y-2, x+1, y-3, x+3, y-1), fill="#e8c088")
        x, y = a
        poly(
            [
                (x - 4, y - 7),
                (x + 2, y - 8),
                (x + 3, y - 3),
                (x + 8, y - 1),
                (x + 8, y),
                (x - 5, y),
            ],
            "#283546" if far else IRON,
            INK,
        )
        d.line((x - 2, y - 5, x + 2, y - 6), fill="#88765d" if far else GOLD)
        if not far:
            d.line((x + 2, y - 2, x + 6, y - 1), fill="#bac4c2")
            poly([(x-4,y-6),(x+2,y-8),(x+2,y-5),(x-3,y-3)], "#87694f", INK)

    hip_shift = round(lean * .45)
    leg((45 + hip_shift, 54 + bob), far_knee, far_ankle, True)
    leg((49 + hip_shift, 54 + bob), knee, ankle, False)
    # Rear arm and layered brigandine, with a split skirt and sword belt.
    elbow = (40 if not run else 49 + (55 - hand[0]) // 2, 47 + bob)
    bar((47 + lean, 38 + bob), elbow, 7, "#475064")
    bar(elbow, off_hand or (elbow[0] + 5, 53 + bob), 6, "#756653")
    part(
        [
            (41, 35),
            (50, 34),
            (54, 39),
            (51, 50),
            (55, 57),
            (50, 62),
            (44, 58),
            (37, 61),
            (40, 51),
            (38, 42),
        ],
        IRON,
        INK,
    )
    part([(49, 38), (53, 40), (50, 49), (47, 51), (45, 45)], "#809099")
    part([(41, 47), (52, 46), (52, 50), (40, 53)], "#7d5841", INK)
    part([(46, 48), (50, 47), (50, 50), (46, 51)], GOLD)
    # The front tab is attached to the belt. It lags the leading knee on push-off.
    sway = (-4, -6, -5, -2, 1, 3, 1, -2)[i] if run else -flutter // 2
    part([(43,49),(51,48),(50,56),(47+sway,66),(42+sway,63),(39+sway,64),
          (43,54)], "#723f42", INK)
    part([(45,50),(50,49),(47,58),(44+sway,63),(43+sway,61)], "#b8664c")
    part([(41,48),(52,46),(52,50),(41,53)], "#573e39", INK)
    part([(47,48),(51,47),(51,50),(47,51)], GOLD)
    # One broad upper fold catches the sky. The bent lower hem exposes the lining.
    trail = -7 if run else -1
    hem = flutter + ((1,0,-2,-3,-1,1,3,2)[i] if run else 0)
    def cloth(x, y):
        return (x+trail, y+hem)
    part([(39,32),(49,31),(50,38),(39,46),cloth(28,51),cloth(16,53),
          cloth(20,49),cloth(11,48),cloth(23,43),(34,37)], "#213546", INK)
    part([(40,33),(48,32),(46,38),(36,44),cloth(24,47),cloth(14,48),
          cloth(22,44),(32,39)], "#528a99")
    part([(39,34),(46,32),(44,35),(36,39),cloth(24,44),cloth(20,45),
          (31,38)], "#a1c3c0")
    part([(40,39),(37,45),cloth(28,50),cloth(19,51),cloth(26,47)],
         "#386779")
    # A shorter, turned-back flap has a separate tip and a copper fastening at the neck.
    part([(40,35),(38,42),cloth(29,47),cloth(22,48),cloth(17,46),
          cloth(25,44),(33,39)], "#437f90", INK)
    part([(39,35),(36,40),cloth(28,45),cloth(22,46),cloth(26,43),(34,39)], "#82b8bb")
    part([(43,35),(44,39),(40,42),(37,42),(40,38)], "#c49b64", INK)
    part([(43,33),(50,33),(53,36),(49,39),(43,38),(39,40),(36,39)], "#789ba3", INK)
    # Full close-helm: stepped comb, dark neck lames, separate visor and bevor.
    part([(38,31),(37,24),(40,19),(47,16),(53,17),(57,22),(57,29),
          (51,35),(44,36)], "#3e5264", INK)
    part([(38,25),(41,19),(48,17),(53,18),(48,20),(44,24)], "#8fa7af")
    part([(39,22),(40,17),(46,13),(54,13),(51,16),(45,18)], "#97664d", INK)
    part([(41,18),(46,14),(52,14),(47,16)], "#e8ba78")
    part([(38,27),(43,24),(45,29),(44,35),(41,37),(37,34)], "#374458", INK)
    part([(40,29),(43,28),(43,32),(40,34)], "#74818b")
    part([(43,23),(51,20),(57,21),(61,24),(55,25),(45,28)], "#ac825b", INK)
    part([(45,23),(51,21),(56,22),(54,23),(46,25)], "#e6cf9b")
    part([(45,27),(55,24),(61,24),(57,28),(49,30),(45,29)], "#17232f")
    part([(50,27),(56,25),(58,25),(55,27),(50,28)], "#ffdc8b")
    part([(48,30),(55,28),(59,27),(56,32),(51,36),(47,34)], "#91a8ac", INK)
    part([(51,31),(56,29),(54,32),(51,34)], "#d3d3bc")
    part([(44,28),(47,27),(49,31),(48,34),(45,33)], "#6d5b50", INK)
    # Wrist turns through the stride, raises the blade on ascent and opens on landing.
    hx, hy = hand
    if armed:
        angles = {"idle": (3, 2, 1, 2, 4, 4), "run": (28, 22, 6, -13, -24, -18, 2, 20),
                  "jump": (-8, -33, -42), "fall": (-24, -5, 12), "land": (18, 11, 5)}
        angle = math.radians(angles[action][i])
        draw_sabre(d, hand, (hx + round(31 * math.cos(angle)), hy + round(31 * math.sin(angle))))
    shoulder = (44 + lean, 39 + bob)
    dx, dy = hx - shoulder[0], hy - shoulder[1]
    span = math.hypot(dx, dy) or 1
    bend = min(6, max(2, 12 - span / 2))
    arm_elbow = (
        round((shoulder[0] + hx) / 2 - dy / span * bend),
        round((shoulder[1] + hy) / 2 + dx / span * bend),
    )
    bar((44 + lean, 39 + bob), arm_elbow, 7, "#465369")
    bar(arm_elbow, hand, 7, "#996b4c")
    d.line((arm_elbow[0], arm_elbow[1]-1, hx-1, hy-1), fill="#dbab72", width=2)
    if run:
        d.line((arm_elbow[0], arm_elbow[1]-2, hx-1, hy-2), fill="#dab584", width=2)
    part([(38, 36), (46, 34), (52, 38), (51, 43), (44, 46), (37, 41)], BRASS, INK)
    part([(37, 38), (39, 35), (45, 34), (50, 36), (51, 38), (44, 37), (39, 40)], "#e1aa6c", INK)
    part([(40, 37), (45, 36), (48, 38), (43, 38)], GOLD)
    part([(41, 40), (47, 39), (46, 41), (42, 42)], "#97704b")
    part([(39, 41), (44, 43), (50, 40), (49, 43), (44, 45)], "#845b46")
    part([(36,39),(40,42),(44,44),(48,43),(47,46),(43,48),(37,44)], "#6f6157", INK)
    part([(37,41),(43,44),(47,43),(44,46),(41,45)], "#c09468")
    d.point((41 + lean, 39 + bob), fill="#ffdc94")
    poly(
        [(hx - 3, hy - 2), (hx, hy - 3), (hx + 3, hy), (hx + 2, hy + 3), (hx - 2, hy + 2)],
        "#766654",
        INK,
    )
    return im, hand


def generate():
    target = ASSETS / "walker"
    target.mkdir(parents=True, exist_ok=True)
    clips = {}
    for action, durations in {
        "idle": [185, 135, 165, 190, 140, 185],
        "run": [75, 65, 75, 75, 75, 65, 75, 75],
        "jump": [75, 100, 110],
        "fall": [65, 85, 100],
        "land": [42, 41, 42],
        "roll": [42, 42, 42, 49, 42, 42, 49, 42],
    }.items():
        sheet = Image.new("RGBA", (96 * len(durations), 96))
        frames = []
        for i, duration in enumerate(durations):
            im, wrist = draw_frame(action, i)
            sheet.paste(im, (i * 96, 0))
            frames.append(
                dict(
                    region=[i * 96, 0, 96, 96],
                    duration_ms=duration,
                    anchor=[48, 80],
                    weapon_socket=list(wrist),
                    events=(
                        ["footfall"]
                        if action == "run" and i in (1, 5)
                        else ["touchdown"]
                        if action == "land" and i == 0
                        else []
                    ),
                )
            )
        sheet.save(target / f"{action}.png")
        clips[action] = dict(
            sheet=f"walker/{action}.png", loop=action in ("idle", "run"), frames=frames
        )
    (target / "clips.json").write_text(json.dumps(clips, indent=2), encoding="utf-8")


if __name__ == "__main__":
    generate()
