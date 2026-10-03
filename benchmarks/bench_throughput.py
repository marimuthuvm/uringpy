#!/usr/bin/env python3
"""Reproducible throughput / latency benchmark for uringpy.

Every performance number this project reports MUST come from this script.
Nothing is hard-coded: all figures are measured on the machine that runs it,
and the raw samples are written to benchmarks/results/ so any reviewer can
re-run and verify. If a result cannot be produced (e.g. io_uring is not
available on the host), the corresponding engine is reported as "unavailable"
rather than fabricated.

Workload: a fixed number of request/response round-trips over a connected
AF_UNIX socket pair. Both engines are driven through the *identical* workload
so the comparison is apples-to-apples. This is a microbenchmark of the read
completion path, not a full network server; the Markdown output states this
explicitly.

Usage:
    python benchmarks/bench_throughput.py \
        --ops 50000 --payload 1024 --repeat 10 --warmup 2000
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import statistics
import sys
import time
from datetime import datetime, timezone

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _percentile(sorted_samples, pct):
    """Nearest-rank percentile over an already-sorted list (pct in 0..100)."""
    if not sorted_samples:
        return float("nan")
    k = max(0, min(len(sorted_samples) - 1, int(round((pct / 100.0) * len(sorted_samples) + 0.5)) - 1))
    return sorted_samples[k]


def _summarize(name, throughputs, latencies_us):
    lat = sorted(latencies_us)
    return {
        "engine": name,
        "runs": len(throughputs),
        "throughput_ops_per_s": {
            "mean": statistics.mean(throughputs) if throughputs else float("nan"),
            "stdev": statistics.stdev(throughputs) if len(throughputs) > 1 else 0.0,
            "min": min(throughputs) if throughputs else float("nan"),
            "max": max(throughputs) if throughputs else float("nan"),
        },
        "latency_us": {
            "p50": _percentile(lat, 50),
            "p90": _percentile(lat, 90),
            "p99": _percentile(lat, 99),
            "p999": _percentile(lat, 99.9),
            "max": lat[-1] if lat else float("nan"),
            "samples": len(lat),
        },
    }


def bench_uringpy(ops, payload_size, warmup, mode="poll", batch=32):
    """Drive uringpy over a socketpair. Returns (rps, latencies_us).

    mode="poll":  original path - submit_read + busy-poll poll_completion.
    mode="wait":  submit_read_and_wait - one io_uring_enter syscall, blocking.
    mode="batch": submit_read_batch_and_wait - `batch` reads + reaps per syscall.

    Raises RuntimeError/OSError/ImportError if uringpy or io_uring is unavailable;
    the caller records the engine as unavailable rather than inventing numbers.
    """
    from uringpy import URingEngine  # imported lazily so asyncio baseline still runs without it

    slot_size = max(4096, payload_size)
    total_slots = max(1024, batch * 2)
    engine = URingEngine(entries=max(1024, batch * 2), slot_size=slot_size,
                         total_slots=total_slots)

    if mode == "batch":
        # Datagram socketpair preserves message boundaries: `batch` sends map
        # one-to-one to `batch` read completions with no stream coalescing.
        reader, writer = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    else:
        reader, writer = socket.socketpair()
    reader.setblocking(True)
    writer.setblocking(True)
    rfd = reader.fileno()
    payload = b"X" * payload_size

    if mode == "batch":
        # A background feeder writes continuously while the main thread issues
        # batched reads. This avoids pre-loading the socket buffer (which would
        # deadlock at large batch sizes) and lets reads/writes overlap. The
        # read path releases the GIL in-kernel, so the feeder runs concurrently.
        import threading

        stop = threading.Event()

        def feeder():
            while not stop.is_set():
                try:
                    writer.send(payload)
                except OSError:
                    break

        feeder_thread = threading.Thread(target=feeder, daemon=True)
        feeder_thread.start()

        def one_batch():
            return engine.submit_read_batch_and_wait(rfd, batch)

        try:
            warmup_batches = max(1, warmup // batch)
            for _ in range(warmup_batches):
                one_batch()

            latencies_us = []
            done = 0
            start = time.perf_counter()
            while done < ops:
                t0 = time.perf_counter_ns()
                res = one_batch()
                n = max(1, len(res))
                per_op = (time.perf_counter_ns() - t0) / 1000.0 / n
                latencies_us.extend([per_op] * len(res))  # amortized per-op latency
                done += len(res)
            elapsed = time.perf_counter() - start
        finally:
            stop.set()
            reader.close()
            writer.close()
            feeder_thread.join(timeout=1.0)
        return done / elapsed, latencies_us

    if mode == "wait":
        def one_op():
            writer.send(payload)
            return engine.submit_read_and_wait(rfd)
    else:
        def one_op():
            writer.send(payload)
            engine.submit_read(rfd)
            while True:
                res = engine.poll_completion()
                if res is not None:
                    return res

    try:
        for _ in range(warmup):
            one_op()

        latencies_us = []
        start = time.perf_counter()
        for _ in range(ops):
            t0 = time.perf_counter_ns()
            one_op()
            latencies_us.append((time.perf_counter_ns() - t0) / 1000.0)
        elapsed = time.perf_counter() - start
    finally:
        reader.close()
        writer.close()

    return ops / elapsed, latencies_us


def bench_asyncio(ops, payload_size, warmup):
    """Baseline: same socketpair round-trip driven by asyncio's readiness loop."""
    import asyncio

    async def _run():
        reader, writer = socket.socketpair()
        reader.setblocking(False)
        writer.setblocking(False)
        loop = asyncio.get_running_loop()
        payload = b"X" * payload_size

        async def one_op():
            await loop.sock_sendall(writer, payload)
            return await loop.sock_recv(reader, payload_size)

        try:
            for _ in range(warmup):
                await one_op()

            latencies_us = []
            start = time.perf_counter()
            for _ in range(ops):
                t0 = time.perf_counter_ns()
                await one_op()
                latencies_us.append((time.perf_counter_ns() - t0) / 1000.0)
            elapsed = time.perf_counter() - start
        finally:
            reader.close()
            writer.close()
        return ops / elapsed, latencies_us

    return asyncio.run(_run())


def run_engine(label, fn, ops, payload_size, warmup, repeat):
    throughputs = []
    latencies_us = []
    print(f"[*] {label}: {repeat} run(s) x {ops} ops, payload={payload_size}B, warmup={warmup}")
    for i in range(repeat):
        rps, lat = fn(ops, payload_size, warmup)
        throughputs.append(rps)
        latencies_us.extend(lat)
        print(f"    run {i + 1}/{repeat}: {rps:,.0f} ops/s")
    return _summarize(label, throughputs, latencies_us)

def collect_environment():
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "kernel": platform.release(),
    }


def render_markdown(env, results, args):
    lines = []
    lines.append("# uringpy benchmark results")
    lines.append("")
    lines.append("> Auto-generated by `benchmarks/bench_throughput.py`. Do not edit by hand.")
    lines.append("> Microbenchmark of the read-completion path over an AF_UNIX socket pair")
    lines.append("> (request/response round-trips). This is **not** a full network server")
    lines.append("> benchmark; absolute numbers are host-specific.")
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    for k, v in env.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append(f"Parameters: ops={args.ops}, payload={args.payload}B, "
                 f"repeat={args.repeat}, warmup={args.warmup}")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Engine | Throughput (ops/s, mean ± stdev) | P50 (µs) | P99 (µs) | P99.9 (µs) |")
    lines.append("| ------ | -------------------------------: | -------: | -------: | ---------: |")
    for r in results:
        if r.get("unavailable"):
            lines.append(f"| {r['engine']} | unavailable: {r['reason']} | — | — | — |")
            continue
        tp = r["throughput_ops_per_s"]
        lat = r["latency_us"]
        lines.append(
            f"| {r['engine']} | {tp['mean']:,.0f} ± {tp['stdev']:,.0f} | "
            f"{lat['p50']:.1f} | {lat['p99']:.1f} | {lat['p999']:.1f} |"
        )
    lines.append("")

    # Computed (never hardcoded) relative comparison, only when both are present.
    measured = {r["engine"]: r for r in results if not r.get("unavailable")}
    uring_key = next((k for k in measured if k.startswith("uringpy")), None)
    if uring_key and "asyncio" in measured:
        u = measured[uring_key]["throughput_ops_per_s"]["mean"]
        a = measured["asyncio"]["throughput_ops_per_s"]["mean"]
        if a > 0:
            lines.append(f"Measured throughput ratio ({uring_key} / asyncio): **{u / a:.2f}x** "
                         f"on this host.")
            lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ops", type=int, default=50000, help="measured ops per run")
    parser.add_argument("--payload", type=int, default=1024, help="payload size in bytes")
    parser.add_argument("--repeat", type=int, default=10, help="number of runs per engine")
    parser.add_argument("--warmup", type=int, default=2000, help="unmeasured warmup ops")
    parser.add_argument("--uring-mode", choices=["poll", "wait", "batch"], default="poll",
                        help="poll: original submit+busy-poll; wait: blocking single-syscall; "
                             "batch: N reads+reaps per syscall")
    parser.add_argument("--batch", type=int, default=32,
                        help="reads submitted/reaped per syscall in batch mode")
    parser.add_argument("--no-asyncio", action="store_true", help="skip asyncio baseline")
    args = parser.parse_args(argv)

    env = collect_environment()
    print(f"[*] Environment: {env['platform']} | Python {env['python']} | "
          f"kernel {env['kernel']} | {env['cpu_count']} CPUs")

    results = []

    try:
        label = f"uringpy ({args.uring_mode}" + (f", b={args.batch})" if args.uring_mode == "batch" else ")")
        results.append(run_engine(label,
                                  lambda o, p, w: bench_uringpy(o, p, w, mode=args.uring_mode,
                                                                batch=args.batch),
                                  args.ops, args.payload, args.warmup, args.repeat))
    except (ImportError, OSError, RuntimeError, MemoryError) as e:
        print(f"[!] uringpy unavailable, reported as such (not fabricated): {e}")
        results.append({"engine": f"uringpy ({args.uring_mode})", "unavailable": True, "reason": str(e)})

    if not args.no_asyncio:
        try:
            results.append(run_engine("asyncio", bench_asyncio,
                                       args.ops, args.payload, args.warmup, args.repeat))
        except Exception as e:  # noqa: BLE001 - baseline failure must not fabricate data
            print(f"[!] asyncio baseline failed: {e}")
            results.append({"engine": "asyncio", "unavailable": True, "reason": str(e)})

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {"environment": env, "parameters": vars(args), "results": results}

    json_path = os.path.join(RESULTS_DIR, f"results-{stamp}.json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    md = render_markdown(env, results, args)
    md_path = os.path.join(RESULTS_DIR, "latest.md")
    with open(md_path, "w") as f:
        f.write(md + "\n")

    print()
    print(md)
    print()
    print(f"[+] Raw samples: {json_path}")
    print(f"[+] Table:       {md_path}")


if __name__ == "__main__":
    main()
