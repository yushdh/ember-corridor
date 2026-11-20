from bisect import bisect_right
from dataclasses import dataclass
import json
import os
from contextlib import ExitStack
from pathlib import Path

import arcade
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parents[1] / "assets"


@dataclass
class Frame:
    right: arcade.Texture
    left: arcade.Texture
    anchor: tuple
    socket: tuple
    events: tuple

    def attachment(self, facing):
        ax, ay = self.anchor
        sx, sy = self.socket
        return (sx - ax) * facing, ay - sy


@dataclass
class Clip:
    ends: list
    frames: list
    loop: bool

    def frame(self, age):
        time = age * 1000
        if self.loop:
            time %= self.ends[-1]
        index = min(len(self.frames) - 1, bisect_right(self.ends, time))
        return self.frames[index]


def load_clips(folder="walker"):
    data = json.loads((ASSETS / folder / "clips.json").read_text(encoding="utf-8"))
    clips = {}
    with ExitStack() as stack:
        sheets = {}
        for name, clip in data.items():
            frames, ends = [], []
            elapsed = 0
            path = (ASSETS if folder == "walker" else ASSETS / folder) / clip["sheet"]
            if path not in sheets:
                sheets[path] = stack.enter_context(Image.open(path))
            sheet = sheets[path]
            for entry in clip["frames"]:
                x, y, w, h = entry["region"]
                texture = arcade.Texture(sheet.crop((x, y, x + w, y + h)))
                frames.append(
                    Frame(
                        texture,
                        texture.flip_left_right(),
                        tuple(entry["anchor"]),
                        tuple(entry["weapon_socket"]),
                        tuple(entry["events"]),
                    )
                )
                elapsed += (
                    entry["duration_ms"] if "duration_ms" in entry else entry["ticks"] * 1000 / 120
                )
                ends.append(elapsed)
            clips[name] = Clip(
                ends, frames, clip.get("loop", name in ("hammer_idle", "hammer_run"))
            )
    return clips


def font_face():
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    face = next(
        (fonts / n for n in ("msyh.ttc", "Deng.ttf", "simhei.ttf") if (fonts / n).is_file()), None
    )
    if face is None:
        raise RuntimeError("需要中文字体。请启用 Windows 中文补充字体并重新启动游戏。")
    return str(face)


def ui_texture(paused=False):
    face = font_face()

    def font(size):
        return ImageFont.truetype(str(face), size)

    im = Image.new("RGBA", (640, 360))
    d = ImageDraw.Draw(im)
    if paused:
        d.rectangle((227, 144, 413, 210), fill=(21, 35, 44, 245), outline="#aa9b80")
        d.text((275, 151), "渡口暂停", font=font(20), fill="#e4d2af")
        d.text((265, 184), "按 Esc 继续行走", font=font(13), fill="#b4c4bd")
        return arcade.Texture(im)
    # Two small inscriptions keep the playable silhouette unobstructed.
    d.rectangle((12, 12, 130, 50), fill=(19, 32, 42, 228))
    d.rectangle((12, 12, 13, 50), fill="#cfab78")
    d.text((21, 15), "余 烬 回 廊", font=font(10), fill="#a8b9b5")
    d.text((20, 28), "盐炉渡口", font=font(17), fill="#f0e4c9")
    labels = (("A/D", "移动"), ("Space", "跳跃"), ("S+Space", "下穿"), ("K", "翻滚"), ("Esc", "暂停"))
    x = 15
    for key, label in labels:
        key_width = round(d.textlength(key, font=font(11))) + 9
        d.rectangle((x, 333, x + key_width, 349), fill="#263843", outline="#82918f")
        d.text((x + 4, 333), key, font=font(11), fill="#e0dfc9")
        x += key_width + 4
        d.text(
            (x, 332), label, font=font(12), fill="#d6ded2", stroke_width=1, stroke_fill="#20333d"
        )
        x += 34
    return arcade.Texture(im)
