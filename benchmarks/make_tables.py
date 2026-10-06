#!/usr/bin/env python3
"""Generate the paper's result tables (LaTeX) from the raw benchmark runs.

    python3 benchmarks/make_tables.py                 # tables -> benchmarks/results/tables/
    python3 benchmarks/make_tables.py --out paper/tables
    python3 benchmarks/make_tables.py --dump          # every cell as plain text

Input is every folder under benchmarks/results/ that holds a runs.csv and a
meta.json, as written by bench_matrix.py. Folders of the same experiment are
pooled (their cells differ); nothing is typed in by hand. The statistics are
the ones bench_matrix.py uses and EXPERIMENTS.md defines:

    mean and 95% half-width   h = t(0.975, n-1) * s / sqrt(n)
    ratio of two means        r = a/b,  h_r = t * r * sqrt(s_a^2/(n_a a^2) + s_b^2/(n_b b^2))
    busy cores                C = cores * busy share of the server
    throughput per busy core  mean / C
    system calls per request  sum(syscalls) / sum(requests) over a cell's runs

Only runs with status "ok" enter a mean; the number of runs used is printed in
each table, and a cell with fewer runs than the others is marked.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench_matrix import ci95, mean_sd, ratio_ci95, read_rows  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def _num(row, key):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return float("nan")


class Cell:
    """All runs of one configuration."""

    def __init__(self):
        self.rows = []      # successful runs
        self.failed = 0
        self.cores = 0      # server core count, from meta.json

    @property
    def rps(self):
        return [v for v in (_num(r, "rps") for r in self.rows) if not math.isnan(v)]

    @property
    def n(self):
        return len(self.rps)

    @property
    def mean(self):
        return mean_sd(self.rps)[0]

    @property
    def hw(self):
        return ci95(self.rps)

    @property
    def cv(self):
        m, sd = mean_sd(self.rps)
        return 100 * sd / m if m and not math.isnan(sd) else float("nan")

    def avg(self, key):
        vals = [v for v in (_num(r, key) for r in self.rows) if not math.isnan(v)]
        return sum(vals) / len(vals) if vals else float("nan")

    def total(self, key):
        return sum(v for v in (_num(r, key) for r in self.rows) if not math.isnan(v))

    @property
    def busy_cores(self):
        return self.cores * self.avg("server_cpu_pct") / 100

    @property
    def per_core(self):
        c = self.busy_cores
        return self.mean / c if c else float("nan")

    @property
    def syscalls_per_request(self):
        req, sysc = self.total("srv_requests"), self.total("srv_syscalls")
        return sysc / req if req and sysc else float("nan")

    @property
    def completions_per_enter(self):
        ent, comp = self.total("srv_enters"), self.total("srv_completions")
        return comp / ent if ent and comp else float("nan")

    @property
    def gil_hold_us(self):
        calls = self.total("srv_handler_calls")
        return self.total("srv_gil_hold_ns") / calls / 1e3 if calls else float("nan")

    @property
    def gil_wait_us(self):
        calls = self.total("srv_handler_calls")
        return self.total("srv_gil_wait_ns") / calls / 1e3 if calls else float("nan")

    @property
    def acquires_per_request(self):
        """GIL acquisitions per handler call (1 without batching)."""
        calls, acq = self.total("srv_handler_calls"), self.total("srv_gil_acquires")
        return acq / calls if calls and acq else float("nan")

    @property
    def errors(self):
        return any(_num(r, "socket_errors") > 0 or _num(r, "non_2xx") > 0
                   or _num(r, "srv_handler_errors") > 0 for r in self.rows)


def load(results_dir):
    """Return ({key: Cell}, [folder info]). key = (experiment, gil, engine, mode,
    workers, resp_size, max_batch, handler_work)."""
    cells, folders = {}, []
    for name in sorted(os.listdir(results_dir)):
        d = os.path.join(results_dir, name)
        runs, meta_path = os.path.join(d, "runs.csv"), os.path.join(d, "meta.json")
        if not (os.path.isfile(runs) and os.path.isfile(meta_path)):
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        rows = read_rows(runs)
        interp = meta.get("server", {}).get("interpreter", "")
        folder_gil = "off" if "gil_off" in interp.lower() else "on"
        cores = int(meta.get("server", {}).get("nproc") or 0)
        ok = 0
        for r in rows:
            gil = r.get("srv_gil") or folder_gil
            key = (r["experiment"], gil, r["engine"], r["mode"], int(r["workers"]),
                   int(r["resp_size"]), int(r["max_batch"]), int(r.get("handler_work") or 0))
            cell = cells.setdefault(key, Cell())
            cell.cores = cores
            if r.get("status") == "ok":
                cell.rows.append(r)
                ok += 1
            else:
                cell.failed += 1
        folders.append({"name": name, "experiment": meta.get("experiment"), "gil": folder_gil,
                        "runs": len(rows), "ok": ok, "meta": meta})
    return cells, folders


class Data:
    def __init__(self, cells, folders):
        self.cells, self.folders = cells, folders

    def get(self, exp, gil, engine, mode, workers, size=13, batch=0, work=0):
        return self.cells.get((exp, gil, engine, mode, workers, size, batch, work))

    def values(self, exp, gil, field):
        idx = {"engine": 2, "mode": 3, "workers": 4, "size": 5, "batch": 6, "work": 7}[field]
        out = []
        for k in self.cells:
            if k[0] == exp and k[1] == gil and k[idx] not in out:
                out.append(k[idx])
        return out


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

DASH = "--"


def nan(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def k_pm(cell):
    """Throughput in thousands with its 95% half-width: '140.7 $\\pm$ 1.2'."""
    if cell is None or cell.n == 0:
        return DASH
    digits = 1 if cell.mean >= 10e3 else 2      # keep three significant figures
    s = f"{cell.mean / 1e3:.{digits}f}"
    if not nan(cell.hw):
        s += " $\\pm$ " + _hw(cell.hw / 1e3, digits)
    return s


def _hw(h, digits):
    """A half-width that would print as zero is shown as an upper bound."""
    if round(h, digits) == 0:
        return f"$<${10 ** -digits:.{digits}f}"
    return f"{h:.{digits}f}"


def ratio_pm(num, den, digits=2):
    if num is None or den is None or not num.n or not den.n:
        return DASH
    r, h = ratio_ci95(num.rps, den.rps)
    if nan(r):
        return DASH
    return f"{r:.{digits}f}" + ("" if nan(h) else " $\\pm$ " + _hw(h, digits))


def fnum(x, digits=1):
    return DASH if nan(x) else f"{x:,.{digits}f}"


def code(text):
    return "\\code{" + text.replace("_", "\\_") + "}"


def table(env, caption, label, spec, header, body, note=None, size="\\footnotesize",
          colsep="4pt"):
    lines = [f"\\begin{{{env}}}[t]", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
             "\\centering", size, f"\\setlength{{\\tabcolsep}}{{{colsep}}}",
             f"\\begin{{tabular}}{{{spec}}}", "\\toprule"]
    lines += header + ["\\midrule"] + body + ["\\bottomrule", "\\end{tabular}"]
    if note:
        lines += ["", "\\vspace{2pt}", f"\\parbox{{\\linewidth}}{{\\footnotesize {note}}}"]
    lines += [f"\\end{{{env}}}", ""]
    return "\n".join(lines)


def run_count(cells):
    """'n = 5' or 'n = 4--5' over the given cells."""
    ns = sorted({c.n for c in cells if c is not None and c.n})
    if not ns:
        return "n = 0"
    return f"$n={ns[0]}$" if len(ns) == 1 else f"$n={ns[0]}$--${ns[-1]}$"


# --------------------------------------------------------------------------
# Plain-text dump (for checking the prose against the data)
# --------------------------------------------------------------------------

def dump(data):
    out = []
    for f in data.folders:
        out.append(f"# {f['name']}: {f['experiment']} gil={f['gil']} runs={f['runs']} ok={f['ok']}")
    out.append("")
    out.append("experiment gil engine mode W size batch work | n mean hw cv% | p50 p99 | "
               "srvCPU% busy_cores per_core cliCPU% | sys/req compl/enter | hold_us wait_us | flags")
    for key in sorted(data.cells, key=lambda k: (k[0], k[1], k[2], k[3], k[5], k[6], k[7], k[4])):
        c = data.cells[key]
        flags = []
        if c.failed:
            flags.append(f"{c.failed} failed")
        if c.cv > 5:
            flags.append("CV>5%")
        if c.avg("client_cpu_pct") > 85:
            flags.append("client>85%")
        if c.errors:
            flags.append("errors")
        out.append(" ".join(str(x) for x in key) + f" | {c.n} {c.mean:,.0f} {c.hw:,.0f} {c.cv:.1f} | "
                   f"{c.avg('lat_p50_ms'):.2f} {c.avg('lat_p99_ms'):.2f} | "
                   f"{c.avg('server_cpu_pct'):.1f} {c.busy_cores:.2f} {c.per_core:,.0f} "
                   f"{c.avg('client_cpu_pct'):.1f} | {c.syscalls_per_request:.3f} "
                   f"{c.completions_per_enter:.1f} | {c.gil_hold_us:.2f} {c.gil_wait_us:.2f} | "
                   + "; ".join(flags))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

BUILD = {"on": "GIL", "off": "free-thr."}
MODES = ["thread", "process"]


def _efficiency(c1, cn):
    """Throughput per busy core at N workers relative to one worker."""
    if c1 is None or cn is None or nan(c1.per_core) or nan(cn.per_core) or not c1.per_core:
        return float("nan")
    return cn.per_core / c1.per_core


def tab_scaling(d):
    """Transport path: throughput at 1..4 workers, both builds, both modes."""
    body, used = [], []
    plan = [("on", "scaling", ["uringpy", "asyncio", "asyncio-proto"]),
            ("on", "baselines", ["uvloop", "uvloop-proto"]),
            ("off", "scaling", ["uringpy", "asyncio", "asyncio-proto"])]
    last_gil = None
    for gil, exp, engines in plan:
        for engine in engines:
            for mode in MODES:
                cs = [d.get(exp, gil, engine, mode, w) for w in (1, 2, 3, 4)]
                if not any(cs):
                    continue
                if last_gil is not None and gil != last_gil:
                    body.append("\\midrule")
                last_gil = gil
                used += cs
                c1, c4 = cs[0], cs[3]
                body.append(" & ".join([
                    BUILD[gil], code(engine), mode, *[k_pm(c) for c in cs],
                    ratio_pm(c4, c1),
                    fnum(c1.busy_cores if c1 else None, 2), fnum(c4.busy_cores if c4 else None, 2),
                    fnum(_efficiency(c1, c4), 2),
                    fnum(c4.avg("lat_p99_ms") if c4 else None, 1)]) + " \\\\")
    if not body:
        return None
    header = ["Build & Engine & Workers as & $N{=}1$ & $N{=}2$ & $N{=}3$ & $N{=}4$ & $S_4$ "
              "& $C_1$ & $C_4$ & $E_4$ & p99$_4$ (ms) \\\\"]
    return table(
        "table*",
        "Transport path, 13-byte body: throughput in thousands of requests per second "
        f"(mean $\\pm$ 95\\% half-width, {run_count(used)}) at $N$ workers; scaling "
        "$S_4=\\bar{x}_4/\\bar{x}_1$; busy server cores $C_N$; throughput per busy core "
        "at four workers relative to one, $E_4=(\\bar{x}_4/C_4)/(\\bar{x}_1/C_1)$; "
        "99th-percentile latency at four workers.",
        "tab:scaling", "@{}lllrrrrrrrrr@{}", header, body, colsep="3pt",
        note="\\code{uvloop} was measured in a separate experiment at one and four workers "
             "only and is not installed in the free-threaded image.")


def tab_factorial(d):
    rows = [("uringpy", "\\code{io\\_uring}", "C"), ("c-epoll", "\\code{epoll}", "C"),
            ("py-uring", "\\code{io\\_uring}", "Python"), ("py-epoll", "\\code{epoll}", "Python"),
            # Not a cell of the design: py-uring holding the GIL while it submits.
            ("py-uring-held", "\\code{io\\_uring}", "Python$^\\ddagger$")]
    body, used = [], []
    held = False
    for engine, iface, loop in rows:
        cs = [d.get("factorial", "on", engine, "thread", w) for w in (1, 2, 4)]
        if not any(cs):
            continue
        if engine == "py-uring-held":
            held = True
            body.append("\\midrule")
        used += cs
        c1, c2, c4 = cs
        body.append(" & ".join([
            code(engine), iface, loop, *[k_pm(c) for c in cs],
            ratio_pm(c2, c1), ratio_pm(c4, c1),
            fnum(c1.syscalls_per_request if c1 else None, 3),
            fnum(c4.syscalls_per_request if c4 else None, 3),
            fnum(c4.busy_cores if c4 else None, 2),
            fnum(c4.avg("lat_p99_ms") if c4 else None, 1)]) + " \\\\")
    if not body:
        return None
    header = ["Engine & Interface & Loop & $N{=}1$ & $N{=}2$ & $N{=}4$ & $S_2$ & $S_4$ "
              "& sys/req$_1$ & sys/req$_4$ & $C_4$ & p99$_4$ (ms) \\\\"]
    return table(
        "table*",
        "The $2{\\times}2$ design (worker threads, GIL build, 13-byte body): throughput in "
        f"thousands of requests per second (mean $\\pm$ 95\\% half-width, {run_count(used)}), "
        "scaling, measured system calls per request at one and four workers, busy server "
        "cores and 99th-percentile latency at four workers.",
        "tab:factorial", "@{}lllrrrrrrrrr@{}", header, body, colsep="3pt",
        note=("$^\\ddagger$ \\code{py-uring} holding the GIL during the submitting system "
              "call; shown for comparison and not part of the $2{\\times}2$ design."
              if held else None))


def tab_effects(d):
    """Ratios read off the 2x2 design: each factor with the other held fixed."""
    def c(engine, w):
        return d.get("factorial", "on", engine, "thread", w)
    rows = [("Interface, loop in C", "uringpy", "c-epoll"),
            ("Interface, loop in Python", "py-uring", "py-epoll"),
            ("Loop, on \\code{io\\_uring}", "uringpy", "py-uring"),
            ("Loop, on \\code{epoll}", "c-epoll", "py-epoll")]
    body = []
    for label, a, b in rows:
        if not c(a, 1) or not c(b, 1):
            continue
        body.append(" & ".join([label, *[ratio_pm(c(a, w), c(b, w)) for w in (1, 2, 4)]]) + " \\\\")
    if not body:
        return None
    return table(
        "table",
        "Effect of each factor with the other held fixed, as a ratio of mean throughputs "
        "($\\pm$ 95\\% half-width) from Table~\\ref{tab:factorial}. Interface: "
        "\\code{io\\_uring} over \\code{epoll}. Loop: C over Python.",
        "tab:effects", "@{}lrrr@{}",
        ["Effect & $N{=}1$ & $N{=}2$ & $N{=}4$ \\\\"], body, colsep="3pt")


def tab_batch(d):
    caps = d.values("batch", "on", "batch")
    if not caps:
        return None
    caps = sorted(c for c in caps if c) + ([0] if 0 in caps else [])
    free = d.get("batch", "on", "uringpy", "thread", 1, batch=0)
    body, used = [], []
    for cap in caps:
        c = d.get("batch", "on", "uringpy", "thread", 1, batch=cap)
        if not c:
            continue
        used.append(c)
        body.append(" & ".join([
            str(cap) if cap else "none", k_pm(c),
            "1" if cap == 0 else ratio_pm(c, free),
            fnum(c.completions_per_enter, 1), fnum(c.syscalls_per_request, 3)]) + " \\\\")
    return table(
        "table",
        "Batch cap (\\code{uringpy}, one worker): completions processed per "
        "\\code{io\\_uring\\_enter} limited to the cap. Throughput in thousands of requests "
        f"per second (mean $\\pm$ 95\\% half-width, {run_count(used)}), ratio to the uncapped "
        "run, measured completions per call and system calls per request.",
        "tab:batch", "@{}rrrrr@{}",
        ["Cap & Throughput & vs.\\ none & compl./call & sys/req \\\\"], body)


def tab_app(d):
    body, used = [], []
    last_gil = None
    for gil in ("on", "off"):
        for engine in ("uringpy-app", "uringpy-app-batch", "asyncio-app",
                       "asyncio-proto-app", "uvloop-proto-app"):
            for mode in MODES:
                cs = [d.get("app", gil, engine, mode, w) for w in (1, 2, 4)]
                if not any(cs):
                    continue
                if last_gil is not None and gil != last_gil:
                    body.append("\\midrule")
                last_gil = gil
                used += cs
                c1, c2, c4 = cs
                flag = "$^\\dagger$" if any(c is not None and c.cv > 5 for c in cs) else ""
                body.append(" & ".join([
                    BUILD[gil], code(engine), mode, *[k_pm(c) for c in cs],
                    ratio_pm(c2, c1), ratio_pm(c4, c1) + flag,
                    fnum(c4.busy_cores if c4 else None, 2),
                    fnum(c4.avg("lat_p99_ms") if c4 else None, 1)]) + " \\\\")
    if not body:
        return None
    dagger = any("dagger" in line for line in body)
    return table(
        "table*",
        "Application-handler workload: every request calls a Python handler. Throughput in "
        f"thousands of requests per second (mean $\\pm$ 95\\% half-width, {run_count(used)}), "
        "scaling, busy server cores and 99th-percentile latency at four workers.",
        "tab:app", "@{}lllrrrrrrr@{}",
        ["Build & Engine & Workers as & $N{=}1$ & $N{=}2$ & $N{=}4$ & $S_2$ & $S_4$ "
         "& $C_4$ & p99$_4$ (ms) \\\\"], body,
        note=("$^\\dagger$ A configuration in this row had a coefficient of variation above 5\\%."
              if dagger else None))


def _size_label(n):
    for unit, div in (("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n >= div and n % div == 0:
            return f"{n // div}~{unit}"
    return f"{n}~B"


def tab_size(d):
    sizes = sorted(d.values("size", "on", "size"))
    if not sizes:
        return None
    # Prefer the process-mode run against the Protocol API (the stronger
    # baseline); fall back to the earlier thread-mode run against streams.
    if d.get("size", "on", "asyncio-proto", "process", 4, size=sizes[0]):
        mode, base, what = "process", "asyncio-proto", "four worker processes"
    else:
        mode, base, what = "thread", "asyncio", "four worker threads"
    body, used = [], []
    for size in sizes:
        u = d.get("size", "on", "uringpy", mode, 4, size=size)
        a = d.get("size", "on", base, mode, 4, size=size)
        if not u and not a:
            continue
        used += [u, a]
        # wrk reports MiB/s read by the client; convert to Gbit/s.
        gbit = u.avg("transfer_mb_s") * 1.048576 * 8 / 1000 if u else float("nan")
        body.append(" & ".join([
            _size_label(size), k_pm(u), k_pm(a), fnum(gbit, 1),
            fnum(u.busy_cores if u else None, 2), fnum(u.syscalls_per_request if u else None, 2)])
            + " \\\\")
    return table(
        "table",
        f"Response-body size ({what}, GIL build). Throughput in thousands of "
        f"requests per second (mean $\\pm$ 95\\% half-width, {run_count(used)}); for "
        "\\code{uringpy} also the data rate received by the client, busy server cores and "
        "system calls per request.",
        "tab:size", "@{}rrrrrr@{}",
        ["Body & \\code{uringpy} & " + code(base) + " & Gbit/s & $C$ & sys/req \\\\"], body)


def tab_handler(d):
    """Cost model against measurement: handler work swept, GIL time measured.

    For each engine and amount of handler work: one-worker throughput x_1, the
    measured GIL hold time per request t_p at one worker, the GIL-held fraction
    f = t_p * x_1 (x_1 = 1/(t_c + t_p) for a saturated worker), the bound
    min(N, 1/f) at N = 4, the measured scaling of threads and of processes, and
    at four worker threads the measured wait for the GIL per request and the
    GIL acquisitions per request.
    """
    body, used = [], []
    engines = [e for e in ("uringpy-app", "uringpy-app-batch")
               if e in d.values("handler", "on", "engine")]
    for n_engine, engine in enumerate(engines):
        works = sorted(k[7] for k in d.cells
                       if k[0] == "handler" and k[1] == "on" and k[2] == engine
                       and k[3] == "thread" and k[4] == 1)
        if n_engine and works:
            body.append("\\midrule")
        for work in works:
            def c(mode, w, gil="on"):
                return d.get("handler", gil, engine, mode, w, work=work)
            t1, t2, t4 = c("thread", 1), c("thread", 2), c("thread", 4)
            p1, p4 = c("process", 1), c("process", 4)
            f1, f4 = c("thread", 1, "off"), c("thread", 4, "off")
            used += [t1, t2, t4, p1, p4, f1, f4]
            tp = t1.gil_hold_us if t1 else float("nan")
            f = tp * 1e-6 * t1.mean if t1 and not nan(tp) else float("nan")
            bound = min(4.0, 1.0 / f) if f and not nan(f) else float("nan")
            body.append(" & ".join([
                code(engine), str(work), k_pm(t1), fnum(tp, 2), fnum(f, 2), fnum(bound, 2),
                ratio_pm(t2, t1), ratio_pm(t4, t1), ratio_pm(p4, p1), ratio_pm(f4, f1),
                fnum(t4.gil_hold_us if t4 else None, 2),
                fnum(t4.gil_wait_us if t4 else None, 2),
                fnum(t4.acquires_per_request if t4 else None, 3)]) + " \\\\")
    if not body:
        return None
    return table(
        "table*",
        "Handler work swept (iterations of an interpreted loop added to every request), GIL "
        "build unless stated. One-worker throughput $\\bar{x}_1$ in thousands of requests per "
        f"second (mean $\\pm$ 95\\% half-width, {run_count(used)}); GIL hold time per request "
        "$t_p$ at one worker; $f = t_p\\,\\bar{x}_1$; the bound $\\min(4, 1/f)$ "
        "of~\\eqref{eq:bound}; measured scaling of worker threads ($S_2$, $S_4$), of worker "
        "processes ($S_4^{\\mathrm{proc}}$) and of threads on the free-threaded build "
        "($S_4^{\\mathrm{ft}}$); and, at four worker threads, GIL hold time $t_p$, wait time "
        "$w$ and GIL acquisitions per request.",
        "tab:handler", "@{}lrrrrrrrrrrrr@{}",
        ["Engine & Work & $\\bar{x}_1$ & $t_p$ ($\\mu$s) & $f$ & bound & $S_2$ & $S_4$ "
         "& $S_4^{\\mathrm{proc}}$ & $S_4^{\\mathrm{ft}}$ & $t_{p,4}$ ($\\mu$s) & $w_4$ ($\\mu$s) "
         "& acq./req \\\\"], body, colsep="3pt")


TABLES = {"handler": tab_handler, "scaling": tab_scaling, "factorial": tab_factorial, "effects": tab_effects,
          "batch": tab_batch, "app": tab_app, "size": tab_size}


def provenance(data):
    lines = ["% Generated by benchmarks/make_tables.py -- do not edit by hand.", "% Source runs:"]
    for f in data.folders:
        m = f["meta"]
        lines.append(f"%   {f['name']}: {f['ok']}/{f['runs']} runs ok, commit "
                     f"{(m.get('client', {}).get('git_commit') or '?')[:7]}, image "
                     f"{(m.get('server', {}).get('image_id') or '?')[:19]}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    ap.add_argument("--out", default=None, help="default: <results>/tables")
    ap.add_argument("--dump", action="store_true", help="print every cell as text and exit")
    args = ap.parse_args(argv)

    data = Data(*load(args.results))
    if not data.cells:
        sys.exit(f"no results found under {args.results}")
    if args.dump:
        sys.stdout.write(dump(data))
        return 0
    out = args.out or os.path.join(args.results, "tables")
    os.makedirs(out, exist_ok=True)
    head = provenance(data)
    for name, build in TABLES.items():
        tex = build(data)
        if tex is None:
            print(f"skipped {name}: no data")
            continue
        path = os.path.join(out, f"tab_{name}.tex")
        with open(path, "w") as f:
            f.write(head + tex)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
