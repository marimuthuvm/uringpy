"""Unit tests for the benchmark driver's parsing and statistics (no I/O)."""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "benchmarks"))

import bench_matrix as bm  # noqa: E402

WRK_OUTPUT = """Running 20s test @ http://10.0.0.2:8080/
  6 threads and 400 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     3.05ms    1.10ms  41.20ms   88.10%
    Req/Sec    21.93k     1.02k   29.80k    71.25%
  Latency Distribution
     50%    2.91ms
     75%    3.40ms
     90%    4.02ms
     99%  812.00us
  2630512 requests in 20.10s, 281.02MB read
  Socket errors: connect 0, read 3, write 0, timeout 2
  Non-2xx or 3xx responses: 7
Requests/sec: 130871.24
Transfer/sec:     13.98MB
"""


def test_parse_wrk():
    r = bm.parse_wrk(WRK_OUTPUT)
    assert r["rps"] == 130871.24
    assert r["requests"] == 2630512
    assert abs(r["duration_s"] - 20.10) < 1e-9
    assert r["lat_p50_ms"] == 2.91 and r["lat_p90_ms"] == 4.02
    assert abs(r["lat_p99_ms"] - 0.812) < 1e-9          # microseconds -> ms
    assert r["lat_avg_ms"] == 3.05
    assert r["transfer_mb_s"] == 13.98
    assert r["socket_errors"] == 5 and r["non_2xx"] == 7


def test_parse_wrk_garbage_is_nan_not_crash():
    assert math.isnan(bm.parse_wrk("unable to connect")["rps"])


def test_parse_server_stats_sums_workers_and_skips_ratios():
    log = ("[uringpy/thread] starting 2 worker(s)\n"
           "[worker 0] waits=10 completions=100 completions_per_wait=10.00 enters=10 "
           "requests=50 syscalls=11 syscalls_per_request=0.22\n"
           "[worker 1] waits=30 completions=300 completions_per_wait=10.00 enters=31 "
           "requests=150 syscalls=33 syscalls_per_request=0.22\n")
    s = bm.parse_server_stats(log)
    assert s == {"waits": 40, "completions": 400, "enters": 41, "requests": 200,
                 "syscalls": 44}


def test_parse_proc_cpu():
    assert bm.parse_proc_cpu("[proc] cpu_ns=1500\n[worker 0] waits=1\n[proc] cpu_ns=500\n") == 2000
    assert bm.parse_proc_cpu("no stats") is None


def test_parse_runtime():
    log = "[runtime] python=3.14.7 gil_enabled=0\n[uringpy/thread] starting 4 worker(s)\n"
    assert bm.parse_runtime(log) == ("3.14.7", "off")
    assert bm.parse_runtime("[runtime] python=3.11.9 gil_enabled=1\n") == ("3.11.9", "on")
    assert bm.parse_runtime("nothing here") == ("", "")


def test_cpu_usage():
    before = bm.parse_proc_stat("cpu  100 0 100 800 0 0 0 0 0 0\n"
                                "cpu0 50 0 50 400 0 0 0 0 0 0\n"
                                "cpu1 50 0 50 400 0 0 0 0 0 0\n")
    after = bm.parse_proc_stat("cpu  400 0 200 1300 0 0 0 100 0 0\n"
                               "cpu0 350 0 100 450 0 0 0 100 0 0\n"
                               "cpu1 50 0 100 850 0 0 0 0 0 0\n")
    busy, steal, busiest = bm.cpu_usage(before, after)
    assert abs(busy - 50.0) < 1e-9       # 500 busy of 1000 elapsed jiffies
    assert abs(steal - 10.0) < 1e-9
    assert abs(busiest - 90.0) < 1e-9    # cpu0: 450 busy of 500


def test_mean_ci_against_known_values():
    values = [10.0, 12.0, 11.0, 13.0, 9.0]
    m, sd = bm.mean_sd(values)
    assert m == 11.0 and abs(sd - math.sqrt(2.5)) < 1e-12
    # t(0.975, df=4) = 2.776
    assert abs(bm.ci95(values) - 2.776 * math.sqrt(2.5) / math.sqrt(5)) < 1e-12
    assert math.isnan(bm.ci95([5.0]))


def test_ratio_ci():
    ratio, hw = bm.ratio_ci95([200.0, 202.0, 198.0], [100.0, 101.0, 99.0])
    assert abs(ratio - 2.0) < 1e-12
    assert 0 < hw < 0.1
    ratio, hw = bm.ratio_ci95([200.0], [100.0])
    assert ratio == 2.0 and math.isnan(hw)


def _row(engine, workers, rps, status="ok", **kw):
    row = {k: "" for k in bm.CSV_FIELDS}
    row.update(engine=engine, mode="thread", workers=workers, resp_size=13,
               max_batch=0, handler_work=0, status=status, rps=rps, srv_gil="on", client_cpu_pct=40.0,
               server_cpu_pct=60.0, lat_p50_ms=1.0, lat_p99_ms=2.0)
    row.update(kw)
    return row


def test_summarize_scaling_and_flags():
    rows = ([_row("uringpy", 1, v, srv_requests=1000, srv_syscalls=20,
                  srv_enters=10, srv_completions=2000) for v in (100.0, 102.0, 98.0)]
            + [_row("uringpy", 4, v, client_cpu_pct=95.0) for v in (300.0, 306.0, 294.0)]
            + [_row("uringcore", 1, "", status="no-start", note="engine unavailable")])
    text = bm.summarize(rows)
    lines = [l for l in text.splitlines() if l.startswith("| uring")]
    assert len(lines) == 3
    one, four, missing = lines
    assert "| 100 |" in one and "1.00×" in one and "| on |" in one
    assert "| 0.020 |" in one and "| 200.0 |" in one     # syscalls/req, compl/enter
    assert "3.00× ±" in four and "load generator may be the limit" in four
    assert "no successful run: engine unavailable" in missing


def test_build_cells_presets_and_overrides():
    args = bm.argparse.Namespace(experiment="batch", engines=None, modes=None,
                                 workers=None, resp_sizes=None, max_batch=None)
    args.handler_work = None
    args.gil_timing = False
    cells = bm.build_cells(args)
    assert len(cells) == 6 and ("uringpy", "thread", 1, 13, 0, 0) in cells
    assert args.gil_timing is False
    args = bm.argparse.Namespace(experiment="scaling", engines="uringpy", modes="thread",
                                 workers="1,8", resp_sizes=None, max_batch=None,
                                 handler_work=None, gil_timing=False)
    assert bm.build_cells(args) == [("uringpy", "thread", 1, 13, 0, 0),
                                    ("uringpy", "thread", 8, 13, 0, 0)]
    args = bm.argparse.Namespace(experiment="handler", engines=None, modes="thread",
                                 workers="1", resp_sizes=None, max_batch=None,
                                 handler_work=None, gil_timing=False)
    cells = bm.build_cells(args)
    assert [c[5] for c in cells] == [0, 30, 100, 300, 1000, 3000]
    assert args.gil_timing is True      # the preset switches GIL timing on


def test_summarize_handler_columns_and_old_results():
    new = [_row("uringpy-app", 1, 100.0, handler_work=300, srv_requests=1000,
                srv_handler_calls=1000, srv_gil_hold_ns=5_000_000,
                srv_gil_wait_ns=250_000, srv_cpu_ns=20_000_000)]
    line = [l for l in bm.summarize(new).splitlines() if l.startswith("| uringpy-app")][0]
    assert "| 300 |" in line                      # handler work column
    assert "| 20.00 | 5.00 | 0.25 |" in line      # proc CPU, GIL hold, GIL wait (µs/req)
    # Results written before the handler_work column existed still summarise,
    # including with the 5-element cell lists their meta.json holds.
    old = _row("uringpy", 1, 100.0)
    del old["handler_work"]
    meta = {"cells": [["uringpy", "thread", 1, 13, 0]], "params": {}}
    assert "| uringpy | thread | 1 |" in bm.summarize([old], meta)
