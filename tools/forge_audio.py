"""Bake the procedural signals and the sample-based melee mix at logical event timing."""
from array import array
from pathlib import Path
import math
import random
import wave

from mix_foley import bake as bake_foley

OUT = Path(__file__).resolve().parents[1] / "assets/combat/audio"
# Random seed, length, initial pitch, end pitch, noise mix, decay, bell overtone.
CUES = {
    "hook": (345, 0.20, 565, 720, 0.08, 4, 0.36),
    "rivet": (346, 0.32, 720, 1210, 0.07, 2, 0.21),
    "ram": (347, 0.37, 205, 106, 0.11, 3, 0.51),
    "roll": (348, 0.14, 310, 110, 0.76, 3, 0),
    "land": (349, 0.11, 150, 58, 0.43, 5, 0),
    "shot": (350, 0.14, 1110, 180, 0.29, 6, 0.22),
    "seal": (351, 0.40, 310, 1070, 0.23, 2.5, 0.52),
    "sweep": (352, 0.46, 196, 88, 0.20, 2.8, 0.61),
    "vent": (353, 0.61, 440, 830, 0.24, 2.4, 0.53),
    "phase": (354, 0.84, 159, 80, 0.09, 2.4, 0.74),
    "gate": (355, 0.48, 466, 699, 0.06, 3.0, 0.44),
    "ignite": (356, 0.27, 485, 1210, 0.28, 2.9, 0.38),
    "firecut": (357, 0.41, 348, 66, 0.82, 3.9, 0.15),
    "fork": (359, 0.34, 530, 455, 0.12, 3.2, 0.47),
    "chain": (360, 0.39, 370, 260, 0.45, 4, 0.22),
}


def chime(age, pitch):
    attack = min(1, age / 0.003)
    tone = math.sin(math.tau * pitch * age)
    partial = 0.19 * math.sin(math.tau * pitch * 2.63 * age)
    return attack * math.exp(-age / 0.039) * (tone + partial)


def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    bake_foley(OUT)
    for name, (seed, duration, start, end, noise, decay, over) in CUES.items():
        rng = random.Random(seed)
        samples = array("h")
        phase = 0
        colored = 0
        for n in range(round(duration * 22050)):
            t = n / 22050
            u = t / duration
            phase += math.tau * (start * (end / start) ** u) / 22050
            colored = 0.56 * colored + 0.44 * rng.uniform(-1, 1)
            envelope = min(1, t / 0.006) * math.exp(-decay * u) * min(1, (1 - u) * 25)
            signal = (1 - noise) * math.sin(phase) + noise * colored + over * math.sin(phase * 2.71)
            mixed = envelope * signal
            if name == "ignite":
                # Two short bronze notes under the bolt whistle; leave room for the release.
                tap = max(0, t - 0.064)
                mixed = (0.60 * chime(t, 368) + 0.73 * chime(tap, 552)) * min(1, (1 - u) * 25)
            if name == "fork":
                # Two tine taps as the ferrule is lowered to the stone.
                echo = max(0, t - 0.13)
                mixed += 0.52 * min(1, echo / 0.003, (1 - u) * 20) * math.exp(-echo / 0.043) * math.sin(math.tau * 844 * echo)
            if name == "chain":
                mixed = 0.0
                for onset, pitch, level in ((0, 418, 0.8), (0.08, 564, 0.64), (0.19, 319, 0.92)):
                    age = t - onset
                    if age >= 0:
                        mixed += level * (0.62 * chime(age, pitch) + colored * math.exp(-age / 0.017))
            samples.append(round(20500 * max(-1.4, min(1.4, mixed))))
        with wave.open(str(OUT / (name + ".wav")), "wb") as wav:
            wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            wav.writeframes(samples.tobytes())


if __name__ == "__main__":
    generate()
