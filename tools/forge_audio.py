"""Synthesize short original mono cues. No external recordings or samples."""
from array import array
from pathlib import Path
import math
import random
import wave

OUT = Path(__file__).resolve().parents[1] / "assets/combat/audio"
# Length, initial pitch, end pitch, noise mix, decay, bell overtone.
CUES = {
    "sabre": (0.12, 800, 185, 0.72, 4, 0),
    "maul": (0.24, 220, 48, 0.57, 3, 0),
    "hit": (0.19, 780, 170, 0.47, 6, 0.32),
    "crush": (0.36, 166, 46, 0.38, 5, 0.4),
    "hurt": (0.20, 285, 110, 0.30, 5, 0.23),
    "hook": (0.20, 565, 720, 0.08, 4, 0.36),
    "rivet": (0.32, 720, 1210, 0.07, 2, 0.21),
    "ram": (0.37, 205, 106, 0.11, 3, 0.51),
    "roll": (0.14, 310, 110, 0.76, 3, 0),
    "land": (0.11, 150, 58, 0.43, 5, 0),
    "shot": (0.14, 1110, 180, 0.29, 6, 0.22),
    "seal": (0.40, 310, 1070, 0.23, 2.5, 0.52),
    "sweep": (0.46, 196, 88, 0.20, 2.8, 0.61),
    "vent": (0.61, 440, 830, 0.24, 2.4, 0.53),
    "phase": (0.84, 159, 80, 0.09, 2.4, 0.74),
    "gate": (0.48, 466, 699, 0.06, 3.0, 0.44),
    "ignite": (0.27, 485, 1210, 0.28, 2.9, 0.38),
    "firecut": (0.41, 348, 66, 0.82, 3.9, 0.15),
    "fire_hit": (0.36, 193, 54, 0.41, 4.1, 0.32),
    "fork": (0.34, 530, 455, 0.12, 3.2, 0.47),
}


def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    for index, (name, (duration, start, end, noise, decay, over)) in enumerate(CUES.items()):
        rng = random.Random(340 + index)
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
            if name == "fork":
                # Two tine taps as the ferrule is lowered to the stone.
                echo = max(0, t - 0.13)
                mixed += 0.52 * min(1, echo / 0.003, (1 - u) * 20) * math.exp(-echo / 0.043) * math.sin(math.tau * 844 * echo)
            if name in ("sabre", "maul"):
                # Air swells towards release; the head of the maul has a low body.
                air = math.sin(math.pi * u) ** 1.25
                mixed = air * (
                    (0.86 if name == "sabre" else 0.56) * colored
                    + (0.08 if name == "sabre" else 0.26) * math.sin(phase)
                )
            elif name in ("hit", "crush", "fire_hit"):
                heavy = name != "hit"
                attack = math.exp(-t / 0.009) * (0.7 * colored + 0.2 * math.sin(phase * 1.7))
                body = (
                    math.exp(-t / (0.075 if heavy else 0.037))
                    * math.sin(phase)
                    * (0.75 if heavy else 0.42)
                )
                ring_t = max(0, t - (0.026 if heavy else 0.012))
                bell = math.sin(math.tau * (420 if heavy else 1090) * ring_t) + 0.39 * math.sin(
                    math.tau * (779 if heavy else 1760) * ring_t
                )
                ring = min(1, ring_t / 0.007) * math.exp(-ring_t / (0.085 if heavy else 0.044))
                mixed = (attack + body + 0.20 * ring * bell) * min(1, t / 0.002, (1 - u) * 25)
                if name == "hit":
                    # A short edge scrape follows the dry contact; leave room for the next swing.
                    scrape = max(0, t - 0.008)
                    rasp = math.sin(math.tau * (1730 * scrape - 8300 * scrape**2))
                    mixed = 0.88 * mixed + 0.28 * rasp * min(1, scrape / 0.002) * math.exp(-scrape / 0.020)
                if name == "crush":
                    # The shell buckles first. The short bronze rattle arrives after the transient.
                    delay = max(0, t - 0.045)
                    rattle = math.sin(math.tau * 636 * delay) + 0.32 * math.sin(
                        math.tau * 941 * delay
                    )
                    mixed = 0.89 * mixed + 0.18 * rattle * min(1, delay / 0.004) * math.exp(
                        -delay / 0.046
                    ) * min(1, (1 - u) * 20)
                if name == "fire_hit":
                    hiss = math.exp(-t / 0.093) * colored * (0.65 + 0.35 * math.cos(91 * t))
                    strike = math.sin(math.tau * 1450 * t) * math.exp(-t / 0.019)
                    mixed += min(1, t / 0.001, (1 - u) * 20) * (0.72 * hiss + 0.3 * strike)
            samples.append(round(20500 * max(-1.4, min(1.4, mixed))))
        with wave.open(str(OUT / (name + ".wav")), "wb") as wav:
            wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            wav.writeframes(samples.tobytes())


if __name__ == "__main__":
    generate()
