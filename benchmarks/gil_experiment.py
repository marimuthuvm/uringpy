#!/usr/bin/env python3
"""
Decisive experiment: is GIL contention -- not syscall count -- the wall for a
Python io_uring runtime?

Design
------
io_uring already amortises system calls (this project measures ~199 completions
per io_uring_enter), so syscalls are *not* the residual cost. The open question
for a *novel* contribution is what is: the hypothesis is that it is the work done
on the hot path while holding the GIL.

We process a fixed number of completions two ways while K CPU-bound Python
threads contend for the GIL:

    reactor_python  -- a genuine interpreted Python per-event loop (status quo:
                       every completion is dispatched in Python bytecode, as in
                       asyncio and the current uringpy server loop).
    reactor_nogil   -- identical arithmetic done in a C `nogil` region (proposed:
                       reap+decode the whole batch in C, hand Python one
                       aggregate -- a GIL-aware io_uring loop).

The per-event arithmetic is the same splitmix64 step in both; only *where the
loop runs* differs. So any divergence in how the two degrade as K grows is
attributable to the GIL, not to syscalls, allocation, or I/O.

Reading the result
------------------
We report each design's contention slowdown = time(K) / time(K=0).
  * If reactor_python inflates (~ (K+1)x, GIL time-sharing) while reactor_nogil
    stays flat, then interpreter-on-hot-path (GIL), not syscalls, is the wall --
    and moving completion reaping into C is a genuine, unstudied lever.
  * If both stay flat, the GIL is not the differentiator here -- pivot.

Run
---
    python3 benchmarks/setup_gilprobe.py build_ext --inplace   # once
    python3 benchmarks/gil_experiment.py                       # sweep

Env: EVENTS, OPS_PER_EVENT, KMAX, REPS.
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


def _best(fn, *args) -> float:
    # Best (min) of REPS runs: least perturbed by scheduler noise.
    return min(fn(*args)[0] for _ in range(REPS))


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


def measure(k: int, py_events: int, nogil_events: int) -> tuple[float, float]:
    """Return (python_seconds, nogil_seconds) with k background contenders."""
    stop = threading.Event()
    threads = [threading.Thread(target=_spin, args=(stop,), daemon=True)
               for _ in range(k)]
    for t in threads:
        t.start()
    try:
        reactor_python(py_events // 10, OPS_PER_EVENT)          # warm
        gilprobe.reactor_nogil(nogil_events // 10, OPS_PER_EVENT)  # warm
        py_s = _best(reactor_python, py_events, OPS_PER_EVENT)
        nogil_s = _best(gilprobe.reactor_nogil, nogil_events, OPS_PER_EVENT)
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
    print(f"- raw GIL release/acquire round-trip: {rt * 1e9:.1f} ns "
          f"(compare vs one io_uring_enter amortised over ~199 completions)")
    print()

    base_py = base_nogil = None
    rows = []
    for k in range(0, KMAX + 1):
        py_s, nogil_s = measure(k, py_events, nogil_events)
        if k == 0:
            base_py, base_nogil = py_s, nogil_s
        rows.append((k, py_s, py_s / base_py, nogil_s, nogil_s / base_nogil))

    print("| K contenders | Python-loop s (slowdown) | C/nogil s (slowdown) |")
    print("| ---: | ---: | ---: |")
    for k, ps, px, ns, nx in rows:
        print(f"| {k} | {ps:.3f} ({px:.2f}x) | {ns:.4f} ({nx:.2f}x) |")

    py_slow = rows[-1][2]
    nogil_slow = rows[-1][4]
    print()
    print(f"Contention slowdown at K={KMAX}: Python-loop {py_slow:.2f}x, "
          f"C/nogil {nogil_slow:.2f}x.")
    if py_slow >= 1.8 and nogil_slow <= 1.3:
        print("VERDICT: supported -- the interpreter-on-hot-path (GIL), not "
              "syscalls, is the wall. Moving completion reaping into C (a "
              "GIL-aware io_uring loop) is a genuine, unstudied lever. Next step: "
              "build the multi-worker sharded reactor and show it scales across "
              "cores where an asyncio-family loop cannot.")
    elif py_slow >= 1.8 and nogil_slow >= 1.8:
        print("VERDICT: inconclusive -- both degrade; contention looks "
              "core-bound rather than GIL-bound. Re-run with KMAX below the core "
              "count, or on the target VM, before concluding.")
    else:
        print("VERDICT: not supported -- GIL contention did not differentiate "
              "the designs here. The GIL-aware angle is weak; pivot to the "
              "zero-copy-through-a-framework or cost-model angle.")


if __name__ == "__main__":
    main()
