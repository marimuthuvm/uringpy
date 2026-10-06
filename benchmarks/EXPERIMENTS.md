# Experiments: what each one tests, how to run it, how every number is computed

This file is the reference for the measurements in the paper. Every table in the
paper comes from one experiment below, run by `benchmarks/bench_matrix.py`, and
every reported number is computed by the formulas in the last section. The raw
per-run data for each table is kept under `benchmarks/results/`.

## The claim under test

> For a Python `io_uring` server, where the per-event loop runs (in C with the
> GIL released, or in Python with it held) matters more than which system-call
> interface is used.

The criterion below was written down on the day of the measurements, while the
`factorial` runs were in progress; the commit that records it is later than
those runs, so it is not a pre-registered test:

- **Supported** if, in the `factorial` experiment, moving the loop from Python to
  C changes throughput far more than switching between `epoll` and `io_uring`,
  **and** in the `batch` experiment, capping the completions handled per
  `io_uring_enter` changes throughput little.
- **Not supported** otherwise; the paper then reports what the data shows.

Outcome: met in part. The first condition holds at four workers and fails at
one; the second holds for caps of 16 and above. The claim as worded above is
therefore not supported for a single worker. What the data supports is narrower
(the interface and batching set one worker's speed; loop placement and GIL
handling decide whether worker threads scale), and that narrower claim was
formulated after seeing the results.

## Setup

Two machines in one zone: a client that generates load and a server that runs
the code under test in a Docker container. The driver runs on the client and
controls the server over ssh.

| | Server | Client |
| --- | --- | --- |
| Role | runs `benchmarks/sharded_server.py` in Docker | runs `bench_matrix.py` and `wrk` |
| Needs | Docker, the benchmark images | python3, wrk, ssh access to the server |

Images, both built from `Dockerfile.bench` so they differ only in `--disable-gil`:

```bash
docker build -f Dockerfile.bench -t uringpy:314 .                                  # CPython with the GIL
docker build -f Dockerfile.bench --build-arg FREE_THREADED=1 -t uringpy:314t .     # free-threaded
```

The machine types, kernel, CPU model, interpreter version, image id, git commit
and random seed of every experiment are recorded in its `meta.json`. Prefer
machine types where one vCPU is one physical core; with hyper-threads, "4
workers on 4 vCPUs" is only 2 cores.

## Experiments

Run each with `python3 benchmarks/bench_matrix.py --experiment <name>` on the
client, with `SERVER`, `SERVER_IP` and `IMAGE` set (see the README).

| Name | Question it answers | Engines | Modes | Workers | Swept |
| --- | --- | --- | --- | --- | --- |
| `scaling` | Does throughput grow with workers in one interpreter, and how does that compare with one process per worker? | uringpy, asyncio, asyncio-proto | thread, process | 1, 2, 4 | — |
| `factorial` | Is the gain from the system-call interface or from where the loop runs? | uringpy, c-epoll, py-uring, py-epoll, and py-uring-held for comparison | thread | 1, 2, 4 | — |
| `batch` | How much does batching completions per system call contribute? | uringpy | thread | 1 | batch cap 1, 4, 16, 64, 256, none |
| `app` | What happens once every request runs Python code? | uringpy-app, uringpy-app-batch, asyncio-app, asyncio-proto-app, uvloop-proto-app | thread, process | 1, 2, 4 | — |
| `handler` | How does thread scaling depend on how long each request holds the GIL, and on how often the GIL changes hands? | uringpy-app, uringpy-app-batch | thread, process | 1, 2, 4 | handler work 0 … 3000 iterations |
| `size` | Where does the advantage end as responses grow? | uringpy, asyncio-proto | process | 4 | body 64 B … 1 MiB |
| `baselines` | How do other event loops and the faster asyncio API compare? | asyncio, asyncio-proto, uvloop, uvloop-proto | thread, process | 1, 4 | — |

The 2x2 design of `factorial`:

| | loop in C, GIL released | loop in Python, GIL held |
| --- | --- | --- |
| `io_uring` | `uringpy` | `py-uring` |
| `epoll` | `c-epoll` | `py-epoll` |

All engines answer each `recv()` with the same bytes and none parses HTTP, so
they differ only in how the I/O loop is built. One difference between the two
Python loops is not the interface and has to be kept in mind: `py-epoll` makes
its system calls through CPython's socket objects, which release the GIL around
each call, and `py-uring` releases it while waiting for completions and while
submitting. `py-uring-held` is `py-uring` keeping the GIL while it submits (the
kernel performs the queued sends inside that call), which is how `py-uring`
behaved in the runs of 2026-10-06 made at commit `b60fe24`. It is run next to
the 2x2 to show what that choice alone does. Defaults: 5 repetitions of 20 s
after a 5 s warm-up, 400 keep-alive connections, one `wrk` thread per client
CPU. Repetitions are interleaved: every cell is run once in shuffled order, then
every cell again, with a fresh server process for every run.

## Output

Each experiment writes `benchmarks/results/<experiment>-<image>-<UTC time>/`:

| File | Content |
| --- | --- |
| `runs.csv` | one row per run: the raw data |
| `meta.json` | machines, software versions, parameters, seed, cell list |
| `summary.md` | one row per cell, computed from `runs.csv` by the formulas below |

`python3 benchmarks/bench_matrix.py --summarize <folder>` rebuilds `summary.md`
from `runs.csv`, so every summary number can be re-derived from the raw data.

Columns of `runs.csv` that the formulas use:

| Column | Source | Meaning |
| --- | --- | --- |
| `rps` | wrk | requests per second over the measured 20 s |
| `lat_p50_ms`, `lat_p99_ms` | wrk | latency percentiles (closed-loop; see Limits) |
| `server_cpu_pct`, `client_cpu_pct` | `/proc/stat` before and after the run | whole-machine busy share |
| `server_max_core_pct` | `/proc/stat` | busy share of the busiest single core |
| `srv_requests` | server counters | responses sent in full |
| `srv_syscalls`, `srv_enters`, `srv_completions` | server counters | system calls, `io_uring_enter` calls, completions |
| `srv_cpu_ns` | server | user + system CPU time of the server processes |
| `srv_handler_calls`, `srv_gil_hold_ns`, `srv_gil_wait_ns` | server counters | handler calls and time spent holding / waiting for the GIL |
| `srv_gil_acquires` | server counters | GIL acquisitions made for handler calls: equal to the calls for `uringpy-app`, fewer for `uringpy-app-batch` |
| `srv_python`, `srv_gil` | server | interpreter version and GIL state at start-up |

Server counters cover the server's whole life, warm-up included. Ratios of two
server counters are therefore consistent; they are never divided by wrk's
request count.

## Published results and tables

The runs behind the reported numbers are kept in `benchmarks/results/`, one
folder per experiment and interpreter (`...-314-...` is the GIL build,
`...-314t-...` the free-threaded build). `benchmarks/make_tables.py` reads every
such folder and writes the result tables:

```bash
python3 benchmarks/make_tables.py                    # LaTeX tables -> benchmarks/results/tables/
python3 benchmarks/make_tables.py --out paper/tables # or wherever the manuscript reads them
python3 benchmarks/make_tables.py --dump             # every configuration as text
```

It uses the statistics functions of `bench_matrix.py`, so a table and a
`summary.md` cannot disagree, and each generated file starts with the folders,
commit and image it was computed from. Folders of the same experiment are
pooled, so a trial or an aborted run must not be left in `benchmarks/results/`.

| Table | Experiment(s) | Shows |
| --- | --- | --- |
| `tab_factorial`, `tab_effects` | `factorial` | the 2x2 design, and each factor's effect with the other held fixed |
| `tab_batch` | `batch` | throughput against the batch cap |
| `tab_scaling` | `scaling` (both builds), `baselines` | throughput at 1 to 4 workers, scaling, busy cores |
| `tab_app` | `app` (both builds) | the same with a Python handler per request |
| `tab_size` | `size` | throughput and data rate against response size |

How the published runs differ from the presets above:

- `scaling` was run with `--workers "1 2 3 4"` (the preset is 1, 2, 4).
- `baselines` was run with `--engines "uvloop uvloop-proto"`, because the two
  `asyncio` engines were already in `scaling`.
- The runs of 2026-10-06 up to and including `size` were made at commit
  `b60fe24`, before the `handler_work`, `srv_cpu_ns`, `srv_handler_calls`,
  `srv_gil_hold_ns` and `srv_gil_wait_ns` columns existed, so their `runs.csv`
  files do not have them. Each `meta.json` records the commit and image used.

Comparisons inside one experiment are interleaved. Comparisons across two
experiments are not: one `uringpy` worker measured 140.7, 146.1 and 144.0
thousand requests per second in three experiments, a spread of 4%. Comparisons
between the GIL build and the free-threaded build are also across experiments.

## Formulas

For a cell with `n` successful runs and throughputs `x_1 … x_n`:

- **Mean**: `m = (x_1 + … + x_n) / n`
- **Standard deviation**: `s = sqrt( sum((x_i - m)^2) / (n - 1) )`
- **95% confidence half-width**: `h = t(0.975, n-1) * s / sqrt(n)`, with `t` the
  Student-t quantile (2.776 for `n = 5`). Reported as `m ± h`.
- **Coefficient of variation**: `CV = 100 * s / m` (percent)

Scaling of a cell with `N` workers against the 1-worker cell of the same engine
and mode (means `m_N`, `m_1`; standard deviations `s_N`, `s_1`; run counts
`n_N`, `n_1`):

- **Scaling**: `S = m_N / m_1`
- **Its 95% half-width** (first-order error propagation for a ratio):
  `h_S = t(0.975, min(n_N, n_1) - 1) * S * sqrt( (s_N / (sqrt(n_N) * m_N))^2 + (s_1 / (sqrt(n_1) * m_1))^2 )`

CPU use between two `/proc/stat` samples, with `busy = total - idle - iowait`:

- **Busy share**: `100 * (busy_after - busy_before) / (total_after - total_before)`
- **Busy cores**: `C = cores * busy share / 100`
- **Throughput per busy core**: `m / C`. This is reported next to `S` because a
  1-worker run on a multi-core server also uses other cores for kernel network
  work, which makes `S` alone understate per-core scaling.
- **Per-core efficiency at `N` workers** (in `make_tables.py`):
  `E_N = (m_N / C_N) / (m_1 / C_1)`, so that `S = E_N * C_N / C_1`. `E_N < 1`
  in process mode, where no lock is shared, is a property of the machine.

Any other ratio of two cells (for example `io_uring` over `epoll`, or threads
over processes) is computed as `m_a / m_b` with the same half-width formula as
`S`.

Per-request costs, from the server's own counters summed over a cell's runs:

- **System calls per request**: `srv_syscalls / srv_requests`
- **Completions per `io_uring_enter`**: `srv_completions / srv_enters`
- **Process CPU per request**: `srv_cpu_ns / srv_requests`
- **GIL hold per request**: `t_p = srv_gil_hold_ns / srv_handler_calls`
- **GIL wait per request**: `w = srv_gil_wait_ns / srv_handler_calls`
- **GIL acquisitions per request**: `srv_gil_acquires / srv_handler_calls`

GIL bound on thread scaling. Take a request to cost `t_c` of CPU with the GIL
released and `t_p` with it held, both measured at one worker (`t_c` = process
CPU per request minus `t_p`). The GIL-held fraction is

- `f = t_p / (t_c + t_p)`

`N` worker threads in one interpreter can run their `t_c` parts in parallel but
only one `t_p` part at a time, so

- **Bound**: `S(N) <= min(N, 1 / f)`

`f = 0` (no Python on the hot path) gives `S(N) <= N`; `f = 1` (everything under
the GIL) gives `S(N) <= 1`. In `make_tables.py`, `f = t_p * m_1`, with `t_p`
measured at one worker and `m_1` the one-worker throughput (a saturated worker
serves `1 / (t_c + t_p)` requests per second).

The bound is an upper bound and can be far from tight. With the default handler
it is about 7 while measured thread scaling stops at 1.57: what it leaves out is
the cost of acquiring a contended lock once per request, which the measured
wait `w` shows directly. `uringpy-app-batch` (`URingEngine.set_gil_batching`)
tests that reading: it takes the GIL once for all requests found in one pass
over the completion queue, which leaves `f` unchanged and cuts the number of
acquisitions per request. In
process mode each worker has its own GIL, so the bound is `N` whatever `f` is.

## Pitfalls and how each is handled

Each row is a way a benchmark of this kind can mislead, what is done about it
here, and where a reader can check.

| Pitfall | What is done | Where to check |
| --- | --- | --- |
| The load generator, not the server, is the limit | The client has twice the server's cores; client CPU is recorded for every run and cells above 85% are flagged | `client_cpu_pct`, flags column |
| Hyper-threads counted as cores | Machine types with one vCPU per physical core; the type is recorded | `meta.json` |
| Noise mistaken for an effect | 5 repetitions, interleaved in shuffled order, a fresh server per run, 95% confidence intervals, a flag when `CV` exceeds 5% | `± 95% CI`, `CV %` |
| A weak baseline | `asyncio` through both its streams and its faster Protocol API; `uvloop`; the same interpreter version for every engine | `scaling`, `baselines` |
| GIL vs. free-threaded confounded by different builds | Both interpreters come from one recipe that differs only in `--disable-gil`; the GIL state the server reports is recorded per run | `Dockerfile.bench`, `GIL` column |
| Crediting `io_uring` for what C code does, or the reverse | The 2x2 design varies the two factors separately; the batch cap varies batching alone | `factorial`, `batch` |
| System-call counts estimated, not measured | Both C reactors count their system calls and completed requests exactly | `syscalls/req`, `compl/enter` |
| The 1-worker baseline quietly uses other cores for kernel network work | Server CPU is recorded; throughput per busy core is reported next to the scaling ratio | Formulas, `server_cpu_pct` |
| A model fed with assumed numbers | Time holding the GIL and time waiting for it are measured per request | `handler`, `GIL hold`, `GIL wait` |
| Engines doing different amounts of protocol work | Every engine answers each `recv()` with identical bytes; none parses HTTP | `sharded_server.py` |
| Errors hidden inside a throughput figure | Socket errors, non-2xx responses, handler errors and failed runs are recorded and flagged | flags column, `status` |
| Numbers that cannot be traced to code | Git commit, image id, interpreter version and random seed per experiment; raw runs kept; summaries regenerable | `meta.json`, `runs.csv` |

What is not handled is listed under Limits and stated in the paper.

## Limits

- `wrk` is a closed-loop generator. Its latency figures describe latency at the
  offered load and suffer from coordinated omission; they compare configurations
  at equal load and are not tail-latency estimates.
- A cell is flagged when the client's busy share exceeds 85%, because the load
  generator may then be the limit, and when `CV` exceeds 5%.
- The engines reply once per `recv()` and do not parse HTTP: no pipelining, no
  fragmented requests. `py-uring` and `py-epoll` send each response with one
  `send`, so they are used only with small responses.
- One protocol, one kernel, one machine family, and a server with few cores.
- The server's four cores are shared by the workers and the kernel's network
  stack: one worker already keeps about 1.2 cores busy, so scaling at four
  workers is about 2.3 to 2.7 for every engine that scales at all.
- With response bodies of 16 KiB or more the network path (about 15.7 Gbit/s
  between the two machines) was the limit, not the server; those `size` cells
  measure the network.
- `py-uring` and `py-epoll` are bare dispatch loops without `asyncio`'s task and
  transport machinery, so the loop-placement effect they show at one worker is a
  lower bound for a full event loop.
- Repetitions are interleaved within an experiment, not across experiments (see
  "Published results and tables").
