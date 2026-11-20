"""Compare the old J cut and the charged L cut at the same doorway and camera."""
import argparse
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

import arcade
import pyglet


def run(project, output, baseline):
    sys.path.insert(0, str(project.resolve()))
    from game.campaign import CampaignWindow
    from game.motion import STEP
    from pixel_check import check_pixels

    class Profile(CampaignWindow):
        def __init__(self):
            self.count = 0
            self.samples = []
            self.work = []
            self.contacts = 0
            self.previous = None
            self.measuring = False
            super().__init__()
            self.on_key_press(arcade.key.ENTER, 0)

        def on_update(self, dt):
            pass

        def on_draw(self):
            cycle, frame = divmod(self.count, 72)
            if cycle >= 6:
                return
            if frame == 0:
                self.start_room(0)
                self.walker.x = 291
                self.combat.foes[0].x = 338
                self.combat.foes[0].enter("recover")
                self.battle_view.levels[:] = [3] * 4
                self.on_key_press(arcade.key.J if baseline else arcade.key.L, 0)
            if frame == 34:
                self.on_key_release(arcade.key.J if baseline else arcade.key.L, 0)
            start = perf_counter()
            super().on_update(2 * STEP)
            super().on_draw()
            self.measuring = cycle > 0 and frame > 1
            if self.measuring:
                self.work.append((perf_counter() - start) * 1000)
            hits = [e for e in self.combat.events if e["kind"] == "hit"]
            if cycle == 0 and len(hits) > self.contacts:
                self.contacts = len(hits)
                image = self.ctx.get_framebuffer_image(self.ctx.screen, components=3)
                check_pixels(image)
                image.save(output / ("before.png" if baseline else "after.png"))
            self.count += 1

        def flip(self):
            super().flip()
            now = perf_counter()
            if self.measuring and self.previous is not None:
                self.samples.append((now - self.previous) * 1000)
            self.previous = now
            if self.count == 6 * 72:
                self.measuring = False
                pyglet.clock.schedule_once(lambda dt: self.close(), 0)

    output.mkdir(parents=True, exist_ok=True)
    window = Profile()
    gpu = pyglet.gl.gl_info.get_renderer()
    arcade.run()
    assert window.contacts == 1 and len(window.work) == len(window.samples) == 350, (
        window.contacts, len(window.work), len(window.samples), window.combat.events
    )

    def stats(values):
        return dict(
            median=round(statistics.median(values), 3),
            p95=round(statistics.quantiles(values, n=100, method="inclusive")[94], 3),
            max=round(max(values), 3),
        )

    result = dict(
        attack="J" if baseline else "L",
        samples=350,
        gpu=gpu,
        width=1280,
        height=720,
        levels=[3] * 4,
        vsync=True,
        guards=2,
        flip_ms=stats(window.samples),
        update_draw_submit_ms=stats(window.work),
    )
    name = "before" if baseline else "after"
    (output / (name + "-timing.json")).write_text(json.dumps(result, indent=2), encoding="utf8")
    print(result)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=root)
    parser.add_argument("--output", type=Path, default=root / "docs/verification/firecut")
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    run(args.project, args.output, args.baseline)
