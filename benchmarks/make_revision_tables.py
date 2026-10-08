#!/usr/bin/env python3
"""
Tables and quoted numbers for the experiments added in revision
(benchmarks/run_revision.sh), from benchmarks/results-revision/.

    python3 benchmarks/make_revision_tables.py                    # -> <results>/tables/
    python3 benchmarks/make_revision_tables.py --out paper/tables

Reads three folders the revision script writes:
  small/           thread-mode configurations of factorial, app, gilbatch and
                   handler, with the interpreter's own count of GIL hand-offs
  small-py313/     the same image built for CPython 3.13, with the io_uring
                   asyncio loops checked (loopcheck-*.txt) and the baselines
                   measured
  large-openloop/  open-loop load (wrk2) at fixed request rates

and, for the repeat check, the main run's folders (--main, default
benchmarks/results). Writes tab_observed.tex, tab_openloop.tex and
revision.tex; every key in revision.tex starts with "rv:". Statistics come
from make_tables.py and bench_matrix.py, so nothing is computed twice.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_tables as mt  # noqa: E402
from bench_matrix import ci95, mean_sd, ratio_ci95  # noqa: E402

W = 4  # the four-core server of the main run

FACTORIAL = [("uringpy", "C loop, \\code{io\\_uring}"), ("c-epoll", "C loop, \\code{epoll}"),
             ("py-uring", "Python loop, \\code{io\\_uring}"),
             ("py-epoll", "Python loop, \\code{epoll}, GIL per call"),
             ("py-epoll-batch", "Python loop, \\code{epoll}, GIL per pass"),
             ("py-uring-held", "Python loop, \\code{io\\_uring}, GIL held")]
APP = [("uringpy-app", "\\code{io\\_uring} reactor, GIL per request"),
       ("uringpy-app-batch", "\\code{io\\_uring} reactor, GIL per batch"),
       ("c-epoll-app", "\\code{epoll} reactor, GIL per request"),
       ("c-epoll-app-batch", "\\code{epoll} reactor, GIL per batch"),
       ("asyncio-app", "\\code{asyncio}, streams"),
       ("asyncio-proto-app", "\\code{asyncio}, Protocol API"),
       ("uvloop-proto-app", "\\code{uvloop}, Protocol API")]
CAPS = [1, 2, 4, 8, 16, 64]


def fmt(x, digits=3):
    return mt.DASH if mt.nan(x) else f"{x:.{digits}f}"


def scaling(data, exp, engine, workers=W, work=0):
    c1 = data.get(exp, "on", engine, "thread", 1, work=work)
    c4 = data.get(exp, "on", engine, "thread", workers, work=work)
    return c1, c4


def observed_rows(data):
    """(label, group, exp, engine, c1, c4) for every thread configuration."""
    rows = []
    for engine, label in FACTORIAL:
        rows.append((label, "loop", "factorial", engine) + scaling(data, "factorial", engine))
    for engine, label in APP:
        rows.append((label, "handler", "app", engine) + scaling(data, "app", engine))
    for cap in CAPS:
        engine = f"uringpy-app-batch{cap}"
        rows.append((f"\\code{{io\\_uring}} reactor, at most {cap} per acquisition", "cap",
                     "gilbatch", engine) + scaling(data, "gilbatch", engine))
    return [r for r in rows if r[4] is not None and r[5] is not None]


def tab_observed(data):
    body, used, group = [], [], None
    for label, g, exp, engine, c1, c4 in observed_rows(data):
        if group is not None and g != group:
            body.append("\\midrule")
        group = g
        used += [c1, c4]
        body.append(" & ".join([label, mt.k_pm(c1), mt.k_pm(c4), mt.ratio_pm(c4, c1),
                                fmt(c4.handoffs), fmt(c4.csw), fmt(c4.gil_switches)])
                    + " \\\\")
    return mt.table(
        "table*",
        "GIL hand-offs observed by the interpreter, four worker threads on the GIL build "
        "(revision run, 400 connections). Throughput in thousands of requests per second "
        f"(mean $\\pm$ 95\\% half-width, {mt.run_count(used)}) at one and four threads, and "
        "scaling $S_4$. Per request at four threads: $\\hat{g}$, the GIL releases (loops "
        "in Python) or acquisitions (C reactors) counted by the engine, an upper limit on "
        "hand-offs; voluntary context switches of the server process (c.sw.); and "
        "$g$, the number of times the GIL was taken by a thread other than its previous "
        "holder, read from CPython's own counter.",
        "tab:observed", "@{}lrrrrrr@{}",
        ["Configuration & $\\bar{x}_1$ & $\\bar{x}_4$ & $S_4$ & $\\hat{g}$ & c.sw. & $g$ \\\\"],
        body, colsep="4pt",
        note=("$\\hat{g}$ is not counted for \\code{asyncio} and \\code{uvloop}; for them c.sw. "
              "and $g$ are divided by the request count of the load generator, scaled to the "
              "server's life."))


# --------------------------------------------------------------------------
# Open loop

def openloop_cells(folder):
    """{(engine, mode, rate): [rows]} from every runs.csv under folder."""
    out = {}
    for name in sorted(os.listdir(folder)):
        runs = os.path.join(folder, name, "runs.csv")
        if not os.path.isfile(runs):
            continue
        with open(runs, newline="") as f:
            for r in csv.DictReader(f):
                if r.get("status") != "ok":
                    continue
                key = (r["engine"], r["mode"], int(float(r.get("rate") or 0)))
                out.setdefault(key, []).append(r)
    return out


def _avg(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) not in ("", None)]
    return math.fsum(vals) / len(vals) if vals else float("nan")


OPENLOOP = [("uringpy-app", "thread", "Threads, GIL per request"),
            ("uringpy-app-batch", "thread", "Threads, GIL per batch"),
            ("uringpy-app-batch", "process", "Processes, GIL per batch"),
            ("uvloop-proto-app", "process", "\\code{uvloop} processes")]


def openloop_summary(cells):
    """{(engine, mode, rate): dict(rps, hw, p50, p99, sustained, n, gsw)}."""
    out = {}
    for key, rows in cells.items():
        rps = [float(r["rps"]) for r in rows]
        m, _ = mean_sd(rps)
        sw = [r for r in rows if r.get("srv_gil_switches") and r.get("srv_requests")]
        gsw = (math.fsum(float(r["srv_gil_switches"]) for r in sw)
               / math.fsum(float(r["srv_requests"]) for r in sw)) if sw else float("nan")
        cs = [r for r in rows if r.get("srv_nvcsw") and r.get("srv_requests")]
        csw = (math.fsum(float(r["srv_nvcsw"]) for r in cs)
               / math.fsum(float(r["srv_requests"]) for r in cs)) if cs else float("nan")
        out[key] = dict(rps=m, hw=ci95(rps), n=len(rps), p50=_avg(rows, "lat_p50_ms"),
                        p99=_avg(rows, "lat_p99_ms"), sustained=m >= 0.95 * key[2], gsw=gsw,
                        csw=csw, cli=_avg(rows, "client_cpu_pct"))
    return out


def _ms(x):
    if mt.nan(x):
        return mt.DASH
    if x >= 100:
        return f"{x:,.0f}"
    return f"{x:.2f}"


def tab_openloop(summary):
    rates = sorted({k[2] for k in summary})
    body, ns = [], set()
    for rate in rates:
        cells = []
        for engine, mode, _ in OPENLOOP:
            s = summary.get((engine, mode, rate))
            if s is None:
                cells += [mt.DASH, mt.DASH]
                continue
            ns.add(s["n"])
            p50, p99 = _ms(s["p50"]), _ms(s["p99"])
            if not s["sustained"]:
                p50 = f"\\textit{{{p50}}}$^{{*}}$"
                p99 = f"\\textit{{{p99}}}"
            cells += [p50, p99]
        body.append(" & ".join([f"{rate // 1000}k"] + cells) + " \\\\")
    peak = []
    for engine, mode, _ in OPENLOOP:
        best = max((s["rps"] for k, s in summary.items() if k[:2] == (engine, mode)),
                   default=float("nan"))
        peak.append(f"\\multicolumn{{2}}{{c}}{{{best / 1e3:.0f}k}}")
    body += ["\\midrule", " & ".join(["highest"] + peak) + " \\\\"]
    head1 = " & ".join(["Offered"] + [f"\\multicolumn{{2}}{{c}}{{{lbl}}}"
                                      for _, _, lbl in OPENLOOP]) + " \\\\"
    head2 = " & ".join(["req/s"] + ["p50 & p99"] * len(OPENLOOP)) + " \\\\"
    n = f"$n={min(ns)}$" if len(ns) == 1 else f"$n={min(ns)}$--${max(ns)}$"
    return mt.table(
        "table*",
        "Open-loop load: requests sent at fixed rates by \\code{wrk2} (latency corrected "
        "for coordinated omission) to four workers with the default handler on the "
        f"four-core server, 400 connections, runs of 30~s ({n}). Median and 99th-percentile "
        "latency in ms (means over repetitions), and the highest rate each configuration "
        "delivered.",
        "tab:openloop", "@{}r" + "rr" * len(OPENLOOP) + "@{}", [head1, head2], body,
        colsep="5pt",
        note=("$^{*}$ In italics: the configuration delivered less than 95\\% of the "
              "offered rate, so requests queued and latency grew without bound."))


# --------------------------------------------------------------------------
# Numbers

RUN_COUNTS = {}


def count_runs(results):
    """Runs made and runs that succeeded, over the three revision folders."""
    made = ok = 0
    for sub in ("small", "small-py313", "large-openloop"):
        top = os.path.join(results, sub)
        if not os.path.isdir(top):
            continue
        for name in os.listdir(top):
            runs = os.path.join(top, name, "runs.csv")
            if os.path.isfile(runs):
                with open(runs, newline="") as f:
                    for r in csv.DictReader(f):
                        made += 1
                        ok += r.get("status") == "ok"
    RUN_COUNTS.update({"rv:runs-made": str(made), "rv:runs-ok": str(ok)})


def spearman(a, b):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):        # average ranks over ties
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2
            i = j + 1
        return out
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float("nan")


def numbers(data, main, py313, ol):
    out = {}
    for label, g, exp, engine, c1, c4 in observed_rows(data):
        name = f"{exp}/{engine}"
        out[f"rv:S:{name}"] = mt.ratio_pm(c4, c1).split(" ")[0]
        out[f"rv:Spm:{name}"] = mt._math(mt.ratio_pm(c4, c1))
        out[f"rv:x:{name}/1"] = f"{c1.mean / 1e3:.1f}"
        out[f"rv:x:{name}/4"] = f"{c4.mean / 1e3:.1f}"
        for q, v in (("gsw", c4.gil_switches), ("csw", c4.csw), ("ho", c4.handoffs)):
            if not mt.nan(v):
                out[f"rv:{q}:{name}"] = f"{v:.3f}"
    # observed hand-offs against handler length
    for engine in ("uringpy-app", "uringpy-app-batch"):
        for work in sorted(data.values("handler", "on", "work")):
            c1, c4 = scaling(data, "handler", engine, work=work)
            if c4 is None or c1 is None:
                continue
            name = f"handler/{engine}/h{work}"
            out[f"rv:S:{name}"] = mt.ratio_pm(c4, c1).split(" ")[0]
            for q, v in (("gsw", c4.gil_switches), ("csw", c4.csw)):
                if not mt.nan(v):
                    out[f"rv:{q}:{name}"] = f"{v:.3f}"
    # the separation the expectations named (1b), with and without the hold-time control
    rows = observed_rows(data)
    fast = [r[5].gil_switches for r in rows if r[5].mean / r[4].mean >= 2]
    slow = [(r[3], r[5].gil_switches) for r in rows if r[5].mean / r[4].mean < 1]
    out["rv:fast-gsw-max"] = f"{max(fast):.3f}"
    out["rv:fast-n"] = str(len(fast))
    out["rv:slow-n"] = str(len(slow))
    out["rv:slow-gsw-min-excl-held"] = f"{min(v for e, v in slow if e != 'py-uring-held'):.3f}"
    out["rv:ratio-epoll-over-uring-app"] = (
        f"{data.get('app', 'on', 'c-epoll-app', 'thread', W).gil_switches / data.get('app', 'on', 'uringpy-app', 'thread', W).gil_switches:.0f}")
    # how well each counter orders the configurations by scaling (Spearman's
    # rank correlation), over the observed rows and the handler sweep
    pts = [(r[5].mean / r[4].mean, r[5].gil_switches, r[5].csw, r[3]) for r in rows]
    for engine in ("uringpy-app", "uringpy-app-batch"):
        for work in sorted(data.values("handler", "on", "work")):
            c1, c4 = scaling(data, "handler", engine, work=work)
            if c1 is not None and c4 is not None and work:
                pts.append((c4.mean / c1.mean, c4.gil_switches, c4.csw, engine))
    for tag, sel in (("all", pts), ("noheld", [p for p in pts if p[3] != "py-uring-held"])):
        s4 = [p[0] for p in sel]
        out[f"rv:rho-gsw-{tag}"] = f"{spearman(s4, [p[1] for p in sel]):.2f}"
        out[f"rv:rho-csw-{tag}"] = f"{spearman(s4, [p[2] for p in sel]):.2f}"
        out[f"rv:rho-n-{tag}"] = str(len(sel))
    # the hold-time control's raw count: owner changes per second of the server's life
    held = data.get("factorial", "on", "py-uring-held", "thread", W)
    if held is not None and held.n:
        sw = math.fsum(float(r["srv_gil_switches"]) for r in held.rows)
        out["rv:held-switches-per-s"] = f"{sw / (len(held.rows) * held.life_s):.0f}"
    out.update(RUN_COUNTS)
    # repeat check against the main run (expectation 1e)
    ratios = []
    for key, c in data.cells.items():
        ref = main.cells.get(key)
        if ref is not None and ref.n and c.n:
            ratios.append(c.mean / ref.mean)
    if ratios:
        out["rv:repeat-n"] = str(len(ratios))
        out["rv:repeat-min"] = f"{min(ratios):.2f}"
        out["rv:repeat-max"] = f"{max(ratios):.2f}"
        out["rv:repeat-within5"] = str(sum(1 for r in ratios if abs(r - 1) <= 0.05))
        import statistics
        for w in (1, 4):
            rs = [c.mean / main.cells[k].mean for k, c in data.cells.items()
                  if k[4] == w and main.cells.get(k) is not None and main.cells[k].n and c.n]
            if rs:
                out[f"rv:repeat-w{w}-min"] = f"{min(rs):.2f}"
                out[f"rv:repeat-w{w}-max"] = f"{max(rs):.2f}"
                out[f"rv:repeat-w{w}-median"] = f"{statistics.median(rs):.2f}"
                out[f"rv:repeat-w{w}-n"] = str(len(rs))
    # Python 3.13: the baselines that ran, threads against processes
    for engine in ("uringpy", "asyncio", "asyncio-proto", "uvloop", "uvloop-proto"):
        for mode in ("thread", "process"):
            c1 = py313.get("loops", "on", engine, mode, 1)
            c4 = py313.get("loops", "on", engine, mode, 4)
            if c1 and c4 and c1.n and c4.n:
                out[f"rv:313:S:{engine}/{mode}"] = mt.ratio_pm(c4, c1).split(" ")[0]
                out[f"rv:313:x:{engine}/{mode}/4"] = f"{c4.mean / 1e3:.1f}"
                if mode == "thread" and not mt.nan(c4.gil_switches):
                    out[f"rv:313:gsw:{engine}"] = f"{c4.gil_switches:.3f}"
    for engine in ("uringpy-app", "uringpy-app-batch", "asyncio-proto-app", "uvloop-proto-app"):
        t, p = py313.get("app", "on", engine, "thread", 4), py313.get("app", "on", engine, "process", 4)
        t1 = py313.get("app", "on", engine, "thread", 1)
        if t and p and t.n and p.n:
            out[f"rv:313:tp:{engine}"] = mt.ratio_pm(t, p).split(" ")[0]
            out[f"rv:313:S:{engine}/thread"] = mt.ratio_pm(t, t1).split(" ")[0]
            if not mt.nan(t.gil_switches):
                out[f"rv:313:gsw:{engine}"] = f"{t.gil_switches:.3f}"
    # open loop
    for (engine, mode, rate), s in ol.items():
        name = f"{engine}/{mode}/{rate // 1000}k"
        out[f"rv:ol:p50:{name}"] = _ms(s["p50"])
        out[f"rv:ol:p99:{name}"] = _ms(s["p99"])
        out[f"rv:ol:x:{name}"] = f"{s['rps'] / 1e3:.1f}"
        if not mt.nan(s["gsw"]):
            out[f"rv:ol:gsw:{name}"] = f"{s['gsw']:.3f}"
        if not mt.nan(s["csw"]):
            out[f"rv:ol:csw:{name}"] = f"{s['csw']:.3f}"
        out[f"rv:ol:cli:{name}"] = f"{s['cli']:.0f}"
    for engine, mode, _ in OPENLOOP:
        keep = [k[2] for k, s in ol.items() if k[:2] == (engine, mode) and s["sustained"]]
        best = max((s["rps"] for k, s in ol.items() if k[:2] == (engine, mode)), default=0)
        out[f"rv:ol:sustained:{engine}/{mode}"] = f"{max(keep) // 1000}k" if keep else mt.DASH
        out[f"rv:ol:peak:{engine}/{mode}"] = f"{best / 1e3:.0f}"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--results", default=os.path.join(HERE, "results-revision"))
    ap.add_argument("--main", default=os.path.join(HERE, "results"))
    ap.add_argument("--out", default=None, help="default: <results>/tables")
    args = ap.parse_args(argv)
    out_dir = args.out or os.path.join(args.results, "tables")
    os.makedirs(out_dir, exist_ok=True)

    data = mt.Data(*mt.load(os.path.join(args.results, "small")))
    py313 = mt.Data(*mt.load(os.path.join(args.results, "small-py313")))
    main_data = mt.Data(*mt.load(args.main))
    ol = openloop_summary(openloop_cells(os.path.join(args.results, "large-openloop")))
    count_runs(args.results)

    files = {"tab_observed.tex": tab_observed(data), "tab_openloop.tex": tab_openloop(ol)}
    nums = numbers(data, main_data, py313, ol)
    lines = ["% Generated by benchmarks/make_revision_tables.py -- do not edit by hand.",
             "\\makeatletter"]
    lines += [f"\\@namedef{{v@{k}}}{{{v}}}" for k, v in sorted(nums.items())]
    lines.append("\\makeatother")
    files["revision.tex"] = "\n".join(lines) + "\n"
    for name, text in files.items():
        with open(os.path.join(out_dir, name), "w") as f:
            f.write(text)
        print(f"wrote {os.path.join(out_dir, name)}")
    print(f"{len(nums)} numbers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
