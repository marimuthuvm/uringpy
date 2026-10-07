# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
"""
GIL-crossing probe for the completion-reaping bottleneck study.

What the probe shows
--------------------
The two extremes of the cost model in EXPERIMENTS.md: a loop that holds the
GIL for all of its work (f = 1) shares the lock with every competing thread,
and a loop that has released it (f = 0) is not slowed by them. It was written
for an earlier, broader hypothesis ("the loop must be in C to scale"), which
the server experiments did not support: what decides thread scaling there is
how often the GIL changes hands, and a loop in Python can scale. The probe
makes no system call and has no hand-offs to count, so it says nothing about
either; it remains as the illustration of f = 1 against f = 0.

The C path (`reactor_nogil`) reaps the whole batch inside one `nogil` region.
The status-quo path is a genuine *interpreted* Python loop and therefore lives
in the driver (gil_experiment.py), not here -- compiling it in Cython would
turn it into GIL-monopolising C and defeat the comparison. The per-event work
(`work_py` mirrors this splitmix64 step) is identical in both, so any
divergence under contention is attributable solely to where the loop runs.
"""

import time


cdef unsigned long long _work(unsigned long long acc, long ops) nogil:
    # Fixed, side-effect-free arithmetic standing in for per-completion decode
    # (a splitmix64 step). Cheap, deterministic, and impossible to optimise away
    # because the accumulator is returned to Python.
    cdef long i
    for i in range(ops):
        acc = acc * <unsigned long long>6364136223846793005ULL \
            + <unsigned long long>1442695040888963407ULL
    return acc


def reactor_nogil(long total_events, long ops_per_event):
    """Reap+decode every completion in C with the GIL released.

    The whole batch is processed inside a single `nogil` region, so contending
    Python threads run in true parallel on other cores -- this is the proposed
    "reap the batch in C, hand Python one aggregate" design. Returns
    (seconds, checksum).
    """
    cdef unsigned long long acc = 0
    cdef long e
    t0 = time.perf_counter()
    with nogil:
        for e in range(total_events):
            acc = _work(acc, ops_per_event)
    return time.perf_counter() - t0, acc


def gil_roundtrip_seconds(long iters):
    """Total seconds for `iters` GIL release/acquire round-trips (no other work).

    Establishes the raw marginal cost of a single crossing, to compare against
    the amortised per-completion syscall cost (io_uring_enter / ~199).
    """
    cdef long i
    t0 = time.perf_counter()
    for i in range(iters):
        with nogil:
            pass
    return time.perf_counter() - t0
