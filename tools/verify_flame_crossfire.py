"""Reproduce a charged slash, dual telegraphs and a riposte in seed 17's west gallery."""
import argparse
import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from statistics import median, quantiles
from time import perf_counter

import arcade
import pyglet
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.combat import CHAIN_OPEN, CHAIN_RADIUS, chain_tip
from game.motion import STEP

K = arcade.key
GALLERY = {1:(K.D,), 95:(K.D,K.SPACE), 171:(K.A,K.K), 172:(), 230:(K.D,K.L),
           231:(K.L,), 286:(), 330:(K.D,K.K), 331:(), 373:(K.A,), 410:(K.A,K.J), 411:()}
CROSSING = {1:(K.D,K.L), 2:(K.L,), 66:(), 119:(K.D,K.K), 120:(),
            162:(K.A,), 199:(K.A,K.J), 200:()}
GALLERY_HIT = {t:keys for t,keys in GALLERY.items() if t < 330}
GALLERY_HIT.update({230:(K.A,K.L), 339:(K.D,K.K), 340:(), 382:(K.A,), 433:(K.A,K.J), 434:()})


def fight(w, out, scene, dodge, early=False):
    staged = scene == "crossing"
    original = w.route
    index = next(i for i,t in enumerate(original.rooms) if t.key == "gallery-west")
    if staged:
        # The armoured guard takes the contact flash without interrupting either attacker.
        tiles = list(original.rooms)
        room = tiles[index].room
        guards = (room.guards[0], ("rivet",330,143,(250,380)), ("ram",198,94,(197,209)))
        tiles[index] = replace(tiles[index],room=replace(room,guards=guards))
        w.route = replace(original,rooms=tuple(tiles))
    w.start_room(index)
    w.route = original
    if staged:
        w.walker.x = 166
    c, p = w.combat, w.walker
    chain, bow, armour = c.foes
    script = {"crossing": CROSSING, "gallery": GALLERY, "gallery-hit": GALLERY_HIT}[scene]
    if early:
        script = dict(CROSSING)
        script[114],script[115] = script.pop(119),script.pop(120)
    roll = {"crossing":119, "gallery":330, "gallery-hit":339}[scene]
    end = {"crossing":218, "gallery":432, "gallery-hit":452}[scene]
    snaps = ({64:"charge", 70:"impact", 82:"arc", 114:"recovery", 128:"roll", 212:"counter"}
             if staged else {240:"bait", 300:"gallery-arc", 336:"gallery-roll", 422:"gallery-counter"})
    held, film = set(), []
    costs = []
    if scene == "gallery-hit":
        snaps = {288:"gallery-impact", 446:"gallery-finisher"}
    if early:
        snaps = {}
    observations = {"both_warnings_during_charge":[], "both_warnings_during_fire_hitstop":[],
                    "open_hook_and_bow_during_swing":[], "under_hook":[], "passing_bolt":[],
                    "roll_starts":[]}
    for tick in range(1,end+1):
        if tick in script and (dodge or tick<roll):
            desired = set(script[tick])
            for key in sorted(held-desired):
                w.on_key_release(key,0)
            for key in script[tick]:
                if key not in held:
                    w.on_key_press(key,0)
            held = desired
        start = perf_counter()
        w.on_update(STEP)
        assert c.tick == tick
        if p.roll_age==0:
            observations["roll_starts"].append(tick)
        dual = chain.state == bow.state == "warn"
        if dual and c.flame.charge>=0:
            observations["both_warnings_during_charge"].append(tick)
        if dual and c.freeze and c.flame.swing>=0:
            observations["both_warnings_during_fire_hitstop"].append(tick)
        if dual and chain.age>=CHAIN_OPEN and c.flame.swing>=0:
            observations["open_hook_and_bow_during_swing"].append(tick)
        if tick>=roll and p.roll_age>=0:
            hx,hy=chain_tip(chain,c.surfaces)
            if chain.state=="active" and abs(hx-p.x)<=11+CHAIN_RADIUS and p.y+p.height<hy-CHAIN_RADIUS:
                observations["under_hook"].append(tick)
            if any(abs(b.x-p.x)<=12 for b in c.bolts):
                observations["passing_bolt"].append(tick)
        if tick%2==0:
            w.on_draw()
            w.ctx.finish()
            costs.append((perf_counter()-start)*1000)
            if dodge and (tick in snaps or tick%4==0):
                im=w.ctx.get_framebuffer_image(w.ctx.screen,components=3)
                if tick in snaps:
                    im.save(out/(snaps[tick]+".png"))
                if tick%4==0:
                    film.append(im.resize((640,360),Image.Resampling.NEAREST))
            w.flip()
    for key in held:
        w.on_key_release(key,0)
    events=list(c.events)
    assert any(ev["kind"]=="firecut" for ev in events)
    assert any(ev["kind"]=="shot" for ev in events)
    if staged:
        assert observations["both_warnings_during_fire_hitstop"] and observations["open_hook_and_bow_during_swing"]
        assert any(ev.get("action")=="firecut" and ev.get("enemy")=="ram" for ev in events)
    if scene == "gallery-hit":
        assert c.hp == 100 and chain.hp == 0 and observations["passing_bolt"]
        assert any(e.get("action")=="firecut" and e.get("enemy")=="chain" for e in events)
    elif dodge and not early:
        assert c.hp==100 and chain.hp==52 and observations["under_hook"] and observations["passing_bolt"], (events,observations)
        assert any(ev.get("action")=="cut" and ev.get("enemy")=="chain" for ev in events)
    elif not dodge:
        assert c.hp<100 and any(ev["kind"]=="hurt" for ev in events)
    if film:
        film[0].save(out/("early-tap.gif" if early else scene+".gif"),save_all=True,append_images=film[1:],
                     duration=([30,30,40]*len(film))[:len(film)],loop=0)
    return dict(player_hp=c.hp,chain_hp=chain.hp,armour_hp=armour.hp,
                windows=observations,events=events,samples=len(costs),
                measured_step_draw_sync_median_ms=round(median(costs),2),
                measured_step_draw_sync_p95_ms=round(quantiles(costs,n=100)[94],2))


def verify(out, *, baseline=False):
    out.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory() as tmp:
        w=CampaignWindow(seed=17,save_dir=Path(tmp)/"profile")
        try:
            w.on_key_press(K.ENTER,0)
            w.battle_view.levels[:]=[3,3,2,3]
            result=dict(seed=17,gpu=pyglet.gl.gl_info.get_renderer(),framebuffer=w.get_framebuffer_size(),
                        levels=list(w.battle_view.levels),frozen=getattr(sys,"frozen",False))
            for name in ("gallery","crossing"):
                for dodge in (False,True):
                    result[name if dodge else name+"_standing"]=fight(w,out,name,dodge)
            result["gallery-hit"]=fight(w,out,"gallery-hit",True)
            result["early_tap"]=fight(w,out,"crossing",True,early=True)
            tap = result["early_tap"]
            assert tap["windows"]["roll_starts"] == ([] if baseline else [118])
            assert (tap["player_hp"],tap["chain_hp"]) == ((82,68) if baseline else (100,52))
            (out/"report.json").write_text(json.dumps(result,indent=2),encoding="utf8")
        finally:
            w.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--baseline", action="store_true", help="Expect the input behaviour of dc4b042.")
    args=parser.parse_args()
    verify(args.out, baseline=args.baseline)
