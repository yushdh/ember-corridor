from bisect import bisect_right
from dataclasses import dataclass
import json
import os
from contextlib import ExitStack
from pathlib import Path

import arcade
from PIL import Image

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
                cell = sheet.crop((x, y, x + w, y + h))
                left = top = 0
                if clip.get("trim_transparent"):
                    # Retain a clear border. Even crop edges preserve integer centres
                    # under mirroring and keep the foot and weapon at the authored pixels.
                    bounds = cell.getchannel("A").getbbox()
                    if bounds:
                        l, t, r, b = bounds
                        left, top = max(0, (l-1)//2*2), max(0, (t-1)//2*2)
                        cell = cell.crop((left, top, min(w, (r+2)//2*2), min(h, (b+2)//2*2)))
                texture = arcade.Texture(cell)
                ax, ay = entry["anchor"]
                sx, sy = entry["weapon_socket"]
                frames.append(
                    Frame(
                        texture,
                        texture.flip_left_right(),
                        (ax-left, ay-top),
                        (sx-left, sy-top),
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
