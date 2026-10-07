#!/usr/bin/env python3
"""Control for the handler sweep: the benchmark handler called from plain
Python threads, with no server and no uringpy.

    HANDLER_WORK=300 python3 benchmarks/handler_thread_control.py

Prints, for 1, 2 and 4 threads, the mean time per call and the total calls per
second. On a GIL build the total stays flat (one thread runs at a time). On a
free-threaded build it shows whether this handler scales across threads in the
interpreter itself, which separates the interpreter's behaviour from the
runtime's in the handler-sweep results.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app_workload import handle_request  # noqa: E402

REQUEST = b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"
CALLS = int(os.environ.get("CALLS") or 20000)


def run(n, out):
    t = time.perf_counter()
    for _ in range(n):
        handle_request(REQUEST)
    out.append((time.perf_counter() - t) / n * 1e6)


def main():
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"python {sys.version.split()[0]} gil_enabled={int(gil)} "
          f"HANDLER_WORK={os.environ.get('HANDLER_WORK') or 0}")
    for n_threads in (1, 2, 4):
        out = []
        threads = [threading.Thread(target=run, args=(CALLS, out)) for _ in range(n_threads)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wall = time.perf_counter() - t0
        print(f"{n_threads} threads: us per call {sum(out) / len(out):.1f}  "
              f"calls per s {n_threads * CALLS / wall:.0f}")


if __name__ == "__main__":
    main()
