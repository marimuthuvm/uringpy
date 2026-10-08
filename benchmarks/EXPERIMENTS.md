# Experiments: what each one tests, how to run it, how every number is computed

This file is the reference for the measurements in the paper. Every table in the
paper comes from one experiment below, run by `benchmarks/bench_matrix.py`, and
every reported number is computed by the formulas in the last section. The raw
per-run data for each table is kept under `benchmarks/results/`.

## The claim under test, and how it changed

> Under the GIL, whether worker threads of one interpreter scale is decided by
> how much of a request runs with the GIL held and by how often the GIL changes
> hands per request. The system-call interface and the language of the loop
> matter to scaling mainly through those two.

This is not the claim the work started from. The order of events:

1. **A broader hypothesis.** "For a Python `io_uring` server, where the
   per-event loop runs (in C with the GIL released, or in Python with it held)
   matters more than which system-call interface is used." Its criterion was
   written down on the day of the first measurements, while the `factorial` runs
   were in progress, so it was not pre-registered: supported if moving the loop
   from Python to C changes throughput far more than switching between `epoll`
   and `io_uring`, and capping the completions handled per `io_uring_enter`
   changes throughput little.
2. **A wrong conclusion.** In the first `factorial` run the Python loop on
   `io_uring` did not scale across threads, and we concluded that a loop in
   Python cannot scale. The loop held the GIL during its submitting system call,
   in which the kernel performs the queued sends; nothing required that. Those
   runs are kept under `benchmarks/results/superseded/`, and the faulty variant
   is kept as the engine `py-uring-held`.
3. **The criterion is not met.** With the GIL released around that call, the
   Python loop on `io_uring` scales nearly as well as the C loop. At one worker
   the interface and the placement of the loop matter about equally. The claim
   at the top of this section was formulated after seeing these results.
4. **Tests of the new claim.** Three experiments were then designed to test it:
   `py-epoll-batch` (GIL releases reduced with the interface and the system
   calls unchanged), `c-epoll-app-batch` (GIL batching on an `epoll` reactor),
   and `gilbatch` (requests per GIL acquisition varied in steps). The prediction
   for the first, and what would refute it, is written under "Experiments"
   below, in the commit at which all current results were measured.
5. **Outcome.** All experiments were run together at that commit (`5db4eab`).
   The prediction for `py-epoll-batch` held: with the interface and the system
   calls of `py-epoll` and its GIL releases made per pass instead of per system
   call it scales like `py-uring`.
   GIL batching restores thread scaling for the `epoll` reactor as it does for
   the `io_uring` reactor, and in `gilbatch` scaling rises step by step as fewer
   acquisitions are made per request. One thing was not expected. The two
   reactors that take the GIL once per request have the same count of
   acquisitions and scale very differently, and the voluntary context switches
   differ with them. A count of releases or acquisitions is therefore an upper
   limit on hand-offs, and context switches per request are reported next to
   it.
6. **How far the claim goes.** Hand-offs of the GIL were not observed: the lock
   was not traced. They are inferred from counters (releases, acquisitions,
   voluntary context switches) and from interventions that change how often the
   GIL is given up. The data support the claim as an ordering of
   configurations, not as a formula that predicts scaling: the hand-off cost
   derived from it differs from one handler size to the next. Everything was
   measured on a four-core server under saturating closed-loop load, where
   on the transport path even processes scale by only 2.3 to 2.7. A supplementary run on the same
   images added 1600 connections and three handler sizes; its expectations
   were written down before it ran and were weak ones. The `asyncio` loops
   built on `io_uring` that motivated the work could not be measured on
   Python 3.14.

The numbers are in the generated tables (`benchmarks/results/tables/`) and in
the paper. The few repeated in this file were copied from `numbers.tex`.

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

`bash benchmarks/run_paper_experiments.sh` runs all of them for the paper at the
checked-out commit: it refuses to start if tracked files differ from that
commit, sends the commit to the server, builds both images from it there
(`uringpy:<commit>` and `uringpy:<commit>t`), runs the test suite inside each
image and stops if it fails, runs the contention probe and the handler thread
control, and then the experiments on both builds. All result folders of one
such run therefore carry one commit in their name and in `meta.json`.

| Name | Question it answers | Engines | Modes | Workers | Swept |
| --- | --- | --- | --- | --- | --- |
| `scaling` | Does throughput grow with workers in one interpreter, and how does that compare with one process per worker? | uringpy, asyncio, asyncio-proto, uvloop, uvloop-proto | thread, process | 1, 2, 3, 4 | — |
| `factorial` | Is the gain from the system-call interface or from where the loop runs? And is it the number of GIL hand-offs that decides thread scaling, with the system calls unchanged? | uringpy, c-epoll, py-uring, py-epoll, py-epoll-batch, py-uring-held | thread, process | 1, 2, 4 | — |
| `batch` | How much does batching completions per system call contribute? | uringpy | thread | 1 | batch cap 1, 4, 16, 64, 256, none |
| `app` | What happens once every request runs Python code, and does taking the GIL once per batch help an `epoll` reactor as much as an `io_uring` one? | uringpy-app, uringpy-app-batch, c-epoll-app, c-epoll-app-batch, asyncio-app, asyncio-proto-app, uvloop-proto-app | thread, process | 1, 2, 4 | — |
| `gilbatch` | Does thread scaling follow the number of requests served per GIL acquisition? | uringpy-app, uringpy-app-batch1 … batch64, uringpy-app-batch | thread | 1, 2, 4 | at most 1, 2, 4, 8, 16, 64 or all pending requests per acquisition |
| `handler` | How does thread scaling depend on how long each request holds the GIL, and where do worker threads stop paying against one process per worker? | uringpy-app, uringpy-app-batch (threads and processes); asyncio-proto-app, uvloop-proto-app (processes, 1 and 4 workers) | thread, process | 1, 2, 4 | handler work 0 … 3000 iterations |
| `load` | Do the results hold at other loads than 400 connections? | uringpy, py-uring, py-epoll, uringpy-app, uringpy-app-batch | thread | 1, 4 | 16, 64, 400, 1600 connections (the 1600-connection runs that count are those of the supplementary run, see below) |
| `size` | Where does the advantage end as responses grow? | uringpy, asyncio-proto | process | 4 | body 64 B … 1 MiB |
| `loops` | How do the `asyncio` event loops built on `io_uring` behave as threads and as processes? Run by `run_supplement.sh` on an image that adds the two packages to the image of the main run (built by `run_loops_experiment.sh`). Neither loop could be measured on Python 3.14; see "Outcome" below. | asyncio, uvloop, uringcore, uringloop | thread, process | 1, 2, 4 | — |
| `baselines` | How do other event loops and the faster asyncio API compare? (now part of `scaling`) | asyncio, asyncio-proto, uvloop, uvloop-proto | thread, process | 1, 4 | — |

### Supplementary run (`run_supplement.sh`)

Two limits of the server container got in the way of the main run. A process in
it could hold 1024 open files, fewer than the 1600 connections of the heaviest
`load` cells, and it could lock too little memory for `uringcore` to register
its buffers. A first attempt at the `loops` experiment on 2026-10-07 (image
`uringpy:5db4eab-loops`) could therefore start neither `io_uring` loop:
`uringcore` failed with `register_buffers failed: Cannot allocate memory`, and
`uringloop` with `module 'asyncio.unix_events' has no attribute
'AbstractChildWatcher'`, an `asyncio` API that Python 3.14 has removed. That
attempt measured `asyncio` and `uvloop` only (60 runs) and is not used.

`bash benchmarks/run_supplement.sh` repeats what the limits spoiled and adds
one sweep. It rebuilds nothing: for `load` and `handler` the server runs the
image of the main run, and for `loops` the image that the first attempt had
built on top of it (`uringpy:5db4eab-loops`, which adds `uringcore` and
`uringloop`). The only difference from the main run is
`--ulimit nofile=65536:65536 --ulimit memlock=-1:-1` on `docker run`, passed through the driver's `--docker-opts` and recorded in
every `meta.json`. The script logs the container's default limits, so the
limits of the main run are on record too.

| Stage | What is run | Expectation, written before the run |
| --- | --- | --- |
| `load`, 1600 connections | the five engines of `load`, 1 and 4 threads | The engines fall in the same order as with 400 connections. The engines that batch give up the GIL no more often per request than with 400 connections, and `py-epoll` stays below the throughput of one worker. |
| `loops` | `asyncio`, `uvloop` and `uringcore` under the same streams server, threads and processes, 1, 2 and 4 workers (`uringloop` only if it starts, which is not expected on Python 3.14) | `uringcore` delivers every event to Python callbacks, as any `asyncio` loop must, so most of a request runs under the GIL. By the bound `1/f` its four threads cannot come near its four processes: we expect thread scaling below 1.5 and process scaling like that of the other loops. Whether the threads fall below one worker depends on how often they sleep: with more than one voluntary context switch per request we expect a loss, as for `asyncio` and `uvloop`; with few, about the throughput of one worker, as for `py-uring-held`. |
| `handler`, 5, 10 and 20 added iterations | `uringpy-app` and `uringpy-app-batch` as threads and processes, the two baselines as processes, 1 and 4 workers | The ratio of batched threads to processes at four workers falls steadily between its values for 0 and for 30 added iterations in the main run. |

`make_tables.py` keeps the 1600-connection runs of this run and leaves out those
of the main run (rule `EXCLUSIONS`: 1600 connections without a raised
open-file limit).

Outcome. The first and the third expectation held (`tab_load`, `tab_handler`).
The `loops` stage did not measure `uringcore`: with the limit on locked memory
raised it started and answered single requests, but all 30 of its runs failed.
With its default buffer pool it raises `RuntimeError: No buffers available`
once a few hundred connections are open, the error ends its event loop, and
the server process exits. Those runs are kept under
`benchmarks/results/superseded/`.

`bash benchmarks/run_loops_experiment.sh` was the third attempt. It gives
`uringcore` a larger buffer pool through the `buffer_count` parameter of its
engine (`URINGCORE_BUFFER_COUNT`, 4096 by default; see `_new_loop` in
`sharded_server.py`), keeps both raised limits, and before measuring checks
that the loop serves 400 connections in four short trial runs. Only one of the
four trial runs succeeded, so the script stopped, as written, and measured
nothing.

A last check sent requests one after another on a single connection. The
server answered 997 of them with its default pool and 4069 with a pool of 4096
buffers, and then reported `No buffers available`: with either pool it serves
a number of requests close to the size of the pool. That explains the
30 failed runs and the failed trial (the first attempt had failed earlier, at
start-up, on the limit on locked memory), and a still larger pool would only
move the point at which it stops.
We did not look for the cause inside the package. `uringcore` 0.9.1 states
that it is tested on Python 3.10 to 3.13, and these runs used 3.14.7.
`uringloop` 0.1.0 does not start on 3.14 at all.

So neither `io_uring`-based `asyncio` loop is part of the results, the second
expectation in the table above was never tested, and the paper says so. What
the checks printed is recorded in
`benchmarks/results/superseded/uringcore-checks-5db4eab-20261007.txt`. Nothing
here says anything about either package on the Python versions it supports.

### Revision experiments (`run_revision.sh`)

A review of the paper raised three objections that the data above cannot
answer: GIL hand-offs were inferred and never observed; everything ran on a
four-core server; and the `io_uring` event loops that motivate the work were
not measured. `bash benchmarks/run_revision.sh` adds one measurement for each,
and one more for a fourth gap: every result above is at saturation, where
latency follows from throughput, so nothing says what batching costs in
latency at the loads a server normally runs at.
Its results go to `benchmarks/results-revision/`, apart from the folders
above, and change none of the numbers above.

**Observed hand-offs.** CPython counts, inside the GIL, every acquisition by a
thread other than the lock's previous holder (`switch_number`, incremented in
`take_gil()`). `uringpy._gilstat.switch_count()` reads that counter, and every
server process reports it at exit (`gil_switches=` on its `[proc]` line,
`srv_gil_switches` in `runs.csv`). It is a count of hand-offs made by the
interpreter itself, not an upper limit inferred from releases. It is read
once, at exit, and costs nothing per request.

| Stage | Machine | What is run |
| --- | --- | --- |
| `h-factorial`, `h-app`, `h-gilbatch`, `h-handler` (`PROFILE=small`) | the four-core server of the main run | the thread-mode configurations of `factorial`, `app` and `gilbatch` (`gilbatch` at 1 and 4 workers), and `handler` for both reactors at 0 to 100 added iterations, threads at 1 and 4 workers; 400 connections, 5 repetitions, as in the main run |
| `check313`, `loops313`, `app313` (`PROFILE=small`) | the same | an image built from `Dockerfile.bench` with CPython 3.13, plus `uringcore` and `uringloop` (`Dockerfile.loops`). `check_loop.py` first tests each loop: one connection with 20,000 requests one after another, then 400 connections with 3 requests each. The loops that pass are measured against `asyncio`, `uvloop` and `uringpy` (streams and Protocol API, threads and processes, 1, 2 and 4 workers), and with the handler (Protocol API, 1 and 4 workers) |
| `L-scaling`, `L-factorial`, `L-app`, `L-handler` (`PROFILE=large`) | the same VMs resized to a server with more cores (8 or 16) and a client with twice as many | `scaling` (the runtime and the two Protocol API baselines), `factorial`, `app` and `handler` (0, 10, 30 and 100 added iterations) at 1, 4 and all cores, threads and processes, 100 connections per server core |
| `L-openloop` (`PROFILE=large`) | the same | open loop: `wrk2` (built on the client; its commit is logged) sends requests at fixed total rates of 50, 100, 150, 200, 300 and 400 thousand per second (and 600 thousand with 16 cores) to the default handler on all cores: the reactor with the GIL taken per request (threads), with GIL batching (threads and processes), and `uvloop` (processes, Protocol API). Runs of 30 s; latency percentiles are corrected for coordinated omission by `wrk2`. Results in `benchmarks/results-revision/large-openloop/` |

Expectations, written before any of these runs (`ĝ` is the counted upper
limit used so far, `gsw` the observed hand-offs per request):

1. **Observed hand-offs, four cores.**
   a. At four threads, the configurations that give up the GIL at every system
      call or every request (`py-epoll`, `c-epoll-app`, `uringpy-app`,
      `asyncio`, `uvloop` and their Protocol and handler variants) show at
      least 0.3 observed hand-offs per request; those that give it up once per
      pass or batch (`py-uring`, `py-epoll-batch`, `uringpy-app-batch`,
      `c-epoll-app-batch`) fewer than 0.1; the C loops without Python
      (`uringpy`, `c-epoll`) fewer than 0.01.
   b. The order holds without overlap: every four-thread configuration with
      `S_4 >= 2` has fewer observed hand-offs per request than every one with
      `S_4 < 1`.
   c. The two reactors that take the GIL once per request (`ĝ = 1` for both)
      differ in observed hand-offs: `c-epoll-app` shows more per request than
      `uringpy-app`. If they show the same, the paper's explanation of why the
      two scale so differently (0.70 against 1.61) is wrong.
   d. In the cap sweep (`gilbatch`), observed hand-offs per request fall as
      the cap rises, as the counted acquisitions do.
   e. Every configuration repeated from the main run delivers within 5% of its
      main-run throughput: the new image changes nothing else.
2. **More cores** (`W` = the server's cores).
   a. Processes scale beyond four workers: `S_W` of `uringpy` processes is
      larger than `S_4`.
   b. With no Python per request, `uringpy` threads stay within 10% of
      `uringpy` processes at `W` workers.
   c. With the default handler and GIL batching, threads at `W` workers deliver
      no more than the lock capacity `1 / t_p,W` measured in the same runs, and
      a smaller fraction of what the same reactor's processes deliver than
      at four workers in the main run (0.93). From the main run the lock
      saturates near 420 thousand requests per second on this handler.
   d. The designs that give up the GIL per request or per system call
      (`c-epoll-app`, `uringpy-app`, `py-epoll`) scale no better as threads at
      `W` workers than at four.
   e. Expectation 1b holds at `W` workers as well.
3. **`uringcore` and `uringloop` on Python 3.13.**
   a. If a loop fails `check_loop.py`, it is reported as unusable for this
      load on a version it supports, with the check's output, and not measured.
   b. A loop that passes runs a Python callback for every event, as `asyncio`
      and `uvloop` do. At four threads it shows at least 0.3 observed
      hand-offs per request and scales below 1.5, while its processes scale
      within 15% of the other loops' processes.
   c. Any advantage it has on one worker does not survive across threads: at
      four threads it is slower than four `uringpy` threads and than four of
      its own processes.
   d. `uringpy` on 3.13 shows the pattern it shows on 3.14: its threads come
      within 10% of its processes at four workers.
4. **Open loop** (added on 2026-10-08 while the `PROFILE=small` run was in
   progress, before any open-loop run).
   a. At 50 and 100 thousand requests per second, where batches are small,
      the median and 99th-percentile latency of batched threads are within 25%
      of those of the threads that take the GIL per request: batching costs
      little latency at light load.
   b. As the rate rises, the per-request threads fall behind first: there is a
      rate that they no longer sustain (achieved below 95% of offered) and
      batched threads still do, and below that rate their tail latency rises
      faster than that of batched threads.
   c. Batched threads stop sustaining the offered rate near the lock capacity
      measured in the closed-loop runs on the same machine; the processes of the
      same reactor sustain the highest rates of the four configurations.

Outcome of the `PROFILE=small` run at commit `4780b0e` (2026-10-08, all
625 runs succeeded). The check on Python 3.13.7 (`small-py313/loopcheck-*.txt`):
`asyncio` and `uvloop` passed. `uringcore` 0.9.1, on a version it states it
supports, failed as on 3.14: one connection was answered 996 times (992 with
the Protocol API) before the loop reported `No buffers available for recv`,
and 400 connections received 575 of 1200 replies. Expectation 3a applies, and
`uringcore` was not measured. `uringloop` was not tested: the server's loader
looked for its loop class under names that version 0.1.0 does not use
(`IouringProactorEventLoop` is the one it exports), so the server did not
start. That was our error, not the package's. The loader was corrected and the
check repeated at the next commit (stages `build313` and `check313`).

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
submitting. So for these two loops the number of system calls and the number of
GIL releases are the same quantity, and the 2x2 alone cannot tell which of the
two decides thread scaling. Two further engines separate them:

| Engine | System calls per request | GIL releases per request | What it tests |
| --- | --- | --- | --- |
| `py-epoll-batch` | as `py-epoll` (`epoll_wait`, `recv`, `send`) | about two per loop pass: one for `epoll_wait`, one for all the `recv` and `send` calls of that pass, made by `uringpy.BatchIO` with the GIL released | same interface and same system calls as `py-epoll`, fewer hand-offs |
| `py-uring-held` | as `py-uring` | one per loop pass: the wait only; the submit keeps the GIL | same interface as `py-uring`, with the GIL held across the kernel's send work (how `py-uring` behaved in the runs of 2026-10-06 at commit `b60fe24`) |

If hand-offs decide thread scaling, `py-epoll-batch` scales like `py-uring`
although it uses `epoll`. If it scales like `py-epoll`, the hand-off explanation
is wrong. The same question is asked of the handler reactors: `c-epoll-app` and
`c-epoll-app-batch` are the `epoll` reactor calling the same Python handler,
taking the GIL once per request and once per batch of ready sockets.

The same conditions hold for every engine: the listening socket has a backlog
of 1024 and `TCP_NODELAY`, set once in `make_reuseport_listener` and passed to
`asyncio` and `uvloop` as well; every server process reports its CPU time and
its context switches from `getrusage` when it stops. Defaults: 5 repetitions of 20 s
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
| `srv_gil_releases` | server counters | for the Python loops: how often the loop released the GIL (one per system call for `py-epoll`; one per wait and one per submit for `py-uring`; one per `epoll_wait` and one per batch of socket calls for `py-epoll-batch`) |
| `srv_nvcsw`, `srv_nivcsw` | `getrusage` in the server processes | voluntary and involuntary context switches; a thread that sleeps waiting for the GIL, or for I/O, counts one voluntary switch |
| `conns` | driver | keep-alive connections opened by `wrk` for this run |
| `srv_python`, `srv_gil` | server | interpreter version and GIL state at start-up |

Server counters cover the server's whole life, warm-up included. Ratios of two
server counters are therefore consistent, and they are not divided by wrk's
request count. The one exception is context switches per request for `asyncio`
and `uvloop`, which do not count requests (see Formulas).

## Published results and tables

The runs behind the reported numbers are in `benchmarks/results/`, one folder
per experiment, interpreter and run. All of them were made on 2026-10-07 (UTC)
on the images built from commit `5db4eab`: `...-5db4eab-...` is the GIL build
and `...-5db4eabt-...` the free-threaded build. Fourteen folders hold 2190
runs. Twelve of them come from `run_paper_experiments.sh` (driver at commit
`5db4eab`) and two, `load-...T185514Z` and `handler-...T194758Z`, from
`run_supplement.sh` (driver at commit `abf3e7c`, same images, raised container
limits). Each folder's `meta.json` records the driver's commit, the image id
and the options passed to `docker run`. `benchmarks/make_tables.py` reads
every such folder and writes the tables, the figures, the numbers quoted in
the paper and the results block of the README:

```bash
python3 benchmarks/make_tables.py                     # -> benchmarks/results/tables/
python3 benchmarks/make_tables.py --out paper/tables  # where the manuscript reads them
python3 benchmarks/make_tables.py --readme README.md  # rewrite the README's results block
python3 benchmarks/make_tables.py --check paper/gil_aware_reactor.tex  # numbers the text uses but the data lacks
python3 benchmarks/make_tables.py --dump              # every configuration as text
```

It uses the statistics functions of `bench_matrix.py`, so a table and a
`summary.md` cannot disagree, and each generated file starts with the folders,
commit and image it was computed from. Folders of the same experiment are
pooled, so a trial or an aborted run must not be left in `benchmarks/results/`.
Sums of measurements are exactly rounded (`math.fsum`), so the generated files
are the same byte for byte whichever Python version runs the script.

| Output | Experiment(s) | Shows |
| --- | --- | --- |
| `tab_probe` | `probe-*.txt` (output of `gil_experiment.py`) | the contention probe, mean and fastest repetition |
| `tab_factorial`, `tab_effects` | `factorial` (both builds) | the 2x2 design and its two controls: throughput, scaling as threads, as processes and as threads without the GIL, system calls, GIL releases and context switches per request; each factor's effect with the other held fixed, and the effect of each control |
| `tab_batch` | `batch` | throughput against the cap on completions per system call |
| `tab_scaling`, `fig_scaling` | `scaling` (both builds) | throughput at 1 to 4 workers, scaling, busy cores |
| `tab_app` | `app` (both builds) | the same with a Python handler per request, GIL taken per request and per batch, on both reactors; GIL acquisitions and context switches per request |
| `tab_gilbatch` | `gilbatch` | scaling against the number of requests served per GIL acquisition, with hold time, wait time, GIL utilisation and context switches per request |
| `tab_handler`, `fig_handler` | `handler` (both builds, main and supplementary run) | handler cost swept over nine sizes: GIL hold and wait time, the bound, measured scaling, GIL utilisation; threads against processes and against the baselines' processes |
| `tab_load` | `load` (main and supplementary run) | scaling, GIL releases or acquisitions and context switches per request at 16, 64, 400 and 1600 connections |
| `tab_size` | `size` | throughput and data rate against response size |
| `fig_handoffs` | `factorial`, `scaling`, `app`, `gilbatch` | thread scaling against voluntary context switches per request, every thread-mode configuration of the GIL build at four workers, with the cap sweep of `gilbatch` as connected points |
| `numbers.tex` | all | every measured number the paper quotes in its text, as `\V{key}` macros: one entry per quantity and configuration, ratios between configurations with their intervals, and counts about the data set itself (`meta:...`: runs made, excluded and failed, runs with socket errors, commits, dates) |

`tab_loops` is written only when an `io_uring`-based loop has data, which it
does not. A `tab_loops.tex` or `tab_ladder.tex` in a tables folder is left over
from an earlier version of the script and is not used.

What a reader should know about these runs:

- **One exclusion, repeated.** The main run also measured `load` with 1600
  connections. Those 50 runs are in `runs.csv` and are left out of every table,
  figure and number by the rule `EXCLUSIONS` in `make_tables.py`, which also
  counts them. The reason: a process in the benchmark container could hold 1024
  open files, fewer than the connections offered. The `py-epoll` server stopped
  on the first `accept` that failed, in all 10 of its runs. The other servers
  kept running and served only the connections they had accepted, between 947
  and 1016, so none of these runs measured 1600 connections. The supplementary
  run repeated the 50 runs with the limit raised, and those are the
  1600-connection rows of `tab_load`.
- **One failed attempt.** The `loops` folder of the supplementary run (90 runs:
  60 of `asyncio` and `uvloop`, which succeeded, and 30 of `uringcore`, which
  all failed) is under `benchmarks/results/superseded/`, because the loop it
  was run for could not be measured. It is not part of the 2190 runs. Its
  `asyncio` and `uvloop` runs repeat twelve configurations of `scaling` some
  twelve hours later, and `make_tables.py` reads them for one purpose only: the
  ratio of the two sessions' throughputs (0.97 to 1.01, `meta:anchor-*`).
- **Socket errors.** `wrk` reported socket errors in 133 of the 2140 runs
  that are used. 107 of them are `handler` runs with 1000 or 3000 added
  iterations (at most 0.37% of a run's requests), for the reactors of this
  repository and for `uvloop-proto-app` alike, mostly where one worker serves
  all 400 connections. 20 are the one-worker runs of the four `io_uring`
  engines with 1600 connections (at most 0.008%), where a single worker accepts
  1600 connections from a listen queue of 1024. Six are scattered. The tables
  mark the affected cells. The driver records the total that `wrk` prints, not
  the kind of error.
- **Comparisons across experiments.** Comparisons inside one experiment are
  interleaved. Comparisons across two experiments are not: one `uringpy` worker
  was measured in `scaling`, `factorial`, `batch` and `load`, and the four means
  lie between 143.0 and 145.6 thousand requests per second. Comparisons between the GIL build and the free-threaded build
  are also across experiments.
- **Text files.** `probe-*.txt` is the output of `gil_experiment.py` and
  `handler-thread-control-*.txt` that of `handler_thread_control.py` (the
  handler called from plain Python threads, without the runtime), both run in
  both images by the same script.
- **Earlier runs.** `benchmarks/results/superseded/` holds every earlier run,
  made at commits `b60fe24`, `5b28fd1` and `d9bc686` while the code was being
  revised (`d9bc686` is in the history as `3510a35`: its message was reworded
  afterwards, its content is the same). They include the `factorial` runs in which `py-uring` held the GIL
  while submitting, which led to the wrong conclusion described at the top of
  this file. `make_tables.py` reads nothing from that folder except the `loops`
  folder described above.

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

The bound counts only the time the GIL is held, and can be far from tight:
with the default handler `1/f` allows more scaling than four cores can give,
while measured thread scaling stops well short of the process figure
(`tab_handler`). What the bound leaves out is the cost of handing the GIL from
one thread to another. With `g` hand-offs per request, each costing `tau` when
another thread is waiting, the GIL is unavailable for `t_p + g*tau` per
request, so

- **Bound with hand-offs**: `S(N) <= min(N, 1 / (f + g * tau * m_1))`

Every release of the GIL is an opportunity for a hand-off, not a hand-off: it
becomes one only if another thread is waiting and gets to run before the
releasing thread asks for the lock again. What is counted is therefore an upper
limit on `g`. The paper and the tables write the counted quantity `g^` (g with
a hat) to keep it apart from `g`. The runs of the revision also observe `g`:

- **Observed GIL hand-offs per request** (`gsw:...`; revision runs only):
  `srv_gil_switches / srv_requests`, where `srv_gil_switches` is CPython's own
  count of acquisitions of the GIL by a thread other than its previous holder,
  summed over the server's processes. For `asyncio` and `uvloop` the divisor
  is estimated as for context switches below.

The counted upper limits:

- **GIL acquisitions per request** (C reactors with a handler):
  `srv_gil_acquires / srv_handler_calls`; 1 when the GIL is taken per request,
  far below 1 with GIL batching (`URingEngine.set_gil_batching`), which takes
  the GIL once for all requests found in one pass.
- **GIL releases per request** (loops in Python):
  `srv_gil_releases / srv_requests`.
- **Voluntary context switches per request**: `srv_nvcsw / srv_requests`. A
  thread that goes to sleep, waiting for the GIL or for I/O, makes one. With
  400 connections, workers that each own their GIL make almost none, so in
  thread mode at that load the switches are waits for the GIL. With few
  connections they also count idle waits and are not used. For `asyncio` and
  `uvloop`, which do not count requests, the divisor is wrk's request rate
  times the server's life (warm-up plus measured time).
- **GIL utilisation at `N` workers**: `U_N = m_N * t_p,N`, the share of each
  second the GIL is held running handlers (`t_p,N` measured at `N` workers).
- **Hand-off cost**, where the GIL is the limit and one acquisition is made per
  request: `tau = 1 / m_N - t_p,N`. It is derived, not timed, and no single
  value fits all handler sizes (`meta:tau-min`, `meta:tau-max` in
  `numbers.tex`).
- **Lock capacity**: `1 / t_p,N`, the requests per second that a lock held
  for `t_p,N` per request could pass if it were never idle (`lockcap:...`).
  Threads cannot exceed it; with long handlers they approach it.
- **Wait per acquisition**: `w_N / g^`, the wait for the GIL divided by the
  acquisitions per request (`wacq:...`). With GIL batching a batch waits long
  but only once.
- **Threads against processes**: throughput of four threads over that of four
  processes of the same engine (`r:thread-over-process:...`). The paper and
  `fig_handler` compare the batched reactor's threads with the batched
  reactor's own processes throughout.
- **Gap to the bound**: `min(N, 1/f) / S_N - 1` for the batched reactor, in
  percent (`boundgap:...`): how far the bound lies above what was measured.
- **Estimate of `f` for the loops written in Python**, whose hold time is not
  instrumented: the extra time per request over the C loop on the same
  interface on one worker, `1/m_1(Python loop) - 1/m_1(C loop)`, as a share of
  the Python loop's time per request (`tpy:...`, `fpy:...`). It is a
  difference of two measured numbers and carries the uncertainty of both.

With GIL batching and long handlers, the interpreter's switch interval
interrupts a batch, so the recorded hold then includes time waiting to resume;
`make_tables.py` prints "n/a" for the utilisation in those cells. In
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
| Crediting the interface or the loop's language for what the handling of the GIL does | Two controls, each aimed at one of the confounded quantities (`py-epoll-batch`: GIL releases per pass, with the interface and the system calls unchanged, though the order of work within a pass changes with it; `py-uring-held`: time under the GIL, with no more releases than before); the same GIL batching on an `epoll` reactor; all of it repeated without the GIL. Neither control is a clean single-factor change, and the paper says so | `factorial`, `app` |
| A correlation across different engines read as a cause | One engine with the number of requests per GIL acquisition varied in steps and nothing else changed | `gilbatch` |
| Results that hold at one load only | Connections varied | `load` |
| Runs dropped without saying so | Two sets of runs are outside the data set: the 1600-connection runs of the main run (a rule in `make_tables.py`, counted, explained and repeated) and the failed attempt to measure `uringcore` (kept under `superseded/` with a record of the checks) | `EXCLUSIONS`, "Published results and tables" |
| Code changing between experiments | Every run uses the server images built from one commit, after the test suite passed in both; the supplementary run uses the same images and a driver that differs by one option, the two raised container limits, which each `meta.json` records | `run_paper_experiments.sh`, `meta.json` |
| Numbers mistyped | Tables, figures, the numbers in the paper's text and the README's results block are generated from the raw runs | `make_tables.py` |
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
  stack: one worker already keeps more than one core busy, so scaling at four
  workers stays well below 4 for every engine, in process mode too. The tables
  report busy cores and throughput per busy core next to scaling.
- With response bodies of 16 KiB or more the network path (about 15.7 Gbit/s
  between the two machines) was the limit, not the server; those `size` cells
  measure the network.
- `py-uring` and `py-epoll` are bare dispatch loops without `asyncio`'s task and
  transport machinery, so the loop-placement effect they show at one worker is a
  lower bound for a full event loop.
- Repetitions are interleaved within an experiment, not across experiments (see
  "Published results and tables").
- GIL releases and acquisitions are counted for the engines of this repository,
  not for `asyncio` or `uvloop`, and they are an upper limit on hand-offs, not
  a count of them. The lock itself was not traced. The batch cap for system
  calls was varied only for the C reactor on one worker.
- Threads under the GIL compete with one process per worker only for handlers
  that hold the GIL for about a microsecond, and only under enough load for
  batches to form (`tab_handler`, `fig_handler`, `tab_load`). With 16
  connections the client did not saturate the server.
- With 100 or more added iterations thread scaling falls on the free-threaded
  build as well. `handler_thread_control.py` reproduces that with plain Python
  threads and no runtime, so it does not come from the runtime. Whether its
  cause lies in the interpreter or in the handler was not determined.
- The time a request holds the GIL grows from one worker to four, with one
  process per worker at least as much as with threads. It is a wall-clock
  time, and at four workers no core is idle, so it includes whatever interrupts
  or slows a handler. The handler sizes at which threads fall behind processes
  are therefore partly a property of this four-core machine.
- With GIL batching and the default handler the lock is busy for about two
  thirds of the time at four workers (`U:...`, `lockcap:...`), so the threads
  are not far from what one lock can pass. More cores were not measured.
- `uvloop` with the streams API shows a 99th-percentile latency above 100 ms
  on one worker, against about 6 ms for `asyncio`; the cause was not found. The
  comparisons with `uvloop` that the paper relies on use the Protocol API.
- The contention probe is reliable only for one competing thread on a 4-core
  machine: with two or three, the timings of both loops scatter widely.
