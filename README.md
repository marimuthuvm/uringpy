# uringpy
# uringpy

A **GIL-aware `io_uring` runtime for CPython**: it reaps completions and drives
the entire accept/recv/send protocol inside a single `nogil` C region, so that
worker threads scale across cores **within one interpreter** — where
`asyncio`-family event loops collapse under GIL contention.

> **Core finding.** Once `io_uring` amortizes system calls (we measure up to
> ~385 completions per `io_uring_enter`), the residual bottleneck for a Python
> async server is *interpreter execution on the hot path* (the GIL), **not** the
> system-call count. Keeping the completion hot path in C removes it.

## Headline results (isolated two-node, cloud VMs, idle 100% / steal 0%)

HTTP keep-alive echo, stock (GIL) CPython, scaling vs. worker count:

| Engine / model       | 1w   | 4w (scaling)             |
| -------------------- | ---- | ------------------------ |
| **uringpy / thread** | 147k | **269k (1.83×)**         |
| asyncio / thread     | 44k  | 18k (**0.47× collapse**) |
| asyncio / process    | 44k  | 70k (1.58×)              |

- uringpy is **~3.3× faster at a single worker** and is the *only* configuration
  that scales across cores **in one interpreter**.
- On **free-threaded** CPython (no GIL), `asyncio` thread-scaling recovers, yet
  uringpy is unchanged and still **~3.8× faster** absolute — because it never
  runs the interpreter on the hot path. The technique is durable across the
  GIL / free-threading transition.
- **Boundary (honest):** with real per-request Python work, single-interpreter
  thread scaling is lost for uringpy too (use process mode), though it degrades
  *gracefully* where `asyncio` *collapses*, and stays ~2.4× faster.

A manuscript describing the full methodology and measurements is in preparation.

## Architecture

- **Kernel interface:** Cython bindings to `liburing` submission/completion rings.
- **C-side reactor:** `URingEngine.serve_forever_echo()` runs the connection
  state machine in one `nogil` region — no per-completion Python object.
- **Sharding:** N workers, each its own ring + `SO_REUSEPORT` socket; the kernel
  shards connections. No shared mutable state, no cross-worker locks.
- **Free-threading safe:** the extension declares free-threading compatibility.

## Requirements

- Linux kernel ≥ 5.6 (echo path); `liburing` ≥ 2.3
- Python ≥ 3.9 (plus a free-threaded build for the no-GIL results)
- GCC / Clang

## Quick start

```bash
sudo apt-get install -y liburing-dev gcc
pip install -e .
pytest
```

## Reproduce the benchmarks

Every number comes from a re-runnable script.

```bash
# Build the container (io_uring needs an unrestricted seccomp profile)
docker build -t uringpy:gil .

# Single-node scaling matrix (uringpy vs asyncio, thread vs process)
docker run --rm --security-opt seccomp=unconfined uringpy:gil \
    bash benchmarks/scaling_matrix.sh

# GIL-vs-syscall isolation probe (no io_uring required)
python3 benchmarks/setup_gilprobe.py build_ext --inplace
python3 benchmarks/gil_experiment.py
```

Two-node (isolated load generator — the fair measurement) runs on any two Linux
hosts via [`benchmarks/twonode_bench.sh`](benchmarks/twonode_bench.sh) (set
`SERVER` / `SERVER_IP`). Free-threaded (no-GIL) image:
[`Dockerfile.freethreaded`](Dockerfile.freethreaded).

## Limitations

- Evaluated on one protocol, kernel, and CPU; tiny-response throughput is
  network/packet-rate bound (~270–290k req/s per VM).
- The multicore thread-scaling benefit applies to I/O-framing-dominated
  services; per-request Python logic requires process-level parallelism.
- Not a drop-in `asyncio` replacement — it is a specialized reactor.

## Citation

If you use this work, please cite it (see [`CITATION.cff`](CITATION.cff)).

## License

MIT — see [`LICENSE`](LICENSE).
