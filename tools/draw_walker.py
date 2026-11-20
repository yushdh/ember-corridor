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
        knee, ankle = (51, 65), (52, 79)
        far_knee, far_ankle = (39, 64), (37, 79)
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

    leg((45, 54 + bob), far_knee, far_ankle, True)
    leg((49, 54 + bob), knee, ankle, False)
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
    # Short, forked shoulder mantle. Anchored at collar, flexing in the wind.
    trail = -8 if run else -2
    # The forked mantle has a broad shoulder mass and two separately folded hems.
    part(
        [
            (45, 31),
            (50, 37),
            (43, 44),
            (33, 48),
            (20 + trail, 51 + flutter),
            (25 + trail, 46 + flutter),
            (16 + trail, 47 + flutter),
            (24 + trail, 42 + flutter),
            (34, 38),
            (38, 33),
        ],
        "#24475b",
        INK,
    )
    part(
        [
            (44, 32),
            (48, 35),
            (44, 41),
            (38, 45),
            (31 + trail, 50 + flutter),
            (26 + trail, 50 + flutter),
            (30 + trail, 46 + flutter),
            (25 + trail, 46 + flutter),
            (30 + trail, 43 + flutter),
            (34, 37),
        ],
        CLOTH,
        INK,
    )
    part(
        [(43, 35), (41, 39), (33, 43), (28 + trail, 47 + flutter), (34 + trail, 44 + flutter)],
        "#78a2ad",
    )
    part([(44, 32), (51, 32), (53, 36), (49, 39), (42, 37), (37, 39), (39, 35)], ICE, INK)
    part(
        [(39, 35), (43, 35), (38, 39), (29 + trail, 44 + flutter), (23 + trail, 45 + flutter)],
        "#73aab9",
    )
    part([(37, 40), (33, 44), (25 + trail, 48 + flutter), (29 + trail, 44 + flutter)], "#4d829a")
    # A light selvage turns back over the dark lining; its free end trails the stride.
    hem = flutter + ((1, 0, -2, -3, -1, 1, 3, 2)[i] if run else 0)
    part(
        [
            (41, 35),
            (35, 42),
            (21 + trail, 49 + hem),
            (13 + trail, 50 + hem),
            (22 + trail, 44 + hem),
            (32, 40),
        ],
        "#36677c",
        INK,
    )
    part(
        [
            (39, 36),
            (33, 42),
            (21 + trail, 47 + hem),
            (17 + trail, 48 + hem),
            (24 + trail, 43 + hem),
            (32, 40),
        ],
        "#78aeb9",
    )
    part([(30, 41), (28, 44), (26, 44), (27, 42)], "#d4c197")
    if run:
        # A cold reflected edge stays behind the warmer hand on the return swing.
        part([(39, 34), (34, 38), (22, 42 + flutter), (13, 44 + flutter),
              (23, 40 + flutter), (33, 36)], "#91c6cd")
    # The folded lining drops away from the shoulder, leaving a notch between the hems.
    fold = flutter + (3 if run else 0)
    part([(40, 40), (37, 47), (28 + trail, 53 + fold), (21 + trail, 54 + fold),
          (28 + trail, 49 + fold), (34, 44)], "#263c50", INK)
    part([(37, 44), (31 + trail, 51 + fold), (25 + trail, 52 + fold),
          (30 + trail, 49 + fold)], "#487384")
    # Sealed kettle helm: raised crest, segmented bronze cheek and lit eye slit.
    part(
        [(39, 31), (39, 24), (42, 20), (48, 18), (52, 20), (55, 24), (55, 30), (51, 35), (45, 35)],
        "#677c88",
        INK,
    )
    part([(40, 25), (42, 21), (48, 19), (51, 21), (46, 21), (43, 25)], LIGHT)
    part([(44, 26), (53, 24), (57, 25), (54, 30), (52, 34), (48, 35), (45, 32)], "#a3afb0", INK)
    part([(44, 26), (55, 24), (54, 27), (47, 29), (44, 28)], INK)
    part([(48, 27), (54, 25), (53, 27), (49, 28)], "#ffdc94")
    part([(49, 30), (54, 28), (51, 33), (49, 34)], "#d1d2c1")
    for x, y in [(47, 30), (49, 31), (51, 30)]:
        d.point((x + lean, y + bob), fill=IRON)
    part([(38, 25), (42, 24), (43, 29), (40, 32), (38, 30)], "#39495a", INK)
    part([(38, 24), (42, 20), (48, 18), (53, 20), (47, 20), (42, 24)], "#91afb6")
    part([(42, 25), (51, 23), (57, 23), (60, 25), (54, 26), (44, 28)], "#95734e", INK)
    part([(47, 26), (56, 24), (55, 26), (48, 28)], "#ffca76")
    part([(53, 28), (57, 26), (54, 32), (50, 35), (49, 33)], "#a1b4ba", INK)
    # Bronze comb and undercut cheek give the helm a readable front even in profile.
    part([(37, 25), (39, 19), (43, 16), (53, 15), (51, 18), (43, 21), (41, 25)], "#8e694e", INK)
    part([(39, 21), (43, 17), (50, 16), (46, 18), (42, 20)], "#d5ae79")
    part([(47, 27), (57, 24), (62, 24), (56, 28), (49, 30)], "#202b36")
    part([(51, 27), (58, 25), (56, 27), (51, 29)], "#ffe1a0")
    part([(53, 25), (59, 23), (62, 23), (59, 25), (54, 26)], "#ede2bd")
    part([(54, 30), (57, 28), (55, 32), (51, 35), (50, 34)], "#d1c3a5")
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
    bar(arm_elbow, hand, 6, BRASS)
    if run:
        d.line((arm_elbow[0], arm_elbow[1]-2, hx-1, hy-2), fill="#dab584", width=2)
    part([(38, 36), (46, 34), (52, 38), (51, 43), (44, 46), (37, 41)], BRASS, INK)
    part([(37, 38), (39, 35), (45, 34), (50, 36), (51, 38), (44, 37), (39, 40)], "#e1aa6c", INK)
    part([(40, 37), (45, 36), (48, 38), (43, 38)], GOLD)
    part([(41, 40), (47, 39), (46, 41), (42, 42)], "#97704b")
    part([(39, 41), (44, 43), (50, 40), (49, 43), (44, 45)], "#845b46")
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
        "idle": [165, 150, 170, 180, 160, 175],
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
