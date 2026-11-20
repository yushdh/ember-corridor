"""Time identical full-feedback flame strikes in the live, synchronized campaign."""
import argparse
import gc
import hashlib
import json
import platform
import statistics
import sys
import weakref
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import arcade
import pyglet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.campaign import CampaignWindow


def stats(values):
    percentiles = statistics.quantiles(values, n=100, method="inclusive")
    return {k: round(v, 4) for k, v in (("median", statistics.median(values)),
                                         ("p95", percentiles[94]), ("p99", percentiles[98]))}


class Sample(CampaignWindow):
    def __init__(self, profile):
        self.frame = 0
        self.record = False
        self.present, self.work, self.sync = [], [], []
        self.previous = None
        self.peak = 0
        self.hashes = {}
        super().__init__(save_dir=profile, seed=17)
        self.on_key_press(arcade.key.ENTER, 0)

    def on_update(self, dt):
        pass

    def sync_pose(self):
        start = perf_counter()
        super().sync_pose()
        if self.record:
            self.sync.append(1000*(perf_counter()-start))

    def on_draw(self):
        cycle, i = divmod(self.frame, 96)
        if cycle >= 9:
            return
        self.record = False
        if i == 0:
            self.start_room(0)
            self.battle_view.levels[:] = [3]*4
            self.battle_view.rng.seed(19)
            self.ambient_tick = 0
            self.walker.x = 292
            for e, x in zip(self.combat.foes, (339, 369)):
                e.x, e.patrol = x, (280, 530)
                e.enter("recover")
            self.on_key_press(arcade.key.L, 0)
        if i == 34:
            self.on_key_release(arcade.key.L, 0)
        self.record = cycle > 0 and i > 1
        start = perf_counter()
        super().on_update(1/60)
        super().on_draw()
        if self.record:
            self.work.append(1000*(perf_counter()-start))
        self.peak = max(self.peak, len(self.battle_view.particles))
        if cycle == 0 and i in (15, 33, 40, 60):
            im = self.ctx.get_framebuffer_image(self.ctx.screen, components=3)
            self.hashes[i] = hashlib.sha256(im.tobytes()).hexdigest()
        self.frame += 1

    def flip(self):
        super().flip()
        now = perf_counter()
        if self.record and self.previous is not None:
            self.present.append(1000*(now-self.previous))
        self.previous = now
        if self.frame == 864:
            self.record = False
            pyglet.clock.schedule_once(lambda dt: self.close(), 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory() as profile:
        w = Sample(Path(profile))
        refs = []
        for i in range(30):
            refs.extend((weakref.ref(w.combat), weakref.ref(w.walker)))
            w.prepare_run()
            w.start_room(1+i%4)
        w.prepare_run()
        gc.collect()
        assert all(ref() is None for ref in refs)
        gpu = pyglet.gl.gl_info.get_renderer()
        arcade.run()
        assert len(w.sync) == len(w.work) == len(w.present) == 752 and w.peak > 0
        data = dict(python=platform.python_version(), arcade=arcade.__version__, gpu=gpu,
                    window=[1280,720], logical=[640,360], vsync=True, levels=[3]*4,
                    foes=2, peak_particles=w.peak, samples=len(w.work), fps=round(1000/statistics.mean(w.present),2),
                    present_ms=stats(w.present), update_draw_submit_ms=stats(w.work), sync_pose_ms=stats(w.sync),
                    released_old_objects=len(refs), warmup_frame_hashes=w.hashes)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(data,indent=2),encoding="utf8")
        print(data)


if __name__ == "__main__":
    main()
