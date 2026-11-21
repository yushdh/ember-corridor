"""Check optional ledges from the room entrances using the campaign's normal input and physics."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import arcade

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.campaign import CampaignWindow
from game.motion import BODY_HALF_WIDTH, STEP
from game.terrain import FLOOR


# For the high rope bridge, launch from the far lip of the western pump.
# The other platforms are within jumping height of the floor directly below.
SIDE_PATHS = {"gate": ("盐栈", None), "sluice-twins": ("中继栈", None),
              "pump": ("索桥", "西泵台"), "gallery-west": ("横渡板", None)}


def verify(seed, out):
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    k = arcade.key
    with TemporaryDirectory() as tmp:
        w = CampaignWindow(seed=seed, save_dir=tmp)
        try:
            w.on_key_press(k.ENTER, 0)
            w.on_key_release(k.ENTER, 0)
            for index, template in enumerate(w.route.rooms):
                if template.key not in SIDE_PATHS:
                    continue
                w.start_room(index)
                c, p = w.combat, w.walker
                for guard in c.foes:
                    guard.hp = 0
                    guard.enter("dead")
                surfaces = {s.name: s for s in c.surfaces}
                destination, launcher = SIDE_PATHS[template.key]
                ledge = surfaces[destination]
                launch = surfaces[launcher] if launcher else FLOOR
                midpoint = (ledge.left + ledge.right) // 2
                launch_x = launch.right - 16 if launcher else midpoint
                takeoff = None
                held = set()
                jump_until = -1
                for tick in range(1200):
                    if p.support is ledge and ledge.left <= p.x < ledge.right:
                        break
                    keys = {k.D} if p.x < midpoint else set()
                    if p.support and p.x >= launch_x and not takeoff:
                        assert p.support == launch, (destination, p.support)
                        takeoff = dict(surface=launch.name, x=round(p.x, 2), y=p.y)
                        jump_until = tick + 65
                    if p.support:
                        for face in c.surfaces[1:]:
                            gap = face.left - p.x - BODY_HALF_WIDTH
                            if face.one_way or not 0 <= gap <= 24 or face.top <= p.y:
                                continue
                            if face.bottom == FLOOR.top:
                                jump_until = tick + 65
                            elif not p.recharge:
                                keys.add(k.K)
                    if tick < jump_until:
                        keys.add(k.SPACE)
                    for key in held - keys:
                        w.on_key_release(key, 0)
                    for key in keys - held:
                        w.on_key_press(key, 0)
                    held = keys
                    w.on_update(STEP)
                    if tick % 4 == 0:
                        w.on_draw()
                else:
                    raise AssertionError((template.key, destination, p.x, p.y, p.support))
                assert takeoff and p.y == ledge.top
                w.on_draw()
                image = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
                image.save(out / f"{template.key}-side.png")
                rows.append(dict(room=index+1, template=template.key, launch=takeoff, surface=destination,
                                 x=round(p.x, 2), feet_y=p.y, top=ledge.top, ticks_from_entry=tick))
                for key in held:
                    w.on_key_release(key, 0)
            if not rows:
                raise ValueError("No matching side paths on this seed")
            (out / "side-platforms.json").write_text(json.dumps(dict(seed=seed, cases=rows,
                method="Room entrance; guards cleared by fixture; keyboard callbacks; 120 Hz"),
                ensure_ascii=False, indent=2), encoding="utf8")
            print(rows)
        finally:
            w.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.seed, args.output)
