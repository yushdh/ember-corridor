"""Compare forge choices with hits, cooldowns and incoming damage in an isolated game window."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import monotonic

import arcade
import pyglet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.campaign import CampaignWindow
from game.motion import STEP
from verify_stage4 import Route


def fresh_crate(out):
    """Reach just the first chest by native movement and combat from a new profile."""
    class FirstChest(Route):
        def drive(self, dt):
            w = self.w
            c = w.combat
            if monotonic() - self.start > 60:
                raise RuntimeError("First-room crate did not complete within 60 seconds")
            assert w.index == 0 and c.hp > 0
            if c.crate_taken:
                assert c.loadout.ranks == {"tide": 1} and w.store.data.shell_known
                assert "shell" not in c.loadout.options
                self.finished = True
                w.close()
            elif w.mode == "forge":
                assert c.loadout.options == ("tooth", "tide")
                assert w.forge_focus == 0
                self.snap("fresh-forge")
                self.tap("2")
            elif c.crate and c.near(w.walker, c.crate):
                self.hold(set())
                self.tap("e")
            else:
                super().drive(dt)

    with TemporaryDirectory() as tmp:
        w = CampaignWindow(save_dir=Path(tmp)/"profile", seed=17)
        trip = FirstChest(w, Path(tmp)/"frames")
        pyglet.clock.schedule_interval(trip.drive, 1/60)
        try:
            arcade.run()
        finally:
            pyglet.clock.unschedule(trip.drive)
            if not w.closed:
                w.close()
        assert trip.finished
        (out/"fresh-forge.png").write_bytes((trip.out/"fresh-forge.png").read_bytes())
        return {"seed": 17, "room": w.combat.room.name, "kills": sum(e.hp == 0 for e in w.combat.foes),
                "claimed": w.combat.loadout.equipped, "shell_unlocked": w.store.data.shell_known}


def verify(out, before=False):
    out.mkdir(parents=True, exist_ok=True)
    keys = arcade.key
    with TemporaryDirectory() as tmp:
        w = CampaignWindow(save_dir=Path(tmp), seed=17)
        def tap(key):
            w.on_key_press(key, 0)
            w.on_key_release(key, 0)

        def shot(name):
            w.on_draw()
            w.ctx.get_framebuffer_image(w.ctx.screen, components=3).save(out / (name + ".png"))

        def ticks_until(predicate, limit):
            for n in range(1, limit + 1):
                w.on_update(STEP)
                if predicate():
                    return n
            raise AssertionError("Timed out waiting for combat")

        def spar(distance):
            w.start_room(0, w.combat)
            w.walker.x = 410
            foe = w.combat.foes[0]
            foe.x = w.walker.x + distance
            return foe

        try:
            tap(keys.ENTER)
            w.store.update(unlock=True)
            rows = []
            for name, slot, heavy, prior in (
                ("swap", 1, False, ("tooth",)),
                ("upgrade", 0, True, ("tooth",)),
                ("armor", 2, False, ("tooth",)),
                ("refit", 0, False, ("tooth", "tide")),
            ):
                w.prepare_run()
                c = w.combat
                if heavy:
                    tap(keys.KEY_2)
                    w.on_update(STEP)
                for item in prior:
                    c.loadout.fit(item)
                for foe in c.foes:
                    foe.hp = 0
                    foe.enter("dead")
                w.walker.x, w.walker.y = c.crate
                w.scroll = 640
                w.sync_pose()
                tap(keys.E)
                for _ in range(slot):
                    tap(keys.DOWN)
                assert w.mode == "forge" and w.forge_focus == slot
                shot(name)
                if before:
                    return

                item = c.loadout.options[slot]
                original = c.loadout.ranks.copy()
                preview = w.forge_offers[item]
                tap(keys.ESCAPE)
                assert w.mode == "play" and not c.crate_taken
                assert c.loadout.ranks == original and c.loadout.equipped == prior[-1]
                tap(keys.E)
                for _ in range(slot):
                    tap(keys.DOWN)
                tap(keys.ENTER)
                assert c.crate_taken and c.loadout.equipped == item and w.mode == "play"
                assert preview == w.forge_stats(c.loadout)

                target = spar(35)
                target.enter("recover")
                health = target.hp
                tap(keys.J)
                ticks_until(lambda: target.hp < health, 105)
                hit = health - target.hp
                if name == "upgrade":
                    shot("hammer-hit")

                spar(440)
                tap(keys.Q)
                w.on_update(STEP)
                assert w.combat.cooldown > 0
                cooldown = ticks_until(lambda: w.combat.cooldown == 0, 421)

                target = spar(35)
                hp = w.combat.hp
                ticks_until(lambda: w.combat.hp < hp, 200)
                loss = hp - w.combat.hp
                assert (hit, cooldown, target.spec.damage - loss) == preview
                rows.append(dict(case=name, equipped=item, initial_ranks=original,
                                 preview=preview, first_hit=hit, cooldown_ticks=cooldown,
                                 hook_base_damage=target.spec.damage, hp_lost=loss))
            results = dict(window=w.get_framebuffer_size(), frozen=getattr(sys, "frozen", False),
                           step_seconds=STEP, cases=rows)
        finally:
            w.close()
    results["fresh_crate"] = fresh_crate(out)
    (out / "checks.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf8")
    print(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    verify(args.out, args.before)
