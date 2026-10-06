#!/usr/bin/env python3
"""
GIL-contention probe: does it matter whether a per-event loop runs in the
interpreter or in a C `nogil` region?

Design
------
A fixed number of "completions" is processed two ways while K CPU-bound Python
threads contend for the GIL:

    reactor_python  -- an interpreted Python per-event loop (every completion
                       is dispatched in bytecode, as in asyncio).
    reactor_nogil   -- the same arithmetic in a C `nogil` region (the whole
                       batch is processed in C with the GIL released).

The per-event arithmetic is the same splitmix64 step in both; only *where the
loop runs* differs. There is no I/O and no system call in either loop, so this
probe says nothing about the system-call interface. That variable is tested
separately by the io_uring/epoll x C/Python factorial experiment
(bench_matrix.py --experiment factorial).

Reading the result
------------------
Each design's contention slowdown is t(K) / t(0), computed from the mean of
REPS timings (standard deviation shown; the minimum-based ratio is printed
alongside, and is smaller because a minimum keeps the luckiest run).
  * Python loop slows while the C loop stays flat: the interpreter on the hot
    path costs throughput under GIL contention; a C loop avoids that cost.
  * Both slow down: the machine ran out of cores; lower KMAX.
  * Neither slows: contention did not separate the designs.

Run
---
    python3 benchmarks/setup_gilprobe.py build_ext --inplace   # once
    python3 benchmarks/gil_experiment.py                       # sweep

Env: OPS_PER_EVENT, KMAX, REPS, TARGET_S. Keep KMAX below the core
count so the contenders and the loop under test each have a core.
"""

from __future__ import annotations

import os
import sys
import threading

# gilprobe builds in place at the project root; ensure it is importable
# regardless of the working directory the experiment is launched from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import gilprobe
except ImportError:
    sys.exit(
        "gilprobe extension not built. Run:\n"
        "    python3 benchmarks/setup_gilprobe.py build_ext --inplace"
    )

import time

OPS_PER_EVENT = int(os.environ.get("OPS_PER_EVENT", "8"))
KMAX = int(os.environ.get("KMAX", "4"))
REPS = int(os.environ.get("REPS", "5"))
TARGET_S = float(os.environ.get("TARGET_S", "0.25"))

_C1 = 6364136223846793005
_C2 = 1442695040888963407
_MASK = (1 << 64) - 1


def reactor_python(total_events: int, ops_per_event: int) -> tuple[float, int]:
    """Status-quo path: dispatch every completion in interpreted Python.

    Mirrors gilprobe._work exactly, but as real bytecode -- so the eval-breaker
    periodically yields the GIL to contending threads, exactly as a Python event
    loop does.
    """
    acc = 0
    t0 = time.perf_counter()
    for _ in range(total_events):
        for _ in range(ops_per_event):
            acc = (acc * _C1 + _C2) & _MASK
    return time.perf_counter() - t0, acc


def _spin(stop: threading.Event) -> None:
    # Pure-Python CPU load: competes for the GIL with the reactor under test.
    x = 0
    while not stop.is_set():
        for _ in range(200_000):
            x += 1


def _times(fn, *args) -> list[float]:
    # All REPS timings. The table reports their mean and standard deviation;
    # the minimum is printed too, but a minimum understates contention (it
    # keeps the run in which the loop happened to win the GIL most often).
    return [fn(*args)[0] for _ in range(REPS)]


def _mean_sd(xs: list[float]) -> tuple[float, float]:
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, 0.0
    return m, (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def _calibrate(fn, ops: int) -> int:
    # Size the event count so this design runs ~TARGET_S at rest -- long enough
    # for stable timing (the C path is ~60x faster, so it needs many more events
    # than the Python path to be measured meaningfully).
    n = 50_000
    while True:
        t = fn(n, ops)[0]
        if t >= 0.03:
            return max(1, int(n * TARGET_S / t))
        n *= 4


def measure(k: int, py_events: int, nogil_events: int) -> tuple[list[float], list[float]]:
    """Return (python_timings, nogil_timings) with k background contenders."""
    stop = threading.Event()
    threads = [threading.Thread(target=_spin, args=(stop,), daemon=True)
               for _ in range(k)]
    for t in threads:
        t.start()
    try:
        reactor_python(py_events // 10, OPS_PER_EVENT)          # warm
        gilprobe.reactor_nogil(nogil_events // 10, OPS_PER_EVENT)  # warm
        py_s = _times(reactor_python, py_events, OPS_PER_EVENT)
        nogil_s = _times(gilprobe.reactor_nogil, nogil_events, OPS_PER_EVENT)
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=1.0)
    return py_s, nogil_s


def main() -> None:
    cpus = os.cpu_count() or 1
    print("# GIL-contention vs. syscall-count experiment")
    print(f"- python: {sys.version.split()[0]}   cpus: {cpus}")
    py_events = _calibrate(reactor_python, OPS_PER_EVENT)
    nogil_events = _calibrate(gilprobe.reactor_nogil, OPS_PER_EVENT)
    print(f"- params: ops/event={OPS_PER_EVENT} Kmax={KMAX} reps={REPS} "
          f"target={TARGET_S}s")
    print(f"- calibrated events: python={py_events:,}  C/nogil={nogil_events:,} "
          f"(each design sized to ~{TARGET_S}s at rest)")

    rt = gilprobe.gil_roundtrip_seconds(2_000_000) / 2_000_000
    print(f"- raw GIL release/acquire round-trip: {rt * 1e9:.1f} ns")
    print()

    rows = []
    for k in range(0, KMAX + 1):
        py_t, nogil_t = measure(k, py_events, nogil_events)
        rows.append((k, _mean_sd(py_t), min(py_t), _mean_sd(nogil_t), min(nogil_t)))
    base_py, base_nogil = rows[0][1][0], rows[0][3][0]
    base_py_min, base_nogil_min = rows[0][2], rows[0][4]

    # Slowdown = mean time with K contenders / mean time with none.
    print("| K contenders | Python loop: mean s (sd) | slowdown | min-based |"
          " C/nogil: mean s (sd) | slowdown | min-based |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for k, (pm, psd), pmin, (nm, nsd), nmin in rows:
        print(f"| {k} | {pm:.3f} ({psd:.3f}) | {pm / base_py:.2f}x | "
              f"{pmin / base_py_min:.2f}x | {nm:.4f} ({nsd:.4f}) | "
              f"{nm / base_nogil:.2f}x | {nmin / base_nogil_min:.2f}x |")

    py_slow = rows[-1][1][0] / base_py
    nogil_slow = rows[-1][3][0] / base_nogil
    print()
    print(f"Contention slowdown at K={KMAX} (means): Python loop {py_slow:.2f}x, "
          f"C/nogil {nogil_slow:.2f}x.")
    if py_slow >= 1.8 and nogil_slow <= 1.3:
        print("RESULT: the interpreted loop slows under GIL contention and the "
              "C nogil loop does not. This probe varies only where the loop "
              "runs; it does not vary the system-call interface (see the "
              "factorial experiment in bench_matrix.py for that).")
    elif py_slow >= 1.8 and nogil_slow >= 1.8:
        print("RESULT: inconclusive -- both loops slow down, so the machine is "
              "short of cores rather than short of the GIL. Re-run with KMAX "
              "below the core count.")
    else:
        print("RESULT: GIL contention did not separate the two loops here.")


if __name__ == "__main__":
    main()
