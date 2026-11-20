"""Cycle lethal combat, R and all five rooms, and sample live Windows process counters."""
import ctypes
from ctypes import wintypes
import gc
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import weakref

import arcade

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow


class Memory(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ("peak_working", "working", "peak_paged", "paged",
            "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile", "private")]


def sample(w, cycle):
    gc.collect()
    w.ctx.finish()
    info = Memory()
    info.cb = ctypes.sizeof(info)
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = (wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD)
    if not get_memory(get_process(), ctypes.byref(info), info.cb):
        raise ctypes.WinError()
    view = w.battle_view
    return dict(cycle=cycle, private_mib=round(info.private/2**20,2),
                working_mib=round(info.working/2**20,2),
                handlers=sum(len(layer) for layer in w._event_stack),
                foes=len(view.enemies), particles=len(view.particles),
                projectiles=len(view.projectiles), voices=len(view.players))


def main():
    with TemporaryDirectory() as profile:
        w = CampaignWindow(save_dir=Path(profile), seed=17)
        try:
            w.on_key_press(arcade.key.ENTER,0)
            w.on_key_release(arcade.key.ENTER,0)
            rows, old = [], []
            for i in range(1, 41):
                w.start_room((i-1)%5)
                old.extend((weakref.ref(w.combat), weakref.ref(w.walker)))
                # Inject enemy contacts through damage_player. Recovery and death use the real clock.
                for frame in range(500):
                    if not w.combat.immune and w.combat.hp:
                        w.combat.damage_player(w.walker,w.combat.foes[0],w.walker.x,w.walker.y+25)
                    w.on_update(1/30)
                    if frame % 6 == 0:
                        w.on_draw()
                    if w.combat.death_age > 45:
                        break
                assert not w.combat.hp and w.combat.death_age > 45
                w.on_key_press(arcade.key.R,0)
                w.on_key_release(arcade.key.R,0)
                assert w.combat.hp == 100 and w.index == 0
                if i in (1,5,10,20,30,40):
                    rows.append(sample(w,i))
            assert all(ref() is None for ref in old)
            assert len({r["handlers"] for r in rows}) == 1
            assert all(not any(r[k] for k in ("particles","projectiles","voices")) for r in rows)
            result = dict(samples=rows, released=len(old), backend="Windows GetProcessMemoryInfo",
                          method="Injected contacts; production death clock, R and room transition")
            out = ROOT/"docs/verification/stage8/soak.json"
            out.write_text(json.dumps(result,indent=2),encoding="utf8")
            print(result)
        finally:
            w.close()


if __name__ == "__main__":
    main()
