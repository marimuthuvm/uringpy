#!/usr/bin/env python3
"""Generate the paper's result tables, figures and in-text numbers (LaTeX)
from the raw benchmark runs.

    python3 benchmarks/make_tables.py                 # -> benchmarks/results/tables/
    python3 benchmarks/make_tables.py --out paper/tables
    python3 benchmarks/make_tables.py --dump          # every cell as plain text

Written to the output folder:

    tab_<name>.tex   one table each
    fig_<name>.tex   one figure each (pgfplots source, drawn when the paper is built)
    numbers.tex      every number the text of the paper quotes, as \\V{key}

Input is every folder under benchmarks/results/ that holds a runs.csv and a
meta.json, as written by bench_matrix.py. Folders of the same experiment are
pooled (their cells differ); nothing is typed in by hand. The statistics are
the ones bench_matrix.py uses and EXPERIMENTS.md defines:

    mean and 95% half-width   h = t(0.975, n-1) * s / sqrt(n)
    ratio of two means        r = a/b,  h_r = t * r * sqrt(s_a^2/(n_a a^2) + s_b^2/(n_b b^2))
    busy cores                C = cores * busy share of the server
    throughput per busy core  mean / C
    system calls per request  sum(syscalls) / sum(requests) over a cell's runs
    g, the upper limit on     counted GIL releases / requests (loops in Python), or
    GIL hand-offs per request counted GIL acquisitions / handler calls (C reactors
                              that call a handler); 0 for a C reactor without one
    context switches / req.   sum(voluntary context switches) / sum(requests)

Only runs with status "ok" enter a mean; the number of runs used is printed in
each table, and a cell with fewer runs than the others is marked. Runs that
match a rule in EXCLUSIONS are left out of everything and counted.
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
        self.engine = ""
        self.life_s = float("nan")   # warm-up + measured seconds of one run
        self.measured_s = float("nan")

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

    def _timed(self, key):
        """Per handler call, over the runs in which GIL timing was switched on."""
        rows = [r for r in self.rows if _num(r, "srv_gil_hold_ns") > 0]
        calls = sum(_num(r, "srv_handler_calls") for r in rows)
        return sum(_num(r, key) for r in rows) / calls / 1e3 if calls else float("nan")

    @property
    def gil_hold_us(self):
        return self._timed("srv_gil_hold_ns")

    @property
    def gil_wait_us(self):
        return self._timed("srv_gil_wait_ns")

    @property
    def acquires_per_request(self):
        """GIL acquisitions per handler call (1 without batching)."""
        calls, acq = self.total("srv_handler_calls"), self.total("srv_gil_acquires")
        return acq / calls if calls and acq else float("nan")

    @property
    def releases_per_request(self):
        """Counted GIL releases per request (the loops written in Python)."""
        req, rel = self.total("srv_requests"), self.total("srv_gil_releases")
        return rel / req if req and rel else float("nan")

    @property
    def handoffs(self):
        """How often a request gives another thread the chance to take the GIL.

        Loops in Python: counted GIL releases per request. C reactors calling
        a handler: counted GIL acquisitions per handler call. C reactors
        without a handler never take the GIL: 0. Not counted for asyncio and
        uvloop (nan)."""
        if self.engine in ("uringpy", "c-epoll"):
            return 0.0
        if self.engine.startswith("py-"):
            rel = self.releases_per_request
            # Runs made before the release counter existed: every system call
            # of py-epoll and py-uring released the GIL once.
            if nan(rel) and self.engine in ("py-epoll", "py-uring"):
                return self.syscalls_per_request
            return rel
        if "-app" in self.engine and self.engine.split("-app")[0] in ("uringpy", "c-epoll"):
            return self.acquires_per_request
        return float("nan")

    @property
    def csw_per_request(self):
        """Voluntary context switches of the server processes per request,
        both from server counters covering the server's whole life."""
        rows = [r for r in self.rows if not math.isnan(_num(r, "srv_requests"))
                and not math.isnan(_num(r, "srv_nvcsw"))]
        req = sum(_num(r, "srv_requests") for r in rows)
        sw = sum(_num(r, "srv_nvcsw") for r in rows)
        return sw / req if req and rows else float("nan")

    @property
    def csw_per_request_est(self):
        """The same for engines that do not count their requests (asyncio,
        uvloop): switches over the server's life divided by the requests wrk
        counted in the measured interval, scaled to the server's life. Assumes
        the request rate of the warm-up equals that of the measurement."""
        rows = [r for r in self.rows if not math.isnan(_num(r, "srv_nvcsw"))
                and not math.isnan(_num(r, "rps"))]
        if not rows or nan(self.life_s):
            return float("nan")
        req = sum(_num(r, "rps") for r in rows) * self.life_s
        return sum(_num(r, "srv_nvcsw") for r in rows) / req if req else float("nan")

    @property
    def csw(self):
        direct = self.csw_per_request
        return self.csw_per_request_est if nan(direct) else direct

    @property
    def gil_util(self):
        """Share of each second the GIL is held running handlers: x * t_p."""
        tp = self.gil_hold_us
        return tp * 1e-6 * self.mean if self.n and not nan(tp) else float("nan")

    @property
    def errors(self):
        return any(_num(r, "socket_errors") > 0 or _num(r, "non_2xx") > 0
                   or _num(r, "srv_handler_errors") > 0 for r in self.rows)


# Runs that are kept in the repository but left out of every table, figure and
# quoted number, with the reason. They are counted (meta:excluded-runs).
#
# load, 1600 connections, in runs made without a raised open-file limit: the
# server container's limit (1024) was below the number of connections. The
# py-epoll server exited on the failed accept() in every run, and the other
# engines served only the connections that fitted under the limit, so none of
# these runs measured 1600 connections. Runs made with the limit raised
# (--docker-opts "--ulimit nofile=...", recorded in meta.json) are kept.
EXCLUSIONS = [
    {"experiment": "load", "conns": 1600, "unless_docker_opt": "nofile",
     "reason": "open-file limit of the server below the number of connections"},
]


def _excluded(row, meta=None):
    opts = ((meta or {}).get("params") or {}).get("docker_opts") or ""
    for rule in EXCLUSIONS:
        if (row.get("experiment") == rule["experiment"]
                and int(row.get("conns") or 400) == rule["conns"]
                and rule["unless_docker_opt"] not in opts):
            return True
    return False


def load(results_dir):
    """Return ({key: Cell}, [folder info]). key = (experiment, gil, engine, mode,
    workers, resp_size, max_batch, handler_work, conns). Runs written before the
    conns column existed used the default of 400 connections. Runs matching
    EXCLUSIONS are counted per folder and otherwise ignored."""
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
        params = meta.get("params", {})
        measured = float(params.get("duration") or "nan")
        life = measured + float(params.get("warmup") or 0)
        ok = excluded = excluded_failed = 0
        served = []     # connections a surviving excluded run really served
        for r in rows:
            if _excluded(r, meta):
                excluded += 1
                excluded_failed += r.get("status") != "ok"
                # closed loop: connections in service = throughput x mean latency
                if r.get("status") == "ok" and not math.isnan(_num(r, "lat_avg_ms")):
                    served.append(_num(r, "rps") * _num(r, "lat_avg_ms") / 1e3)
                continue
            gil = r.get("srv_gil") or folder_gil
            key = (r["experiment"], gil, r["engine"], r["mode"], int(r["workers"]),
                   int(r["resp_size"]), int(r["max_batch"]), int(r.get("handler_work") or 0),
                   int(r.get("conns") or 400))
            cell = cells.setdefault(key, Cell())
            cell.cores, cell.engine = cores, r["engine"]
            cell.life_s, cell.measured_s = life, measured
            if r.get("status") == "ok":
                cell.rows.append(r)
                ok += 1
            else:
                cell.failed += 1
        folders.append({"name": name, "experiment": meta.get("experiment"), "gil": folder_gil,
                        "runs": len(rows), "ok": ok, "excluded": excluded,
                        "excluded_failed": excluded_failed, "excluded_served": served,
                        "meta": meta})
    return cells, folders


class Data:
    def __init__(self, cells, folders, results_dir=None):
        self.cells, self.folders, self.results_dir = cells, folders, results_dir

    def get(self, exp, gil, engine, mode, workers, size=13, batch=0, work=0, conns=400):
        return self.cells.get((exp, gil, engine, mode, workers, size, batch, work, conns))

    def values(self, exp, gil, field):
        idx = {"engine": 2, "mode": 3, "workers": 4, "size": 5, "batch": 6, "work": 7,
               "conns": 8}[field]
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
        out.append(f"# {f['name']}: {f['experiment']} gil={f['gil']} runs={f['runs']} ok={f['ok']}"
                   + (f" excluded={f['excluded']}" if f.get("excluded") else ""))
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

BUILD = {"on": "GIL", "off": "no GIL"}
MODES = ["thread", "process"]


def _efficiency(c1, cn):
    """Throughput per busy core at N workers relative to one worker."""
    if c1 is None or cn is None or nan(c1.per_core) or nan(cn.per_core) or not c1.per_core:
        return float("nan")
    return cn.per_core / c1.per_core


def tab_scaling(d):
    """Transport path: throughput at 1..4 workers, both builds, both modes."""
    body, used = [], []
    engines = ["uringpy", "asyncio", "asyncio-proto", "uvloop", "uvloop-proto"]
    last_gil = None
    separate = False
    for gil in ("on", "off"):
        for engine in engines:
            for mode in MODES:
                cs = [d.get("scaling", gil, engine, mode, w) for w in (1, 2, 3, 4)]
                if not any(cs):       # earlier runs had uvloop in its own experiment
                    cs = [d.get("baselines", gil, engine, mode, w) for w in (1, 2, 3, 4)]
                    separate = separate or any(cs)
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
    header = ["Build & Engine & Workers & $N{=}1$ & $N{=}2$ & $N{=}3$ & $N{=}4$ & $S_4$ "
              "& $C_1$ & $C_4$ & $E_4$ & p99 (ms) \\\\"]
    return table(
        "table*",
        "Transport path, 13-byte body: throughput in thousands of requests per second "
        f"(mean $\\pm$ 95\\% half-width, {run_count(used)}) at $N$ workers; scaling "
        "$S_4=\\bar{x}_4/\\bar{x}_1$; busy server cores $C_N$; throughput per busy core "
        "at four workers relative to one, $E_4=(\\bar{x}_4/C_4)/(\\bar{x}_1/C_1)$; "
        "99th-percentile latency at four workers.",
        "tab:scaling", "@{}lllrrrrrrrrr@{}", header, body, colsep="3pt",
        note=("``no GIL'' is the free-threaded build; \\code{uvloop} is not installed in "
              "its image."
              + (" It was measured in a separate experiment at one and four workers only."
                 if separate else "")))


# The 2x2 design and its two controls. A control differs from a cell of the
# design in one thing only and is not itself a cell.
FACTORIAL_ROWS = [
    ("uringpy", "\\code{io\\_uring}", "C", ""),
    ("c-epoll", "\\code{epoll}", "C", ""),
    ("py-uring", "\\code{io\\_uring}", "Python", ""),
    ("py-epoll", "\\code{epoll}", "Python", ""),
    ("py-epoll-batch", "\\code{epoll}", "Python", "$^{a}$"),
    ("py-uring-held", "\\code{io\\_uring}", "Python", "$^{b}$"),
]
FACTORIAL_NOTES = {
    "py-epoll-batch": "$^{a}$ \\code{py-epoll} with the \\code{recv} and \\code{send} calls of "
                      "all ready sockets made by one C call that releases the GIL once.",
    "py-uring-held": "$^{b}$ \\code{py-uring} holding the GIL during the submitting "
                     "system call.",
}


def tab_factorial(d):
    body, used, notes, free = [], [], [], False
    for engine, iface, loop, mark in FACTORIAL_ROWS:
        cs = [d.get("factorial", "on", engine, "thread", w) for w in (1, 2, 4)]
        if not any(cs):
            continue
        if mark and not notes:
            body.append("\\midrule")
        if mark:
            notes.append(FACTORIAL_NOTES[engine])
        p1, p4 = (d.get("factorial", "on", engine, "process", w) for w in (1, 4))
        f1, f4 = (d.get("factorial", "off", engine, "thread", w) for w in (1, 4))
        free = free or bool(f1 and f4)
        used += cs + [p1, p4, f1, f4]
        c1, c2, c4 = cs
        body.append(" & ".join([
            code(engine) + mark, loop, *[k_pm(c) for c in cs],
            ratio_pm(c4, c1), ratio_pm(p4, p1), ratio_pm(f4, f1),
            fnum(c4.syscalls_per_request if c4 else None, 3),
            _handoffs(c4), fnum(c4.csw if c4 else None, 3),
            fnum(c4.busy_cores if c4 else None, 2),
            fnum(c4.avg("lat_p99_ms") if c4 else None, 1)]) + " \\\\")
    if not body:
        return None
    if not free:        # no free-threaded runs: drop that column
        body = [line if line == "\\midrule" else
                " & ".join(line.split(" & ")[:7] + line.split(" & ")[8:]) for line in body]
    header = ["Engine & Loop & $N{=}1$ & $N{=}2$ & $N{=}4$ & $S_4$ "
              "& $S_4^{\\mathrm{proc}}$ " + ("& $S_4^{\\mathrm{ft}}$ " if free else "")
              + "& sys & $g$ & c.sw. & $C_4$ & p99 \\\\"]
    return table(
        "table*",
        "The $2{\\times}2$ design and two controls (worker threads, GIL build, 13-byte body): "
        "throughput in thousands of requests per second (mean $\\pm$ 95\\% half-width, "
        f"{run_count(used)}) at $N$ workers; scaling of worker threads $S_4$, of worker "
        "processes $S_4^{\\mathrm{proc}}$"
        + (" and of worker threads on the free-threaded build $S_4^{\\mathrm{ft}}$" if free else "")
        + "; and, at four worker threads, per request: measured "
        "system calls (sys), GIL releases ($g$, the upper limit on hand-offs) and voluntary "
        "context switches (c.sw.); busy "
        "server cores $C_4$; and 99th-percentile latency in ms.",
        "tab:factorial", "@{}llrrrrrrrrrr" + ("r" if free else "") + "@{}", header, body,
        colsep="3pt",
        note=" ".join(["The upper four rows are the design; the lower rows are controls that "
                       "differ from one cell in one respect."] + notes) if notes else None)


def _handoffs(c):
    """Hand-offs per request for a table cell; a C reactor without a handler is 0."""
    if c is None:
        return DASH
    h = c.handoffs
    return "0" if h == 0 else fnum(h, 3)


def tab_effects(d):
    """Ratios read off the 2x2 design, each factor with the other held fixed,
    and the two ratios the controls add."""
    def c(engine, w):
        return d.get("factorial", "on", engine, "thread", w)
    rows = [("Interface, loop in C", "uringpy", "c-epoll"),
            ("Interface, loop in Python", "py-uring", "py-epoll"),
            ("Loop, on \\code{io\\_uring}", "uringpy", "py-uring"),
            ("Loop, on \\code{epoll}", "c-epoll", "py-epoll"),
            None,
            ("GIL releases (\\code{epoll})$^{a}$", "py-epoll-batch", "py-epoll"),
            ("Interface (batched)$^{b}$", "py-uring", "py-epoll-batch")]
    body, controls = [], False
    for row in rows:
        if row is None:
            continue
        label, a, b = row
        if not c(a, 1) or not c(b, 1):
            continue
        if "py-epoll-batch" in (a, b) and not controls:
            controls = True
            if body:
                body.append("\\midrule")
        body.append(" & ".join([label, *[ratio_pm(c(a, w), c(b, w)) for w in (1, 2, 4)]]) + " \\\\")
    if not body:
        return None
    return table(
        "table",
        "Effect of each factor with the other held fixed, as a ratio of mean throughputs "
        "($\\pm$ 95\\% half-width) from Table~\\ref{tab:factorial}. Interface: "
        "\\code{io\\_uring} over \\code{epoll}. Loop: C over Python.",
        "tab:effects", "@{}lrrr@{}",
        ["Effect & $N{=}1$ & $N{=}2$ & $N{=}4$ \\\\"], body, colsep="2pt",
        note=("$^{a}$ \\code{py-epoll-batch} over \\code{py-epoll}: the same interface and "
              "the same system calls, with the GIL released once for all the \\code{recv} and "
              "\\code{send} calls of a pass instead of once per call. The batched loop also "
              "runs less Python per request. $^{b}$ \\code{py-uring} over "
              "\\code{py-epoll-batch}: both release the GIL about twice per pass, but "
              "\\code{py-uring} runs more Python per event, so this ratio is not the effect "
              "of the interface alone." if controls else None))


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


APP_ENGINES = ["uringpy-app", "uringpy-app-batch", "c-epoll-app", "c-epoll-app-batch",
               "asyncio-app", "asyncio-proto-app", "uvloop-proto-app"]


def tab_app(d):
    body, used = [], []
    last_gil = None
    for gil in ("on", "off"):
        for engine in APP_ENGINES:
            for mode in MODES:
                cs = [d.get("app", gil, engine, mode, w) for w in (1, 2, 4)]
                if not any(cs):
                    continue
                if last_gil is not None and gil != last_gil:
                    body.append("\\midrule")
                last_gil = gil
                used += cs
                c1, c2, c4 = cs
                flag = "$^\\dagger$" if any(c is not None and c.n and c.cv > 5 for c in cs) else ""
                # Acquisitions per request are a hand-off count only where the
                # workers share one GIL.
                acq = _handoffs(c4) if mode == "thread" and gil == "on" else DASH
                body.append(" & ".join([
                    BUILD[gil], code(engine), mode, *[k_pm(c) for c in cs],
                    ratio_pm(c2, c1), ratio_pm(c4, c1) + flag, acq,
                    fnum(c4.csw if c4 else None, 3)
                    + ("$^\\ast$" if c4 and nan(c4.csw_per_request) and not nan(c4.csw) else ""),
                    fnum(c4.busy_cores if c4 else None, 2),
                    fnum(c4.avg("lat_p99_ms") if c4 else None, 1)]) + " \\\\")
    if not body:
        return None
    dagger = any("dagger" in line for line in body)
    star = any("ast$" in line for line in body)
    notes = []
    if any(line.startswith(BUILD["off"]) for line in body):
        notes.append("``no GIL'' is the free-threaded build.")
    if star:
        notes.append("$^\\ast$ These servers do not count their requests; the switches are "
                     "divided by the request count of the client, scaled from the measured "
                     "interval to the life of the server.")
    if dagger:
        notes.append("$^\\dagger$ A configuration in this row had a coefficient of variation "
                     "above 5\\%.")
    return table(
        "table*",
        "Application-handler workload: every request calls a Python handler. Throughput in "
        f"thousands of requests per second (mean $\\pm$ 95\\% half-width, {run_count(used)}), "
        "scaling, and at four workers: GIL acquisitions per request ($g$) where the reactor "
        "counts them and the workers share one GIL, voluntary context switches per request "
        "(c.sw.), busy server cores and 99th-percentile latency.",
        "tab:app", "@{}lllrrrrrrrrr@{}",
        ["Build & Engine & Workers & $N{=}1$ & $N{=}2$ & $N{=}4$ & $S_2$ & $S_4$ "
         "& $g$ & c.sw. & $C_4$ & p99 (ms) \\\\"], body, colsep="3pt",
        note=" ".join(notes) or None)


# Requests served per GIL acquisition: engine -> cap shown in the table.
GILBATCH_ENGINES = [("uringpy-app", "---"), ("uringpy-app-batch1", "1"),
                    ("uringpy-app-batch2", "2"), ("uringpy-app-batch4", "4"),
                    ("uringpy-app-batch8", "8"), ("uringpy-app-batch16", "16"),
                    ("uringpy-app-batch64", "64"), ("uringpy-app-batch", "none")]


def tab_gilbatch(d):
    """Dose-response: thread scaling against requests served per GIL acquisition."""
    body, used = [], []
    for engine, cap in GILBATCH_ENGINES:
        c1, c2, c4 = (d.get("gilbatch", "on", engine, "thread", w) for w in (1, 2, 4))
        if not c1 or not c4:
            continue
        used += [c1, c2, c4]
        util = c4.gil_util
        body.append(" & ".join([
            cap, fnum(c4.handoffs, 3), k_pm(c1), k_pm(c4),
            ratio_pm(c2, c1) + _flagged(c2, c1), ratio_pm(c4, c1) + _flagged(c4, c1),
            fnum(c4.gil_hold_us, 2), fnum(c4.gil_wait_us, 2),
            "n/a" if not nan(util) and util > 1.02 else fnum(util, 2),
            fnum(c4.csw, 3)]) + " \\\\")
    if len(body) < 3:
        return None
    dagger = any("dagger" in line for line in body)
    return table(
        "table*",
        "Requests served per GIL acquisition (\\code{uringpy} with the handler, worker "
        "threads, GIL build). Cap: the largest number of requests handled under one "
        "acquisition; ``---'' is the reactor that takes the GIL for each request without "
        "the batching code, ``none'' takes it once for all requests found in a pass. "
        "Measured at four workers: GIL acquisitions per request $g$, hold time $t_{p,4}$ and "
        "wait time $w_4$ per request in $\\mu$s, GIL utilisation "
        "$U_4=\\bar{x}_4\\,t_{p,4}$, voluntary context switches per request (c.sw.). Throughput in "
        f"thousands of requests per second (mean $\\pm$ 95\\% half-width, {run_count(used)}).",
        "tab:gilbatch", "@{}rrrrrrrrrr@{}",
        ["Cap & $g$ & $\\bar{x}_1$ & $\\bar{x}_4$ & $S_2$ & $S_4$ & $t_{p,4}$ & $w_4$ "
         "& $U_4$ & c.sw. \\\\"], body, colsep="4pt",
        note=("$^\\dagger$ A configuration in this ratio had a coefficient of variation above "
              "5\\%." if dagger else None))


def tab_load(d):
    """Connection sweep: the same engines at lighter and heavier load."""
    engines = [e for e in ("uringpy", "py-uring", "py-epoll", "uringpy-app", "uringpy-app-batch")
               if e in d.values("load", "on", "engine")]
    conns = sorted(d.values("load", "on", "conns"))
    if not engines or len(conns) < 2:
        return None
    body, used = [], []
    for i, engine in enumerate(engines):
        if i:
            body.append("\\midrule")
        for n, conn in enumerate(conns):
            c1 = d.get("load", "on", engine, "thread", 1, conns=conn)
            c4 = d.get("load", "on", engine, "thread", 4, conns=conn)
            if not c1 and not c4:
                continue
            used += [c1, c4]
            body.append(" & ".join([
                code(engine) if n == 0 else "", str(conn),
                fnum(c1.mean / 1e3 if c1 and c1.n else None, 1),
                fnum(c4.mean / 1e3 if c4 and c4.n else None, 1),
                ratio_pm(c4, c1) + _flagged(c4, c1),
                DASH if c4 is None else "0" if c4.handoffs == 0 else fnum(c4.handoffs, 2),
                fnum(c4.csw if c4 else None, 2)]) + " \\\\")
    dagger = any("dagger" in line for line in body)
    left_out = sum(f.get("excluded", 0) for f in d.folders if f["experiment"] == "load")
    notes = []
    raised = any("nofile" in ((f["meta"].get("params") or {}).get("docker_opts") or "")
                 for f in d.folders if f["experiment"] == "load")
    if left_out and raised:
        notes.append("The rows with 1600 connections were measured in a later run with the "
                     f"server's limit on open files raised; {left_out} earlier runs, made "
                     "under a limit below that number of connections, are not shown "
                     "(Section~\\ref{sec:threats}).")
    elif left_out:
        notes.append(f"{left_out} runs with 1600 connections are not shown: that number "
                     "exceeded the server's limit on open files "
                     "(Section~\\ref{sec:threats}).")
    if dagger:
        notes.append("$^\\dagger$ A configuration in this ratio had a coefficient of variation "
                     "above 5\\%.")
    return table(
        "table",
        "Load varied: keep-alive connections opened by the client (worker threads, GIL "
        "build). Mean throughput in thousands of requests per second at one and four workers "
        f"({run_count(used)}), scaling with its 95\\% half-width, and at four workers per "
        "request: GIL hand-off opportunities $g$ and voluntary context switches (c.sw.).",
        "tab:load", "@{}lrrrrrr@{}",
        ["Engine & Conn. & $\\bar{x}_1$ & $\\bar{x}_4$ & $S_4$ & $g$ & c.sw. \\\\"], body,
        colsep="2.5pt", note=" ".join(notes) or None)


LOOP_ENGINES = [("asyncio", "\\code{epoll} (selector loop)"), ("uvloop", "libuv"),
                ("uringcore", "\\code{io\\_uring}"), ("uringloop", "\\code{io\\_uring}")]


def tab_loops(d):
    """asyncio-compatible event loops under one server script (streams API):
    the standard loop, uvloop and the loops built on io_uring."""
    present = d.values("loops", "on", "engine")
    if not any(e in present for e in ("uringcore", "uringloop")):
        return None         # without an io_uring loop this repeats tab_scaling
    workers = sorted(w for w in d.values("loops", "on", "workers"))
    top = max(workers)
    body, used = [], []
    for engine, iface in LOOP_ENGINES:
        for mode in MODES:
            cs = [d.get("loops", "on", engine, mode, w) for w in workers]
            if not any(cs):
                continue
            used += cs
            c1, cn = cs[0], cs[-1]
            body.append(" & ".join([
                code(engine), iface, mode, *[k_pm(c) for c in cs],
                ratio_pm(cn, c1) + _flagged(cn, c1),
                fnum(cn.csw if cn else None, 3), fnum(cn.busy_cores if cn else None, 2),
                fnum(cn.avg("lat_p99_ms") if cn else None, 1)]) + " \\\\")
    if not body:
        return None
    dagger = any("dagger" in line for line in body)
    cols = " & ".join(f"$N{{=}}{w}$" for w in workers)
    return table(
        "table*",
        "Event loops for \\code{asyncio} under one server script (streams API, 13-byte "
        "body, GIL build): the standard loop, \\code{uvloop}, and the loop built on "
        "\\code{io\\_uring}. Throughput in thousands of requests per second (mean $\\pm$ "
        f"95\\% half-width, {run_count(used)}) at $N$ workers, scaling $S_{top}$, and at "
        f"{top} workers: voluntary context switches per request (c.sw., divided by the "
        "client's request count), busy server cores and 99th-percentile latency.",
        "tab:loops", "@{}lll" + "r" * (len(workers) + 4) + "@{}",
        [f"Loop & Built on & Workers & {cols} & $S_{top}$ & c.sw. & $C_{top}$ & p99 (ms) \\\\"],
        body, colsep="4pt",
        note=("Measured in a supplementary run, with the container's limits on open files "
              "and on locked memory raised."
              + (" $^\\dagger$ A configuration in this ratio had a coefficient of variation "
                 "above 5\\%." if dagger else "")))


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


def _flagged(*cells):
    """Dagger for a ratio whose cells include one with CV above 5%."""
    return "$^\\dagger$" if any(c is not None and c.n and c.cv > 5 for c in cells) else ""


def tab_handler(d):
    """Cost model against measurement: handler work swept, GIL time measured.

    For each engine and amount of handler work: one-worker throughput x_1, the
    measured GIL hold time per request t_p at one worker, the GIL-held fraction
    f = t_p * x_1 (x_1 = 1/(t_c + t_p) for a saturated worker), the bound
    min(N, 1/f) at N = 4, the measured scaling of threads and of processes,
    and at four worker threads: GIL hold time and wait time per request, GIL
    acquisitions per request, and the GIL utilisation U_4 = x_4 * t_p,4 (the
    share of each second the GIL is held running handlers).
    """
    body, used = [], []
    engines = [e for e in ("uringpy-app", "uringpy-app-batch")
               if e in d.values("handler", "on", "engine")]
    dagger = False
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
            tp4 = t4.gil_hold_us if t4 else float("nan")
            util = tp4 * 1e-6 * t4.mean if t4 and not nan(tp4) else float("nan")
            acq = t4.acquires_per_request if t4 else float("nan")
            if nan(acq) and engine == "uringpy-app" and t4 and not nan(tp4):
                acq = 1.0  # one acquisition per call by construction (older runs lack the counter)
            flags = [_flagged(t2, t1), _flagged(t4, t1), _flagged(p4, p1), _flagged(f4, f1)]
            dagger = dagger or any(flags)
            body.append(" & ".join([
                "request" if engine == "uringpy-app" else "batch",
                str(work), k_pm(t1), fnum(tp, 2), fnum(f, 2), fnum(bound, 2),
                ratio_pm(t2, t1) + flags[0], ratio_pm(t4, t1) + flags[1],
                ratio_pm(p4, p1) + flags[2], ratio_pm(f4, f1) + flags[3],
                fnum(tp4, 2), fnum(t4.gil_wait_us if t4 else None, 2),
                fnum(acq, 3), "n/a" if util > 1.02 else fnum(util, 2)]) + " \\\\")
    if not body:
        return None
    return table(
        "table*",
        "Handler work swept (iterations of an interpreted loop added to every request), GIL "
        "build unless stated, with the GIL taken once per request (\\code{uringpy-app}) or "
        "once per batch of requests (\\code{uringpy-app-batch}). One-worker throughput $\\bar{x}_1$ in thousands of requests per "
        f"second (mean $\\pm$ 95\\% half-width, {run_count(used)}); GIL hold time per request "
        "$t_p$ at one worker; $f = t_p\\,\\bar{x}_1$; the bound $\\min(4, 1/f)$ "
        "of~\\eqref{eq:bound}; measured scaling of worker threads ($S_2$, $S_4$), of worker "
        "processes ($S_4^{\\mathrm{proc}}$) and of threads on the free-threaded build "
        "($S_4^{\\mathrm{ft}}$); and, at four worker threads, GIL hold time $t_{p,4}$ and wait "
        "time $w_4$ per request, GIL acquisitions per request $g$, and GIL utilisation "
        "$U_4 = \\bar{x}_4\\,t_{p,4}$.",
        "tab:handler", "@{}lrrrrrrrrrrrrr@{}",
        ["GIL per & Work & $\\bar{x}_1$ & $t_p$ ($\\mu$s) & $f$ & bound & $S_2$ & $S_4$ "
         "& $S_4^{\\mathrm{proc}}$ & $S_4^{\\mathrm{ft}}$ & $t_{p,4}$ & $w_4$ "
         "& $g$ & $U_4$ \\\\"], body, colsep="2pt",
        note=("$t_{p,4}$ and $w_4$ in $\\mu$s. n/a: with "
              "batching and long handlers the interpreter's switch interval interrupts a "
              "batch, so the recorded hold includes time waiting to resume."
              + (" $^\\dagger$ A configuration in this ratio had a coefficient of variation "
                 "above 5\\%." if dagger else "")))


def tab_probe(d):
    """Contention probe (gil_experiment.py): read from the newest probe-*.txt."""
    import glob
    import re
    files = sorted(glob.glob(os.path.join(d.results_dir or "", "probe-*.txt")))
    if not files:
        return None
    text = open(files[-1]).read()
    rows = re.findall(r"^\|\s*(\d+)\s*\|\s*([\d.]+) \(([\d.]+)\)\s*\|\s*([\d.]+)x\s*\|\s*([\d.]+)x"
                      r"\s*\|\s*([\d.]+) \(([\d.]+)\)\s*\|\s*([\d.]+)x\s*\|\s*([\d.]+)x\s*\|",
                      text, re.M)
    reps = re.search(r"reps=(\d+)", text)
    if not rows:
        return None
    body = [f"{k} & {pm} ({psd}) & {px} & {pmin} & {float(cm):.3f} ({float(csd):.3f}) & {cx} & {cmin} \\\\"
            for k, pm, psd, px, pmin, cm, csd, cx, cmin in rows]
    return table(
        "table",
        "Contention probe: time in seconds to process a fixed number of events while $K$ "
        "threads compete for the GIL, as mean (standard deviation) over "
        f"{reps.group(1) if reps else '?'} repetitions, with the slowdown relative to $K=0$ "
        "computed from the means and from the fastest repetition (min).",
        "tab:probe", "@{}rrrrrrr@{}",
        ["& \\multicolumn{3}{c}{Python loop} & \\multicolumn{3}{c}{C \\code{nogil} loop} \\\\",
         "$K$ & time (sd) & mean & min & time (sd) & mean & min \\\\"], body, colsep="3pt")


# --------------------------------------------------------------------------
# Figures (pgfplots source; drawn when the paper is built)
# --------------------------------------------------------------------------

# Three colours that remain distinguishable for colour-blind readers. Every
# series also has its own marker or line style, so a figure can be read in
# greyscale; a fourth series is drawn in dark grey, never in a fourth hue.
COLORS = {"sA": "2A78D6", "sB": "EB6834", "sC": "1BAF7A", "ink": "52514E"}

AXIS = ("tick label style={font=\\scriptsize}, label style={font=\\footnotesize}, "
        "legend style={font=\\scriptsize, draw=black!25, cells={anchor=west}, row sep=-1.5pt, "
        "inner sep=2pt}, grid=major, grid style={black!8}, axis line style={black!55}, "
        "tick style={black!55}, "
        "every axis plot/.append style={line width=0.8pt, mark size=1.9pt}")


def _colors():
    return "\n".join(f"\\definecolor{{{k}}}{{HTML}}{{{v}}}" for k, v in COLORS.items())


def _plot(style, points, legend=None, errors=False):
    """One \\addplot. points: (x, y) or (x, y, err, ...)."""
    pts = [p for p in points if not nan(p[0]) and not nan(p[1])]
    if not pts:
        return []
    coords = []
    for p in pts:
        s = f"({p[0]:.5g},{p[1]:.5g})"
        if errors:
            err = p[2] if len(p) > 2 and not nan(p[2]) else 0.0
            s += f" +- (0,{err:.4g})"
        coords.append(s)
    opts = style
    if errors:
        opts += (", error bars/.cd, y dir=both, y explicit, "
                 "error bar style={line width=0.4pt}, error mark options={rotate=90, "
                 "mark size=1.5pt, line width=0.4pt}")
    lines = [f"\\addplot[{opts}] coordinates {{{' '.join(coords)}}};"]
    if legend:
        lines.append(f"\\addlegendentry{{{legend}}}")
    else:
        lines[0] = lines[0].replace("\\addplot[", "\\addplot[forget plot, ", 1)
    return lines


def _labels(points, anchors):
    """Direct labels: a node beside each point that carries one, on the side
    given for it (a tikz anchor), so labels do not collide with other marks."""
    out = []
    for p in points:
        if len(p) > 3 and p[3]:
            out.append(f"\\node[font=\\scriptsize, inner sep=3pt, anchor={anchors.get(p[3], 'south west')}] "
                       f"at (axis cs:{p[0]:.5g},{p[1]:.5g}) {{{p[3]}}};")
    return out


LEGEND_BELOW = ("legend columns=2, legend style={at={(0.5,-0.27)}, anchor=north, "
                "font=\\scriptsize, draw=black!25, cells={anchor=west}, column sep=4pt, "
                "row sep=-1.5pt, inner sep=2pt}")


LEGEND_BELOW_1 = LEGEND_BELOW.replace("legend columns=2", "legend columns=1")


def _figure(env, caption, label, body):
    return "\n".join([f"\\begin{{{env}}}[t]", "\\centering", _colors(), *body,
                      f"\\caption{{{caption}}}", f"\\label{{{label}}}", f"\\end{{{env}}}", ""])


def _scaling_point(c1, c4, x, label=None):
    if c1 is None or c4 is None or not c1.n or not c4.n or nan(x) or x <= 0:
        return None
    r, h = ratio_ci95(c4.rps, c1.rps)
    return (x, r, h, label)


def _handoff_points(d):
    """The series of fig_handoffs: {name: [(csw per request, S_4, half-width, label)]}."""
    def pt(exp, engine, label=None):
        c1 = d.get(exp, "on", engine, "thread", 1)
        c4 = d.get(exp, "on", engine, "thread", 4)
        return _scaling_point(c1, c4, c4.csw if c4 else float("nan"), label)

    def series(pairs):
        return sorted((p for p in (pt(*a) for a in pairs) if p), key=lambda p: p[0])

    uring = series([("gilbatch", e) for e, _ in GILBATCH_ENGINES])
    if not uring:      # no cap sweep: the two reactors of the handler experiment
        uring = series([("app", "uringpy-app"), ("app", "uringpy-app-batch")])
    return {
        "cloops": series([("factorial", "uringpy"), ("factorial", "c-epoll")]),
        "loops": series([("factorial", e, code(e))
                         for e in ("py-epoll", "py-epoll-batch", "py-uring")]),
        "uring": uring,
        "epoll": series([("app", "c-epoll-app"), ("app", "c-epoll-app-batch")]),
        "others": series([("scaling", e) for e in ("asyncio", "asyncio-proto", "uvloop",
                                                   "uvloop-proto")]
                         + [("app", e) for e in ("asyncio-app", "asyncio-proto-app",
                                                 "uvloop-proto-app")]),
        "held": series([("factorial", "py-uring-held", code("py-uring-held"))]),
        "uring_loops": series([("loops", e, code(e)) for e in ("uringcore", "uringloop")]),
    }


# Bands of the figure quoted in the text: configurations that hardly ever
# sleep, and configurations that sleep more than once per request.
FIG_LOW_CSW, FIG_HIGH_CSW = 0.02, 1.0


def _figure_numbers(d):
    pts = _handoff_points(d)
    rest = [p for name, ps in pts.items() if name not in ("held", "uring_loops") for p in ps]
    out = {"fig:handoffs/points": f"{len(rest) + len(pts['held'])}"}
    low = [p for p in rest if p[0] <= FIG_LOW_CSW]
    high = [p for p in rest if p[0] >= FIG_HIGH_CSW]
    mid = [p for p in rest if FIG_LOW_CSW < p[0] < FIG_HIGH_CSW]
    for name, band in (("low", low), ("mid", mid), ("high", high)):
        if band:
            out[f"fig:handoffs/{name}-n"] = f"{len(band)}"
            out[f"fig:handoffs/{name}-csw-min"] = f"{min(p[0] for p in band):.3f}"
            out[f"fig:handoffs/{name}-csw-max"] = f"{max(p[0] for p in band):.3f}"
            out[f"fig:handoffs/{name}-S-min"] = f"{min(p[1] for p in band):.2f}"
            out[f"fig:handoffs/{name}-S-max"] = f"{max(p[1] for p in band):.2f}"
    out["fig:handoffs/low-threshold"] = f"{FIG_LOW_CSW:g}"
    return out


def fig_handoffs(d):
    """Thread scaling against voluntary context switches per request: every
    thread-mode configuration of the GIL build measured at 1 and 4 workers and
    400 connections. Context switches are available for every engine, GIL
    hand-off opportunities (g) only for ours, so this axis can carry the
    asyncio and uvloop baselines as well."""
    pts = _handoff_points(d)
    cloops, loops, uring = pts["cloops"], pts["loops"], pts["uring"]
    epoll, others, held = pts["epoll"], pts["others"], pts["held"]
    uring_loops = pts["uring_loops"]
    everything = cloops + loops + uring + epoll + others + held + uring_loops
    if len(everything) < 2:
        return None
    xs = [p[0] for p in everything]
    lo, hi = min(xs) / 2, max(xs) * 2.5
    top = max([p[1] for p in everything] + [2.5])
    # label -> (direction in degrees, length of the leader line)
    pins = {code("py-epoll"): (205, "7mm"), code("py-epoll-batch"): (90, "4mm"),
            code("py-uring"): (270, "6mm"), code("py-uring-held"): (270, "4mm"),
            code("uringcore"): (90, "5mm"), code("uringloop"): (60, "8mm")}
    ceiling = (d.get("factorial", "on", "uringpy", "process", 1),
               d.get("factorial", "on", "uringpy", "process", 4))
    body = ["\\begin{tikzpicture}",
            f"\\begin{{axis}}[{AXIS}, width=\\columnwidth, height=62mm, xmode=log, "
            f"xmin={lo:g}, xmax={hi:g}, ymin=0, ymax={math.ceil(top * 2 + 0.3) / 2:g}, "
            "xlabel={voluntary context switches per request, four worker threads}, "
            f"ylabel={{thread scaling $S_4$}}, {LEGEND_BELOW}]"]
    body += ["\\addplot[forget plot, black!35, line width=0.5pt] coordinates "
             f"{{({lo:g},1) ({hi:g},1)}};"]
    body += _plot("only marks, ink, mark=asterisk, mark size=2.4pt", cloops,
                  "C loop, no Python", errors=True)
    # legend in two columns: short entries left, long entries right
    body += _plot("sB, mark=square*, mark options={fill=sB}", uring,
                  "C reactor + handler, \\code{io\\_uring}", errors=True)
    body += _plot("only marks, sA, mark=*, mark options={fill=sA}", loops,
                  "loop in Python", errors=True)
    body += _plot("only marks, sC, mark=triangle*, mark options={fill=sC}, mark size=2.4pt",
                  epoll, "C reactor + handler, \\code{epoll}", errors=True)
    body += _plot("only marks, ink, mark=diamond, mark size=2.4pt", others,
                  "\\code{asyncio}, \\code{uvloop}", errors=True)
    if all(c is not None and c.n for c in ceiling):
        top_s = ceiling[1].mean / ceiling[0].mean
        body += [f"\\addplot[ink, densely dashed, line width=0.5pt] coordinates "
                 f"{{({lo:g},{top_s:.4g}) ({hi:g},{top_s:.4g})}};",
                 "\\addlegendentry{C loop as processes}"]
    body += _plot("only marks, ink, mark=o", held, None, errors=True)
    body += _plot("only marks, ink, mark=diamond*, mark options={fill=ink}, mark size=2.4pt",
                  uring_loops, "\\code{asyncio} loop on \\code{io\\_uring}", errors=True)
    for p in loops + held + uring_loops:
        angle, dist = pins.get(p[3], (90, "4mm"))
        body.append(f"\\node[inner sep=0pt, pin={{[font=\\scriptsize, inner sep=1pt, "
                    f"pin distance={dist}, pin edge={{black!50, thin}}]{angle}:{{{p[3]}}}}}] "
                    f"at (axis cs:{p[0]:.5g},{p[1]:.5g}) {{}};")
    body += ["\\end{axis}", "\\end{tikzpicture}"]
    return _figure(
        "figure",
        "Thread scaling at four workers against voluntary context switches of the server "
        "per request (GIL build, 400 connections; bars are 95\\% half-widths; the grey line "
        "marks no gain over one worker, the dashed line the scaling of the C loop run as "
        "processes). Shown are the thread-mode configurations of "
        "Tables~\\ref{tab:factorial}, \\ref{tab:scaling}, \\ref{tab:app} "
        "and~\\ref{tab:gilbatch}, an engine that appears in two of them once. The connected "
        "points are one reactor with the number of requests served per GIL acquisition "
        "varied. For "
        "\\code{asyncio} and \\code{uvloop} the request count is the client's. "
        "\\code{py-uring-held} switches rarely but holds the GIL while the kernel performs "
        "the sends.",
        "fig:handoffs", body)


def fig_scaling(d):
    """Throughput against workers, both builds: threads solid, processes dashed."""
    engines = [("uringpy", "sA", "*", "o"), ("asyncio-proto", "sB", "square*", "square"),
               ("uvloop-proto", "sC", "triangle*", "triangle")]
    panels = []
    for gil, title in (("on", "GIL build"), ("off", "free-threaded build")):
        plots = []
        for engine, color, solid, hollow in engines:
            for mode in MODES:
                cs = [(w, d.get("scaling", gil, engine, mode, w)) for w in (1, 2, 3, 4)]
                if not any(c for _, c in cs):
                    cs = [(w, d.get("baselines", gil, engine, mode, w)) for w in (1, 2, 3, 4)]
                pts = [(w, c.mean / 1e3, c.hw / 1e3) for w, c in cs if c is not None and c.n]
                style = (f"{color}, mark={solid}, mark options={{fill={color}}}"
                         if mode == "thread" else
                         f"{color}, densely dashed, mark={hollow}, mark options={{solid}}")
                short = "threads" if mode == "thread" else "processes"
                plots += _plot(style, pts, f"{code(engine)}, {short}", errors=True)
        if plots:
            panels.append((title, plots))
    if not panels:
        return None
    top = max(c.mean for k, c in d.cells.items()
              if k[0] in ("scaling", "baselines") and c.n) / 1e3
    top = 50 * math.ceil(top * 1.05 / 50)
    body = ["\\begin{tikzpicture}",
            "\\begin{groupplot}[group style={group size=2 by 1, horizontal sep=14mm}, "
            f"{AXIS}, width=0.46\\textwidth, height=58mm, xtick={{1,2,3,4}}, xmin=0.8, xmax=4.2, "
            f"ymin=0, ymax={top:g}, xlabel={{workers $N$}}, "
            f"ylabel={{thousand requests per second}}, {LEGEND_BELOW}]"]
    for title, plots in panels:
        body += [f"\\nextgroupplot[title={{\\footnotesize {title}}}]"] + plots
    body += ["\\end{groupplot}", "\\end{tikzpicture}"]
    return _figure(
        "figure*",
        "Transport path: throughput against the number of workers, as threads of one "
        "interpreter (solid lines, filled markers) and as one process per worker (dashed "
        "lines, open markers). Bars are 95\\% half-widths; most are smaller than the markers. "
        "\\code{uvloop} is not available on the free-threaded build.",
        "fig:scaling", body)


def fig_handler(d):
    """The handler sweep: (a) thread scaling against the bound, (b) throughput
    at four workers, threads against processes and the process baselines."""
    works = sorted(k[7] for k in d.cells if k[0] == "handler" and k[1] == "on"
                   and k[2] == "uringpy-app" and k[3] == "thread" and k[4] == 1)
    if len(works) < 3:
        return None

    def c(engine, mode, w, work, gil="on"):
        return d.get("handler", gil, engine, mode, w, work=work)

    tp = {}
    for work in works:
        t1 = c("uringpy-app", "thread", 1, work)
        tp[work] = t1.gil_hold_us if t1 and t1.n else float("nan")
    works = [w for w in works if not nan(tp[w]) and tp[w] > 0]
    if len(works) < 3:
        return None

    def scaling(engine, mode, gil="on"):
        return [p[:3] for p in (_scaling_point(c(engine, mode, 1, w, gil), c(engine, mode, 4, w, gil),
                                               tp[w]) for w in works) if p]

    def absolute(engine, mode):
        out = []
        for w in works:
            cell = c(engine, mode, 4, w)
            if cell is not None and cell.n:
                out.append((tp[w], cell.mean / 1e3, cell.hw / 1e3))
        return out

    bound = []
    for w in works:
        t1 = c("uringpy-app", "thread", 1, w)
        f = tp[w] * 1e-6 * t1.mean
        bound.append((tp[w], min(4.0, 1.0 / f)))
    xmin = 10 ** math.floor(math.log10(min(tp.values())) - 0.05)
    xmax = 10 ** math.ceil(math.log10(max(tp.values())) + 0.05)
    common = (f"{AXIS}, width=0.46\\textwidth, height=60mm, xmode=log, xmin={xmin:g}, "
              f"xmax={xmax:g}, xlabel={{GIL hold time per request $t_p$ ($\\mu$s), one worker}}")
    a = ["\\nextgroupplot[title={\\footnotesize (a) scaling at four workers}, ymin=0, ymax=4.3, "
         f"ylabel={{scaling $S_4$}}, {LEGEND_BELOW_1}]",
         "\\addplot[ink, line width=0.6pt] coordinates {"
         + " ".join(f"({x:.5g},{y:.4g})" for x, y in bound) + "};",
         "\\addlegendentry{bound $\\min(4, 1/f)$}"]
    a += _plot("sA, mark=*, mark options={fill=sA}", scaling("uringpy-app", "thread"),
               "threads, GIL per request", errors=True)
    a += _plot("sB, mark=square*, mark options={fill=sB}", scaling("uringpy-app-batch", "thread"),
               "threads, GIL per batch", errors=True)
    a += _plot("sC, densely dashed, mark=triangle, mark options={solid}, mark size=2.4pt",
               scaling("uringpy-app", "process"), "processes", errors=True)
    a += _plot("ink, densely dotted, mark=diamond, mark options={solid}, mark size=2.4pt",
               scaling("uringpy-app", "thread", "off"), "threads, free-threaded", errors=True)
    b = ["\\nextgroupplot[title={\\footnotesize (b) throughput at four workers}, ymode=log, "
         f"ylabel={{thousand requests per second}}, {LEGEND_BELOW_1}]"]
    b += _plot("sA, mark=*, mark options={fill=sA}", absolute("uringpy-app", "thread"),
               "\\code{uringpy} threads, GIL per request")
    b += _plot("sB, mark=square*, mark options={fill=sB}", absolute("uringpy-app-batch", "thread"),
               "\\code{uringpy} threads, GIL per batch")
    b += _plot("sA, densely dashed, mark=o, mark options={solid}",
               absolute("uringpy-app", "process"), "\\code{uringpy} processes")
    b += _plot("sC, densely dashed, mark=triangle, mark options={solid}, mark size=2.4pt",
               absolute("uvloop-proto-app", "process"), "\\code{uvloop} processes (Protocol API)")
    b += _plot("ink, densely dashed, mark=diamond, mark options={solid}, mark size=2.4pt",
               absolute("asyncio-proto-app", "process"), "\\code{asyncio} processes (Protocol API)")
    body = ["\\begin{tikzpicture}",
            f"\\begin{{groupplot}}[group style={{group size=2 by 1, horizontal sep=16mm}}, {common}]",
            *a, *b, "\\end{groupplot}", "\\end{tikzpicture}"]
    return _figure(
        "figure*",
        "Handler cost swept (GIL build unless stated). The horizontal axis is the measured "
        "time one request holds the GIL on one worker. (a)~Scaling at four workers against "
        "the bound of~\\eqref{eq:bound}; bars are 95\\% half-widths. (b)~Throughput at four "
        "workers: worker threads of one interpreter (solid) against one process per worker "
        "(dashed), for \\code{uringpy} and for the two baselines through the Protocol API.",
        "fig:handler", body)


FIGURES = {"handoffs": fig_handoffs, "scaling": fig_scaling, "handler": fig_handler}


# --------------------------------------------------------------------------
# Numbers quoted in the text of the paper
# --------------------------------------------------------------------------
#
# The paper writes \V{key} wherever it quotes a measurement, and numbers.tex
# defines every key, so no number in the text is typed by hand. Keys:
#
#   <quantity>:<experiment>/<g|f>/<engine>/<mode>/<workers>[/s<body bytes>]
#              [/b<batch cap>][/h<handler work>][/c<connections>]
#
# g is the GIL build, f the free-threaded build; the bracketed parts appear
# only when they differ from the defaults (13 bytes, no cap, no added work, 400
# connections). Quantities:
#
#   x, xpm   throughput in thousands of requests per second, without and with
#            its 95% half-width            S, Spm   scaling against one worker
#   sys      system calls per request      ho       GIL releases or acquisitions
#                                                   per request (limit on hand-offs)
#   csw      voluntary context switches per request
#   cpe      completions per io_uring_enter
#   C        busy server cores             E        throughput per busy core
#                                                   relative to one worker
#   p50, p99 latency in ms                 cv       coefficient of variation, %
#   tp, w    GIL hold and wait time per request, microseconds
#   U        GIL utilisation x * tp        f        tp * x (one worker)
#   bound    min(4, 1/f)                   tau      1/x - tp, microseconds
#   us       1/x per worker: workers / x, microseconds
#
# and r:<name>, rpm:<name> for the ratios listed in _ratio_names(), meta:<name>
# for counts over the whole data set, fig:handoffs/<band>-<quantity> for the
# ranges of the points in fig_handoffs.

def _base(key):
    exp, gil, engine, mode, w, size, batch, work, conns = key
    s = f"{exp}/{'g' if gil == 'on' else 'f'}/{engine}/{mode}/{w}"
    if size != 13:
        s += f"/s{size}"
    if batch:
        s += f"/b{batch}"
    if work:
        s += f"/h{work}"
    if conns != 400:
        s += f"/c{conns}"
    return s


def _math(s):
    """A table string ('140.7 $\\pm$ 1.2') for use inside math mode."""
    return s.replace("$", "")


def _ratio_names():
    """(name, numerator, denominator) as cell names of the form used in keys."""
    out = []
    for n in (1, 2, 4):
        def fac(engine, mode="thread", n=n):
            return f"factorial/g/{engine}/{mode}/{n}"
        out += [(f"iface-c/{n}", fac("uringpy"), fac("c-epoll")),
                (f"iface-py/{n}", fac("py-uring"), fac("py-epoll")),
                (f"loop-uring/{n}", fac("uringpy"), fac("py-uring")),
                (f"loop-epoll/{n}", fac("c-epoll"), fac("py-epoll")),
                (f"handoff-epoll/{n}", fac("py-epoll-batch"), fac("py-epoll")),
                (f"iface-batched/{n}", fac("py-uring"), fac("py-epoll-batch")),
                (f"pyuring-over-cepoll/{n}", fac("py-uring"), fac("c-epoll")),
                (f"pyuring-over-uringpy/{n}", fac("py-uring"), fac("uringpy")),
                (f"pybatch-over-pyuring/{n}", fac("py-epoll-batch"), fac("py-uring")),
                (f"pybatch-over-cepoll/{n}", fac("py-epoll-batch"), fac("c-epoll")),
                (f"held/{n}", fac("py-uring-held"), fac("py-uring"))]
    for build in ("g", "f"):
        for n in (1, 2, 3, 4):
            for base in ("asyncio", "asyncio-proto", "uvloop", "uvloop-proto"):
                u = f"scaling/{build}/uringpy/thread/{n}"
                out += [(f"uringpy-over-{base}/thread/{build}/{n}", u,
                         f"scaling/{build}/{base}/thread/{n}"),
                        (f"uringpy-over-{base}/process/{build}/{n}", u,
                         f"scaling/{build}/{base}/process/{n}")]
        for n in (1, 2, 4):
            a = f"app/{build}/"
            out += [(f"gilbatch-gain/{build}/{n}", a + f"uringpy-app-batch/thread/{n}",
                     a + f"uringpy-app/thread/{n}"),
                    (f"gilbatch-gain-epoll/{build}/{n}", a + f"c-epoll-app-batch/thread/{n}",
                     a + f"c-epoll-app/thread/{n}"),
                    (f"app-iface/{build}/{n}", a + f"uringpy-app/thread/{n}",
                     a + f"c-epoll-app/thread/{n}"),
                    (f"app-iface-batch/{build}/{n}", a + f"uringpy-app-batch/thread/{n}",
                     a + f"c-epoll-app-batch/thread/{n}"),
                    (f"app-iface-process/{build}/{n}", a + f"uringpy-app/process/{n}",
                     a + f"c-epoll-app/process/{n}")]
            for base in ("asyncio-app", "asyncio-proto-app", "uvloop-proto-app"):
                for mine in ("uringpy-app", "uringpy-app-batch", "c-epoll-app-batch"):
                    for mm in MODES:
                        for bm in MODES:
                            out.append((f"{mine}/{mm}-over-{base}/{bm}/{build}/{n}",
                                        a + f"{mine}/{mm}/{n}", a + f"{base}/{bm}/{n}"))
    # across experiments: the bare Python loop against asyncio, the capped
    # io_uring loop against the epoll loop, timed against untimed runs
    out += [("pyepoll-over-asyncio/1", "factorial/g/py-epoll/thread/1",
             "scaling/g/asyncio/thread/1"),
            ("pyepoll-over-asyncio-proto/1", "factorial/g/py-epoll/thread/1",
             "scaling/g/asyncio-proto/thread/1"),
            ("cap1-over-cepoll/1", "batch/g/uringpy/thread/1/b1", "factorial/g/c-epoll/thread/1"),
            ("uvloop-over-asyncio/1", "scaling/g/uvloop/thread/1", "scaling/g/asyncio/thread/1"),
            ("uvloop-proto-over-asyncio-proto/1", "scaling/g/uvloop-proto/thread/1",
             "scaling/g/asyncio-proto/thread/1"),
            ("timed-over-untimed/4", "gilbatch/g/uringpy-app/thread/4",
             "app/g/uringpy-app/thread/4")]
    for conns in ("/c16", "/c64", ""):
        out += [(f"load-batch-gain{conns or '/c400'}",
                 f"load/g/uringpy-app-batch/thread/4{conns}", f"load/g/uringpy-app/thread/4{conns}"),
                (f"load-pyuring-over-pyepoll{conns or '/c400'}",
                 f"load/g/py-uring/thread/4{conns}", f"load/g/py-epoll/thread/4{conns}")]
    # the handler's cost on one worker, and the two builds against each other
    out += [("handler-cost/1", "app/g/uringpy-app/thread/1", "scaling/g/uringpy/thread/1"),
            ("uringpy-ft-over-gil/4", "scaling/f/uringpy/thread/4", "scaling/g/uringpy/thread/4"),
            ("gil-batch-over-ft/4", "app/g/uringpy-app-batch/thread/4",
             "app/f/uringpy-app/thread/4")]
    for base in ("asyncio", "asyncio-proto"):
        out.append((f"{base}-ft-over-gil/1", f"scaling/f/{base}/thread/1",
                    f"scaling/g/{base}/thread/1"))
    return out


def numbers(d):
    """{key: value} of everything the text quotes."""
    out, by_name = {}, {}
    for key, c in d.cells.items():
        by_name[_base(key)] = (key, c)
    for name, (key, c) in by_name.items():
        if not c.n:
            continue
        exp, gil, engine, mode, w = key[:5]
        digits = 1 if c.mean >= 10e3 else 2
        out[f"x:{name}"] = f"{c.mean / 1e3:.{digits}f}"
        out[f"xpm:{name}"] = _math(k_pm(c))
        out[f"us:{name}"] = f"{w / c.mean * 1e6:.1f}"
        out[f"n:{name}"] = str(c.n)
        for q, v, fmt in (("sys", c.syscalls_per_request, ".3f"), ("ho", c.handoffs, ".3f"),
                          ("csw", c.csw, ".3f"), ("cpe", c.completions_per_enter, ".0f"),
                          ("C", c.busy_cores, ".2f"), ("p50", c.avg("lat_p50_ms"), ".1f"),
                          ("p99", c.avg("lat_p99_ms"), ".1f"), ("cv", c.cv, ".1f"),
                          ("tp", c.gil_hold_us, ".2f"), ("w", c.gil_wait_us, ".2f"),
                          ("U", c.gil_util, ".2f"), ("cli", c.avg("client_cpu_pct"), ".0f")):
            if not nan(v):
                out[f"{q}:{name}"] = format(v, fmt)
        if not nan(c.gil_hold_us):
            out[f"tau:{name}"] = f"{1e6 / c.mean - c.gil_hold_us:.1f}"
        one = d.cells.get(key[:4] + (1,) + key[5:])
        if one is not None and one.n:
            if w != 1:
                out[f"S:{name}"] = _math(ratio_pm(c, one).split(" ")[0])
                out[f"Spm:{name}"] = _math(ratio_pm(c, one))
                e = _efficiency(one, c)
                if not nan(e):
                    out[f"E:{name}"] = f"{e:.2f}"
            tp1 = one.gil_hold_us
            if not nan(tp1):
                f = tp1 * 1e-6 * one.mean
                out[f"f:{name}"] = f"{f:.2f}"
                out[f"bound:{name}"] = f"{min(4.0, 1 / f):.2f}"
        other = d.cells.get(key[:3] + ("process",) + key[4:])
        if mode == "thread" and other is not None and other.n:
            out[f"r:thread-over-process:{name}"] = _math(ratio_pm(c, other).split(" ")[0])
            out[f"rpm:thread-over-process:{name}"] = _math(ratio_pm(c, other))
    for name, num, den in _ratio_names():
        a, b = by_name.get(num), by_name.get(den)
        if a and b and a[1].n and b[1].n:
            out[f"r:{name}"] = _math(ratio_pm(a[1], b[1]).split(" ")[0])
            out[f"rpm:{name}"] = _math(ratio_pm(a[1], b[1]))
    # ratios within the sweeps
    for key, c in d.cells.items():
        exp, gil, engine, mode, w, size, batch, work, conns = key
        if not c.n:
            continue
        if exp == "batch" and batch:
            free = d.cells.get(key[:6] + (0,) + key[7:])
            if free is not None and free.n:
                out[f"rpm:cap/{batch}"] = _math(ratio_pm(c, free))
                out[f"r:cap/{batch}"] = _math(ratio_pm(c, free).split(" ")[0])
        if exp == "size" and engine == "uringpy":
            base = d.cells.get(key[:2] + ("asyncio-proto",) + key[3:])
            if base is not None and base.n:
                out[f"r:size/{size}"] = _math(ratio_pm(c, base).split(" ")[0])
            gbit = c.avg("transfer_mb_s") * 1.048576 * 8 / 1000
            if not nan(gbit):
                out[f"gbit:{_base(key)}"] = f"{gbit:.1f}"
        if exp == "handler" and engine == "uringpy-app-batch" and gil == "on":
            plain = d.cells.get(key[:2] + ("uringpy-app",) + key[3:])
            if plain is not None and plain.n:
                out[f"rpm:handler-batch-gain/{mode}/{w}/h{work}"] = _math(ratio_pm(c, plain))
                out[f"r:handler-batch-gain/{mode}/{w}/h{work}"] = \
                    _math(ratio_pm(c, plain).split(" ")[0])
        if exp == "handler" and mode == "thread" and w == 4 and gil == "on":
            for base in ("uringpy-app", "asyncio-proto-app", "uvloop-proto-app"):
                p = d.cells.get(key[:2] + (base, "process") + key[4:])
                if p is not None and p.n:
                    out[f"rpm:{engine}/thread-over-{base}/process/h{work}"] = \
                        _math(ratio_pm(c, p))
                    out[f"r:{engine}/thread-over-{base}/process/h{work}"] = \
                        _math(ratio_pm(c, p).split(" ")[0])
    out.update(_meta_numbers(d))
    out.update(_figure_numbers(d))
    out.update(_text_file_numbers(d))
    return out


def _meta_numbers(d):
    cells = [c for c in d.cells.values()]
    runs = sum(c.n + c.failed for c in cells)
    excluded = sum(f.get("excluded", 0) for f in d.folders)
    out = {"meta:runs": f"{runs}", "meta:cells": f"{len(cells)}",
           "meta:failed": f"{sum(c.failed for c in cells)}",
           "meta:excluded-runs": f"{excluded}",
           "meta:excluded-failed": f"{sum(f.get('excluded_failed', 0) for f in d.folders)}",
           "meta:runs-made": f"{runs + excluded}",
           "meta:cv-flagged": f"{sum(1 for c in cells if c.n and c.cv > 5)}"}
    rows = [r for c in cells for r in c.rows]
    cli = [c.avg("client_cpu_pct") for c in cells if c.n]
    cli = [v for v in cli if not nan(v)]
    if cli:
        out["meta:client-max-cell"] = f"{max(cli):.0f}"
    per_run = [v for v in (_num(r, "client_cpu_pct") for r in rows) if not nan(v)]
    if per_run:
        out["meta:client-max-run"] = f"{max(per_run):.0f}"
        out["meta:client-runs-over-85"] = f"{sum(1 for v in per_run if v > 85)}"
    steal = [v for r in rows for v in (_num(r, "server_steal_pct"), _num(r, "client_steal_pct"))
             if not nan(v)]
    if steal:
        out["meta:steal-max"] = f"{max(steal):.1f}"
    out["meta:non2xx-runs"] = f"{sum(1 for r in rows if _num(r, 'non_2xx') > 0)}"
    bad = [(_num(r, "socket_errors") / _num(r, "requests"), r) for r in rows
           if _num(r, "socket_errors") > 0 and _num(r, "requests") > 0]
    out["meta:sockerr-runs"] = f"{len(bad)}"
    out["meta:sockerr-max-pct"], out["meta:sockerr-experiments"] = "0", "none"
    if bad:
        out["meta:sockerr-max-pct"] = f"{100 * max(b[0] for b in bad):.2f}"
        out["meta:sockerr-experiments"] = ", ".join(sorted({b[1]['experiment'] for b in bad}))
    out["meta:handler-error-runs"] = f"{sum(1 for r in rows if _num(r, 'srv_handler_errors') > 0)}"
    # Socket-error runs outside the two longest handlers of the handler sweep.
    out["meta:sockerr-other"] = f"{sum(1 for _, r in bad if not (r['experiment'] == 'handler' and _num(r, 'handler_work') >= 1000))}"
    served = [v for f in d.folders for v in f.get("excluded_served", [])]
    if served:
        out["meta:excluded-served-min"] = f"{min(served):.0f}"
        out["meta:excluded-served-max"] = f"{max(served):.0f}"
    # Hand-off cost derived from throughput and hold time, tau = 1/x_4 - t_p,4,
    # for the reactor that takes the GIL once per request. It is a difference of
    # two numbers, so it is quoted only for the handler sizes at which the 95%
    # half-width of 1/x_4 is below one microsecond.
    taus = []
    for k, c in d.cells.items():
        if (k[:5] == ("handler", "on", "uringpy-app", "thread", 4) and c.n
                and not nan(c.gil_hold_us) and not nan(c.hw)):
            if 1e6 * c.hw / c.mean ** 2 < 1.0:
                taus.append((k[7], 1e6 / c.mean - c.gil_hold_us))
    if taus:
        out["meta:tau-min"] = f"{min(t for _, t in taus):.1f}"
        out["meta:tau-max"] = f"{max(t for _, t in taus):.1f}"
        out["meta:tau-n"] = f"{len(taus)}"
        out["meta:tau-max-work"] = f"{max(w for w, _ in taus)}"
    # Scaling of the six loops as threads on the free-threaded build.
    ft = []
    for engine, *_ in FACTORIAL_ROWS:
        c1 = d.get("factorial", "off", engine, "thread", 1)
        c4 = d.get("factorial", "off", engine, "thread", 4)
        if c1 is not None and c4 is not None and c1.n and c4.n:
            ft.append(c4.mean / c1.mean)
    if ft:
        out["meta:factorial-ft-S-min"] = f"{min(ft):.2f}"
        out["meta:factorial-ft-S-max"] = f"{max(ft):.2f}"
    # Python a loop adds over the C loop on the same interface, on one worker:
    # extra time per request, and that time as a share of the request (an
    # estimate of f for loops whose GIL hold time is not instrumented).
    for py, c_loop in (("py-epoll", "c-epoll"), ("py-epoll-batch", "c-epoll"),
                       ("py-uring", "uringpy")):
        a = d.get("factorial", "on", py, "thread", 1)
        b = d.get("factorial", "on", c_loop, "thread", 1)
        if a is not None and b is not None and a.n and b.n:
            extra = 1e6 / a.mean - 1e6 / b.mean
            out[f"tpy:{py}"] = f"{extra:.2f}"
            out[f"fpy:{py}"] = f"{extra * a.mean / 1e6:.2f}"
            out[f"fpy-bound:{py}"] = f"{1e6 / (extra * a.mean):.1f}" if extra > 0 else "inf"
    # The two ways of computing context switches per request, where both apply.
    diffs = [abs(c.csw_per_request_est / c.csw_per_request - 1) for c in cells
             if c.n and not nan(c.csw_per_request) and not nan(c.csw_per_request_est)
             and c.csw_per_request > 0.05]
    if diffs:
        out["meta:csw-method-diff"] = f"{100 * max(diffs):.0f}"
    # Workers that own their GIL sleep only when they run out of work: the most
    # voluntary context switches per request of any process-mode configuration
    # at 400 connections with a small response and no added handler work.
    idle = [c.csw for k, c in d.cells.items()
            if k[0] in ("scaling", "factorial", "app") and k[3] == "process" and c.n
            and not nan(c.csw)]
    if idle:
        out["meta:csw-max-process"] = f"{max(idle):.3f}"
    # The server code is the image's: its tag carries the commit it was built at
    # (uringpy:<commit>, with "t" for the free-threaded build or "-loops").
    import re
    images = {(f["meta"].get("server", {}).get("image") or "") for f in d.folders}
    commits = sorted({m.group(1) for m in (re.search(r":([0-9a-f]{7})", i) for i in images) if m})
    drivers = sorted({(f["meta"].get("client", {}).get("git_commit") or "?")[:7]
                      for f in d.folders})
    out["meta:commits"] = ", ".join(commits or drivers)
    out["meta:driver-commits"] = ", ".join(drivers)
    later = [c for c in drivers if c not in commits]
    if later:
        out["meta:supplement-commits"] = ", ".join(later)
    days = sorted({(f["meta"].get("started_utc") or "")[:10] for f in d.folders} - {""})
    if days:
        out["meta:days"] = f"{len(days)}"
        out["meta:first-day"], out["meta:last-day"] = days[0], days[-1]
    out["meta:folders"] = f"{len(d.folders)}"
    return out


def _text_file_numbers(d):
    """Numbers from the two experiments that are not driver runs: the
    contention probe (probe-*.txt) and the handler thread control
    (handler-thread-control-*.txt). The newest file of each is read."""
    import glob
    import re
    out = {}
    files = sorted(glob.glob(os.path.join(d.results_dir or "", "probe-*.txt")),
                   key=os.path.getmtime)
    if files:
        text = open(files[-1]).read()
        for k, _pm, _psd, px, _pmin, _cm, _csd, cx, _cmin in re.findall(
                r"^\|\s*(\d+)\s*\|\s*([\d.]+) \(([\d.]+)\)\s*\|\s*([\d.]+)x\s*\|\s*([\d.]+)x"
                r"\s*\|\s*([\d.]+) \(([\d.]+)\)\s*\|\s*([\d.]+)x\s*\|\s*([\d.]+)x\s*\|",
                text, re.M):
            out[f"probe:py/{k}"], out[f"probe:c/{k}"] = px, cx
        reps = re.search(r"reps=(\d+)", text)
        if reps:
            out["probe:reps"] = reps.group(1)
    files = sorted(glob.glob(os.path.join(d.results_dir or "", "handler-thread-control-*.txt")),
                   key=os.path.getmtime)
    if files:
        build, work = None, None
        for line in open(files[-1]):
            m = re.match(r"python \S+ gil_enabled=(\d) HANDLER_WORK=(\d+)", line)
            if m:
                build, work = ("g" if m.group(1) == "1" else "f"), m.group(2)
                continue
            m = re.match(r"(\d+) threads: us per call\s+([\d.]+)\s+calls per s\s+(\d+)", line)
            if m and build:
                out[f"control:{build}/h{work}/{m.group(1)}"] = f"{int(m.group(3)) / 1e3:.1f}"
                out[f"control-us:{build}/h{work}/{m.group(1)}"] = m.group(2)
    return out


def numbers_tex(values):
    lines = ["\\makeatletter"]
    for key in sorted(values):
        lines.append(f"\\@namedef{{v@{key}}}{{{values[key]}}}")
    lines.append("\\makeatother")
    return "\n".join(lines) + "\n"


def check_keys(tex_path, values):
    """Keys the paper uses that numbers.tex does not define."""
    import re
    used = re.findall(r"\\V\{([^}]*)\}", open(tex_path).read())
    return sorted({k for k in used if k not in values})


# --------------------------------------------------------------------------
# The results summary of the README (Markdown), generated like the tables
# --------------------------------------------------------------------------

README_START = "<!-- results:start (written by benchmarks/make_tables.py --readme; do not edit) -->"
README_END = "<!-- results:end -->"


def _md(cell_text):
    """A LaTeX table string as Markdown: '140.7 $\\pm$ 1.2' -> '140.7 ± 1.2'."""
    return cell_text.replace(" $\\pm$ ", " ± ").replace("$<$", "<").replace("--", "n/a")


def headline_md(d):
    """The README's results block. Every number comes from the runs; the
    sentences around them are fixed text, written for the runs they describe
    and to be re-read whenever the runs change."""
    v = numbers(d)

    def cell(exp, engine, mode, w, gil="on"):
        return d.get(exp, gil, engine, mode, w)

    def row(*cols):
        return "| " + " | ".join(cols) + " |"

    def scale(c4, c1):
        return _md(ratio_pm(c4, c1).split(" ")[0]) + "×" if c4 and c1 and c4.n and c1.n else "n/a"

    out = [README_START, "",
           f"All numbers below were measured at commit `{v.get('meta:commits', '?')}` and are "
           "written into this file by `benchmarks/make_tables.py --readme README.md` from the "
           "raw runs in `benchmarks/results/`. Thousands of requests per second, mean ± 95% "
           "confidence half-width; scaling is four workers over one worker of the same engine.",
           ""]

    rows = []
    for engine, name in (("uringpy", "**uringpy**"), ("asyncio-proto", "asyncio (Protocol API)"),
                         ("uvloop-proto", "uvloop (Protocol API)")):
        for mode in MODES:
            c1, c4 = cell("scaling", engine, mode, 1), cell("scaling", engine, mode, 4)
            if c1 and c4:
                rows.append(row(name, mode + ("s" if mode == "thread" else "es"), _md(k_pm(c1)),
                                _md(k_pm(c4)), scale(c4, c1)))
    if rows:
        out += ["**Transport only (no Python per request), GIL build**", "",
                row("Engine", "Workers as", "1 worker", "4 workers", "Scaling"),
                row("---", "---", "---:", "---:", "---:"), *rows, ""]

    rows = []
    what = {"uringpy": "C loop on `io_uring`, no Python", "c-epoll": "C loop on `epoll`, no Python",
            "py-uring": "Python loop on `io_uring`, GIL released per pass",
            "py-epoll": "Python loop on `epoll`, GIL released per system call",
            "py-epoll-batch": "the same `epoll` loop, GIL released per pass",
            "py-uring-held": "the `io_uring` loop holding the GIL while it submits"}
    for engine, _iface, _loop, _mark in FACTORIAL_ROWS:
        c1, c4 = cell("factorial", engine, "thread", 1), cell("factorial", engine, "thread", 4)
        if not (c1 and c4):
            continue
        f1 = cell("factorial", engine, "thread", 1, "off")
        f4 = cell("factorial", engine, "thread", 4, "off")
        rows.append(row(f"{what[engine]} (`{engine}`)", fnum(c4.syscalls_per_request, 2),
                        _md(_handoffs(c4)), fnum(c4.csw, 3), _md(k_pm(c4)), scale(c4, c1),
                        scale(f4, f1)))
    if rows:
        out += ["**The same server loop built six ways (four worker threads)**", "",
                row("Loop", "System calls per request", "GIL releases per request",
                    "Context switches per request", "4 threads", "Scaling",
                    "Scaling without the GIL"),
                row("---", "---:", "---:", "---:", "---:", "---:", "---:"), *rows, ""]

    rows = []
    what = {"uringpy-app": "`io_uring` reactor, GIL per request",
            "uringpy-app-batch": "`io_uring` reactor, GIL per batch",
            "c-epoll-app": "`epoll` reactor, GIL per request",
            "c-epoll-app-batch": "`epoll` reactor, GIL per batch",
            "asyncio-proto-app": "asyncio (Protocol API)", "uvloop-proto-app": "uvloop (Protocol API)"}
    for engine in what:
        t1, t4 = cell("app", engine, "thread", 1), cell("app", engine, "thread", 4)
        p4 = cell("app", engine, "process", 4)
        if not (t1 and t4):
            continue
        rows.append(row(f"{what[engine]} (`{engine}`)", _md(k_pm(t4)), scale(t4, t1),
                        fnum(t4.csw, 2), _md(k_pm(p4)) if p4 else "n/a"))
    if rows:
        out += ["**With a Python handler on every request (GIL build)**", "",
                row("Server", "4 threads", "Thread scaling", "Context switches per request",
                    "4 processes"),
                row("---", "---:", "---:", "---:", "---:"), *rows, ""]

    def has(*keys):
        return all(k in v for k in keys)

    notes = []
    k = ("S:factorial/g/py-epoll/thread/4", "S:factorial/g/py-epoll-batch/thread/4",
         "S:factorial/g/py-uring/thread/4", "S:factorial/g/py-uring-held/thread/4")
    if has(*k):
        notes.append(
            "- **It is the GIL hand-offs, not the system calls.** The Python loop on `epoll` makes "
            "the same two system calls per request in both of its variants. Releasing the GIL once "
            f"per pass instead of once per system call takes four threads from {v[k[0]]}× to "
            f"{v[k[1]]}× the throughput of one. The Python loop on `io_uring` scales by {v[k[2]]}×, "
            f"and by {v[k[3]]}× if it merely holds the GIL during its submitting call. Without the "
            "GIL all six loops scale alike.")
    k = ("x:app/g/uringpy-app/thread/4", "x:app/g/uringpy-app-batch/thread/4",
         "r:thread-over-process:app/g/uringpy-app-batch/thread/4",
         "r:uringpy-app-batch/thread-over-uvloop-proto-app/process/g/4")
    if has(*k):
        notes.append(
            "- **GIL batching.** With a Python handler on every request, taking the GIL once per "
            "batch instead of once per request (`engine.set_gil_batching(True)`) lifts four-thread "
            f"throughput from {v[k[0]]} to {v[k[1]]} thousand requests per second. That is {v[k[2]]} "
            f"of four processes of the same reactor and {v[k[3]]}× the best process-per-worker "
            "baseline measured (uvloop, Protocol API). The same batching rescues the `epoll` "
            "reactor.")
    limits = []
    k = ("tp:handler/g/uringpy-app-batch/thread/1", "tp:handler/g/uringpy-app-batch/thread/1/h30",
         "rpm:uringpy-app-batch/thread-over-uringpy-app/process/h30")
    if has(*k):
        limits.append(
            f"  - **Handler length.** The handler above holds the GIL for {v[k[0]]} µs per request. "
            f"With one that holds it for {v[k[1]]} µs, batched threads deliver "
            f"{v[k[2]].split(' ')[0]} of what processes do, and less with longer ones. No design "
            "recovers thread scaling once the lock itself is busy.")
    k = ("S:load/g/uringpy-app-batch/thread/4/c64", "S:load/g/uringpy-app-batch/thread/4")
    if has(*k):
        limits.append(
            "  - **Light load.** Batches need a backlog. With 64 connections instead of 400, batched "
            f"threads scale by {v[k[0]]}× instead of {v[k[1]]}×.")
    k = ("S:scaling/f/asyncio-proto/thread/4", "r:uringpy-over-asyncio-proto/thread/f/4")
    if has(*k):
        limits.append(
            f"  - **Free-threaded build.** `asyncio` threads scale there ({v[k[0]]}×); uringpy keeps "
            f"an advantage in speed per worker ({v[k[1]]}× at four workers on the transport path) "
            "and no longer one in scaling.")
    if has("r:size/16384"):
        limits.append("  - **Large responses.** With bodies of 16 KiB or more the network, not the "
                      "server, was the limit.")
    if has("r:loop-uring/4"):
        limits.append(f"  - On the transport path the C loop is only {v['r:loop-uring/4']}× faster "
                      "at four workers than the Python loop on `io_uring`.")
    if limits:
        notes += ["- **Limits, measured.**"] + limits
    out += notes + ["", README_END]
    return "\n".join(out) + "\n"


def splice_readme(path, block):
    """Replace the text between the two markers in the file at `path`."""
    text = open(path).read()
    a, b = text.find(README_START), text.find(README_END)
    if a < 0 or b < a:
        sys.exit(f"{path}: markers not found ({README_START!r} ... {README_END!r})")
    new = text[:a] + block.rstrip("\n") + text[b + len(README_END):]
    if new != text:
        with open(path, "w") as f:
            f.write(new)
    return new != text


TABLES = {"probe": tab_probe, "factorial": tab_factorial, "effects": tab_effects,
          "batch": tab_batch, "scaling": tab_scaling, "app": tab_app, "gilbatch": tab_gilbatch,
          "handler": tab_handler, "load": tab_load, "size": tab_size, "loops": tab_loops}


def provenance(data):
    lines = ["% Generated by benchmarks/make_tables.py -- do not edit by hand.", "% Source runs:"]
    for f in data.folders:
        m = f["meta"]
        left_out = f", {f['excluded']} excluded" if f.get("excluded") else ""
        lines.append(f"%   {f['name']}: {f['ok']}/{f['runs']} runs ok{left_out}, commit "
                     f"{(m.get('client', {}).get('git_commit') or '?')[:7]}, image "
                     f"{(m.get('server', {}).get('image_id') or '?')[:19]}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    ap.add_argument("--out", default=None, help="default: <results>/tables")
    ap.add_argument("--dump", action="store_true", help="print every cell as text and exit")
    ap.add_argument("--readme", metavar="README.md",
                    help="rewrite the results block between the markers in this file")
    ap.add_argument("--check", metavar="PAPER.tex",
                    help="list the \\V{key} numbers the paper uses that the data does not define")
    args = ap.parse_args(argv)

    data = Data(*load(args.results), results_dir=args.results)
    if not data.cells:
        sys.exit(f"no results found under {args.results}")
    if args.dump:
        sys.stdout.write(dump(data))
        return 0
    out = args.out or os.path.join(args.results, "tables")
    os.makedirs(out, exist_ok=True)
    head = provenance(data)
    for prefix, builders in (("tab", TABLES), ("fig", FIGURES)):
        for name, build in builders.items():
            tex = build(data)
            if tex is None:
                print(f"skipped {prefix}_{name}: no data")
                continue
            path = os.path.join(out, f"{prefix}_{name}.tex")
            with open(path, "w") as f:
                f.write(head + tex)
            print(f"wrote {path}")
    values = numbers(data)
    path = os.path.join(out, "numbers.tex")
    with open(path, "w") as f:
        f.write(head + numbers_tex(values))
    print(f"wrote {path} ({len(values)} numbers)")
    if args.readme:
        changed = splice_readme(args.readme, headline_md(data))
        print(f"{'updated' if changed else 'unchanged'} {args.readme}")
    if args.check:
        missing = check_keys(args.check, values)
        for key in missing:
            print(f"UNDEFINED in {args.check}: \\V{{{key}}}")
        return 1 if missing else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
