"""Bake short combat cues from the licensed PCM takes in tools/foley."""
from array import array
from pathlib import Path
import wave

RATE = 22050
SOURCE = Path(__file__).with_name("foley")
STEEL = "impactMetal_light_002"
EDGE = "impactMetal_light_003"
PLATE = "impactMetal_heavy_000"
PALM = "impactPunch_medium_000"
THUD = "impactPunch_heavy_001"
WOOD = "impactWood_heavy_001"

# Output length in ms, followed by (take, source offset ms, entry ms, speed, gain).
MIXES = {
    "sabre": (119, [("swing2", 12, 0, 1.12, .59)]),
    "maul": (195, [("swing", 24, 0, .90, .71)]),
    "hit": (123, [(STEEL, 0, 0, 1.05, .56), (PALM, 8, 3, 1.08, .53)]),
    "hit_lift": (144, [(EDGE, 0, 0, 1.10, .49), (WOOD, 0, 4, 1.12, .48)]),
    "hit_thrust": (109, [(PALM, 14, 0, 1.16, .78), (STEEL, 1, 7, 1.18, .32)]),
    "crush": (241, [(WOOD, 0, 0, .87, .62), (THUD, 10, 3, .89, .74),
                    (PLATE, 0, 21, .94, .41)]),
    "hurt": (152, [(PALM, 5, 0, .96, .69), (WOOD, 2, 8, .93, .26)]),
    "fire_hit": (274, [(PLATE, 0, 0, 1.04, .60), (THUD, 9, 3, .95, .66),
                       ("swing2", 26, 14, .79, .34), (WOOD, 1, 39, 1.18, .14)]),
}


def bake(out):
    for name, (length, layers) in MIXES.items():
        mix = [0.] * round(length * RATE / 1000)
        for take, offset, delay, speed, gain in layers:
            with wave.open(str(SOURCE / (take + ".wav")), "rb") as wav:
                assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (RATE, 1, 2)
                pcm = array("h", wav.readframes(wav.getnframes()))
            start = round(delay * RATE / 1000)
            for i in range(start, len(mix)):
                pos = offset * RATE / 1000 + (i - start) * speed
                index = int(pos)
                if index + 1 >= len(pcm):
                    break
                sample = pcm[index] + (pcm[index + 1] - pcm[index]) * (pos - index)
                mix[i] += gain * sample * min(1, (i-start+1)/12)
        # Preserve the recorded attack and leave headroom when swing and impact coincide.
        scale = min(1, 27100 / max(map(abs, mix)))
        tail = round(min(35, length / 4) * RATE / 1000)
        samples = array("h", (round(s * scale * min(1, (len(mix)-1-i)/tail))
                              for i,s in enumerate(mix)))
        with wave.open(str(out / (name + ".wav")), "wb") as wav:
            wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            wav.writeframes(samples.tobytes())
