"""Attribute slow window draws during a separate, instrumented seed-17 soak."""

import argparse
import cProfile
import json
import pstats
from pathlib import Path
from time import perf_counter, thread_time
from unittest.mock import patch

from soak_gallery import RecordingWindow, run


def trace_draws(out, seconds):
    original = RecordingWindow.on_draw
    slow = []
    frame = 0  # Title pre-draw is frame zero.

    def draw(window):
        nonlocal frame
        profiler = cProfile.Profile()
        start, cpu_start = perf_counter(), thread_time()
        profiler.runcall(original, window)
        elapsed = 1000 * (perf_counter() - start)
        cpu = 1000 * (thread_time() - cpu_start)
        if elapsed >= 25:
            stats = pstats.Stats(profiler).strip_dirs().stats
            calls = []
            for (file, line, name), (_, count, own, total, _) in stats.items():
                calls.append(dict(file=file, line=line, name=name, count=count,
                                  own_ms=round(1000 * own, 3), total_ms=round(1000 * total, 3)))
            slow.append(dict(frame=frame, room=window.index + 1, tick=window.combat.tick,
                             wall_ms=round(elapsed, 3), thread_cpu_ms=round(cpu, 3),
                             own=sorted(calls, key=lambda c: -c["own_ms"])[:10],
                             cumulative=sorted(calls, key=lambda c: -c["total_ms"])[:15]))
        frame += 1

    with patch.object(RecordingWindow, "on_draw", draw):
        run(out, seconds, None)
    (out / "draw-calls.json").write_text(json.dumps(slow, indent=2), encoding="utf8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=240)
    args = parser.parse_args()
    trace_draws(args.out, args.seconds)
