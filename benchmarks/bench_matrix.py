#!/usr/bin/env python3
"""
Benchmark driver: repeated, interleaved measurements with confidence intervals.

Runs on the CLIENT machine. For every cell of an experiment it starts a fresh
server, warms it up, measures it with wrk, samples CPU use on both machines,
stops the server and collects its counters. Each cell is measured REPS times;
repetitions are interleaved (all cells once, in shuffled order, then all cells
again, ...) so slow drift of the machines does not line up with one cell.

Two ways to run the server:

  two-node (the publication setup; server in Docker on another machine):
      python3 benchmarks/bench_matrix.py --experiment scaling \\
          --server user@10.0.0.2 --server-ip 10.0.0.2

  single-node (smoke test only; the load generator competes for cores):
      python3 benchmarks/bench_matrix.py --experiment scaling --local

Experiments (--experiment), each a preset you can override with --engines,
--modes, --workers, --resp-sizes and --max-batch:

  scaling    uringpy vs asyncio, thread vs process, 1/2/4 workers
  app        the same matrix with a Python handler per request
  factorial  2x2 ablation: {io_uring, epoll} x {loop in C, loop in Python}
  batch      uringpy with the completions-per-enter cap swept from 1 to unlimited
  loops      asyncio, uvloop, uringcore, uringloop (needs the cross-runtime image)
  size       response-size sweep, 64 B to 1 MiB

Output, in benchmarks/results/<experiment>-<UTC time>/:
  runs.csv     one row per measured run (raw data)
  meta.json    machines, software versions, parameters, random seed
  summary.md   per-cell mean, standard deviation and 95% confidence interval

Re-create summary.md from existing raw data with:  --summarize <directory>

Standard library only; needs wrk on the client. Latency figures come from wrk,
which is closed-loop: they describe the latency at this load, not an
open-loop tail.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import random
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

EXPERIMENTS = {
    "scaling": dict(engines=["uringpy", "asyncio"], modes=["thread", "process"],
                    workers=[1, 2, 4]),
    "app": dict(engines=["uringpy-app", "asyncio-app"], modes=["thread", "process"],
                workers=[1, 2, 4]),
    "factorial": dict(engines=["uringpy", "c-epoll", "py-uring", "py-epoll"],
                      modes=["thread"], workers=[1, 2, 4]),
    "batch": dict(engines=["uringpy"], modes=["thread"], workers=[1],
                  max_batch=[1, 4, 16, 64, 256, 0]),
    "loops": dict(engines=["asyncio", "uvloop", "uringcore", "uringloop"],
                  modes=["thread", "process"], workers=[1, 4]),
    "size": dict(engines=["uringpy", "asyncio"], modes=["thread"], workers=[4],
                 resp_sizes=[64, 1024, 16384, 65536, 262144, 1048576]),
}

CSV_FIELDS = [
    "experiment", "rep", "order", "engine", "mode", "workers", "resp_size",
    "max_batch", "status", "rps", "duration_s", "requests",
    "lat_p50_ms", "lat_p75_ms", "lat_p90_ms", "lat_p99_ms", "lat_avg_ms",
    "transfer_mb_s", "socket_errors", "non_2xx",
    "client_cpu_pct", "client_steal_pct", "server_cpu_pct", "server_steal_pct",
    "server_max_core_pct", "srv_requests", "srv_syscalls", "srv_enters",
    "srv_completions", "srv_waits", "srv_handler_errors", "note",
]

# Two-sided 95% Student-t critical values, index = degrees of freedom.
_T95 = [float("nan"), 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306,
        2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101,
        2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048,
        2.045, 2.042]


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------

def t95(df):
    if df < 1:
        return float("nan")
    return _T95[df] if df < len(_T95) else 1.960


def mean_sd(values):
    n = len(values)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(values) / n
    if n < 2:
        return m, float("nan")
    return m, math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))


def ci95(values):
    """Half-width of the 95% confidence interval of the mean (nan if n < 2)."""
    n = len(values)
    _, sd = mean_sd(values)
    if n < 2:
        return float("nan")
    return t95(n - 1) * sd / math.sqrt(n)


def ratio_ci95(num, den):
    """Ratio of means num/den with a 95% half-width (first-order delta method;
    degrees of freedom taken from the smaller sample)."""
    mn, sn = mean_sd(num)
    md, sd = mean_sd(den)
    if not den or md == 0 or math.isnan(mn) or math.isnan(md):
        return float("nan"), float("nan")
    ratio = mn / md
    if len(num) < 2 or len(den) < 2 or mn == 0:
        return ratio, float("nan")
    rel = math.sqrt((sn / math.sqrt(len(num)) / mn) ** 2
                    + (sd / math.sqrt(len(den)) / md) ** 2)
    return ratio, t95(min(len(num), len(den)) - 1) * ratio * rel


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

_TIME_UNITS = {"us": 1e-3, "ms": 1.0, "s": 1e3, "m": 6e4, "h": 3.6e6}
_SIZE_UNITS = {"B": 1 / 1e6, "KB": 1 / 1024, "MB": 1.0, "GB": 1024.0}


def _to_ms(text):
    m = re.fullmatch(r"([0-9.]+)(us|ms|s|m|h)", text)
    return float(m.group(1)) * _TIME_UNITS[m.group(2)] if m else float("nan")


def parse_wrk(output):
    """Extract the numbers we report from wrk --latency output."""
    out = {"rps": float("nan"), "requests": 0, "duration_s": float("nan"),
           "lat_p50_ms": float("nan"), "lat_p75_ms": float("nan"),
           "lat_p90_ms": float("nan"), "lat_p99_ms": float("nan"),
           "lat_avg_ms": float("nan"), "transfer_mb_s": float("nan"),
           "socket_errors": 0, "non_2xx": 0}
    for line in output.splitlines():
        s = line.strip()
        m = re.match(r"Requests/sec:\s+([0-9.]+)", s)
        if m:
            out["rps"] = float(m.group(1))
            continue
        m = re.match(r"Transfer/sec:\s+([0-9.]+)(B|KB|MB|GB)", s)
        if m:
            out["transfer_mb_s"] = float(m.group(1)) * _SIZE_UNITS[m.group(2)]
            continue
        m = re.match(r"(50|75|90|99)%\s+(\S+)", s)
        if m:
            out[f"lat_p{m.group(1)}_ms"] = _to_ms(m.group(2))
            continue
        m = re.match(r"Latency\s+(\S+)\s+\S+\s+\S+\s+\S+%", s)
        if m:
            out["lat_avg_ms"] = _to_ms(m.group(1))
            continue
        m = re.match(r"(\d+) requests in (\S+),", s)
        if m:
            out["requests"] = int(m.group(1))
            out["duration_s"] = _to_ms(m.group(2)) / 1e3
            continue
        m = re.match(r"Socket errors: connect (\d+), read (\d+), write (\d+), timeout (\d+)", s)
        if m:
            out["socket_errors"] = sum(int(g) for g in m.groups())
            continue
        m = re.match(r"Non-2xx or 3xx responses: (\d+)", s)
        if m:
            out["non_2xx"] = int(m.group(1))
    return out


def parse_server_stats(log_text):
    """Sum the raw counters of all '[worker N] key=value ...' lines."""
    totals = {}
    for line in log_text.splitlines():
        if not line.startswith("[worker "):
            continue
        for key, value in re.findall(r"(\w+)=([0-9.]+)", line):
            if key.endswith(("_per_wait", "_per_enter", "_per_request")):
                continue  # ratios are recomputed from the summed counters
            try:
                totals[key] = totals.get(key, 0) + int(float(value))
            except ValueError:
                pass
    return totals


def parse_proc_stat(text):
    """/proc/stat -> {cpu_name: (busy_jiffies, steal_jiffies, total_jiffies)}."""
    cpus = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts or not parts[0].startswith("cpu"):
            continue
        nums = [int(x) for x in parts[1:9]]
        nums += [0] * (8 - len(nums))
        user, nice, system, idle, iowait, irq, softirq, steal = nums
        total = sum(nums)
        cpus[parts[0]] = (total - idle - iowait, steal, total)
    return cpus


def cpu_usage(before, after):
    """Return (busy %, steal %, busiest single core %) between two samples."""
    def pct(name, idx):
        b, a = before.get(name), after.get(name)
        if not b or not a or a[2] == b[2]:
            return float("nan")
        return 100.0 * (a[idx] - b[idx]) / (a[2] - b[2])

    cores = [pct(n, 0) for n in after if n != "cpu"]
    cores = [c for c in cores if not math.isnan(c)]
    return pct("cpu", 0), pct("cpu", 1), (max(cores) if cores else float("nan"))


# --------------------------------------------------------------------------
# Running things
# --------------------------------------------------------------------------

def sh(cmd, timeout=60):
    """Run a local command; return (exit code, stdout+stderr)."""
    try:
        p = subprocess.run(cmd, shell=isinstance(cmd, str), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout.decode(errors="replace")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode(errors="replace")
    except OSError as e:
        return 127, str(e)


class Remote:
    """Server machine reached over ssh; the server runs in a Docker container."""

    NAME = "uringpy-srv"

    def __init__(self, target, image, port):
        self.target, self.image, self.port = target, image, port
        self.ssh = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
                    target]

    def run(self, command, timeout=60):
        return sh(self.ssh + [command], timeout=timeout)

    def start(self, engine, mode, workers, env):
        envs = " ".join(f"-e {k}={shlex.quote(str(v))}" for k, v in env.items())
        self.run(f"docker rm -f {self.NAME} >/dev/null 2>&1; "
                 f"docker run -d --name {self.NAME} --network host "
                 f"--security-opt seccomp=unconfined {envs} {shlex.quote(self.image)} "
                 f"python3 benchmarks/sharded_server.py --engine {engine} --mode {mode} "
                 f"--workers {workers} --host 0.0.0.0 --port {self.port} >/dev/null")

    def stop(self):
        _, logs = self.run(f"docker stop -t 5 {self.NAME} >/dev/null 2>&1; "
                           f"docker logs {self.NAME} 2>&1; "
                           f"docker rm {self.NAME} >/dev/null 2>&1", timeout=40)
        return logs

    def proc_stat(self):
        return self.run("cat /proc/stat", timeout=15)[1]

    def describe(self):
        info = {"target": self.target, "image": self.image}
        info["kernel"] = self.run("uname -r")[1].strip()
        info["nproc"] = self.run("nproc")[1].strip()
        info["cpu_model"] = self.run(
            "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2")[1].strip()
        info["machine_type"] = self.run(_GCE_MACHINE_TYPE, timeout=10)[1].strip()
        info["image_id"] = self.run(
            f"docker image inspect --format '{{{{.Id}}}}' {shlex.quote(self.image)}")[1].strip()
        info["interpreter"] = self.run(
            f"docker run --rm {shlex.quote(self.image)} python3 -c {shlex.quote(_PYINFO)}",
            timeout=60)[1].strip()
        return info


class Local:
    """Server as a subprocess on this machine (single-node smoke test)."""

    def __init__(self, port):
        self.port = port
        self.proc = None
        self.log_path = os.path.join("/tmp", f"uringpy-bench-{os.getpid()}.log")

    def start(self, engine, mode, workers, env):
        full_env = dict(os.environ)
        full_env.update({k: str(v) for k, v in env.items()})
        self.log = open(self.log_path, "wb")
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "sharded_server.py"), "--engine", engine,
             "--mode", mode, "--workers", str(workers), "--host", "127.0.0.1",
             "--port", str(self.port)],
            stdout=self.log, stderr=subprocess.STDOUT, env=full_env,
            start_new_session=True)

    def stop(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.send_signal(signal.SIGTERM)
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            try:  # make sure no worker process outlives the run
                os.killpg(self.proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            self.proc.wait()
            self.proc = None
            self.log.close()
        try:
            with open(self.log_path, "rb") as f:
                return f.read().decode(errors="replace")
        except OSError:
            return ""

    def proc_stat(self):
        with open("/proc/stat") as f:
            return f.read()

    def describe(self):
        return {"target": "local subprocess (single-node)",
                "kernel": os.uname().release, "nproc": os.cpu_count(),
                "machine_type": "same machine as the client",
                "interpreter": subprocess.run([sys.executable, "-c", _PYINFO],
                                              stdout=subprocess.PIPE).stdout.decode().strip()}


_PYINFO = ("import sys;g=getattr(sys,'_is_gil_enabled',None);"
           "print(sys.version.split()[0],'gil_on' if (g is None or g()) else 'gil_OFF')")
_GCE_MACHINE_TYPE = ("curl -s -m 2 -H 'Metadata-Flavor: Google' "
                     "http://metadata.google.internal/computeMetadata/v1/instance/machine-type"
                     " 2>/dev/null | awk -F/ '{print $NF}'")


def wait_ready(url, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                r.read()
                return True
        except Exception:
            time.sleep(0.1)
    return False


def run_wrk(wrk, url, threads, conns, seconds):
    return sh([wrk, f"-t{threads}", f"-c{conns}", f"-d{seconds}s", "--latency", url],
              timeout=seconds + 60)


def local_proc_stat():
    with open("/proc/stat") as f:
        return f.read()


def run_one(server, cell, args, url):
    """Measure one cell once; returns a dict of CSV fields."""
    engine, mode, workers, resp_size, max_batch = cell
    row = {"engine": engine, "mode": mode, "workers": workers,
           "resp_size": resp_size, "max_batch": max_batch, "status": "ok", "note": ""}
    env = {"URINGPY_STATS": 1, "RESP_SIZE": resp_size}
    if max_batch:
        env["URINGPY_MAX_BATCH"] = max_batch
    server.start(engine, mode, workers, env)
    try:
        if not wait_ready(url):
            row["status"] = "no-start"
            return row
        if args.warmup > 0:
            run_wrk(args.wrk, url, args.threads, args.conns, args.warmup)
        c0, s0 = local_proc_stat(), server.proc_stat()
        code, out = run_wrk(args.wrk, url, args.threads, args.conns, args.duration)
        c1, s1 = local_proc_stat(), server.proc_stat()
        row.update(parse_wrk(out))
        if code != 0 or math.isnan(row["rps"]):
            row["status"] = "wrk-failed"
            row["note"] = out.strip().splitlines()[-1][:200] if out.strip() else ""
        cb, cs, _ = cpu_usage(parse_proc_stat(c0), parse_proc_stat(c1))
        sb, ss, smax = cpu_usage(parse_proc_stat(s0), parse_proc_stat(s1))
        row.update(client_cpu_pct=cb, client_steal_pct=cs, server_cpu_pct=sb,
                   server_steal_pct=ss, server_max_core_pct=smax)
    finally:
        logs = server.stop()
        if row["status"] == "no-start":
            lines = logs.strip().splitlines()
            row["note"] = lines[-1][:200] if lines else "server did not answer"
    stats = parse_server_stats(logs)
    for key in ("requests", "syscalls", "enters", "completions", "waits", "handler_errors"):
        if key in stats:
            row["srv_" + key] = stats[key]
    return row


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

def _f(value, digits=0):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value:,.{digits}f}"


def _num(row, key):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return float("nan")


def _avg(rows, key):
    vals = [v for v in (_num(r, key) for r in rows) if not math.isnan(v)]
    return sum(vals) / len(vals) if vals else float("nan")


def summarize(rows, meta=None):
    """Build the Markdown summary from raw run rows (dicts of CSV fields)."""
    groups, order = {}, []
    for r in rows:
        key = (r["engine"], r["mode"], int(r["workers"]), int(r["resp_size"]),
               int(r["max_batch"]))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    # Present cells in the order the experiment defines them, not run order.
    if meta and meta.get("cells"):
        rank = {tuple(c): i for i, c in enumerate(meta["cells"])}
        order.sort(key=lambda k: rank.get(k, len(rank)))

    lines = ["# Benchmark summary", ""]
    if meta:
        p = meta.get("params", {})
        lines += [f"- experiment: {meta.get('experiment')}   started (UTC): {meta.get('started_utc')}",
                  f"- repetitions per cell: {p.get('reps')}   run length: {p.get('duration')} s"
                  f"   warm-up: {p.get('warmup')} s   order: interleaved, shuffled (seed {p.get('seed')})",
                  f"- load: wrk -t{p.get('threads')} -c{p.get('conns')} --latency",
                  f"- client: {meta.get('client', {}).get('machine_type') or '?'}"
                  f", {meta.get('client', {}).get('nproc')} CPUs, kernel {meta.get('client', {}).get('kernel')}",
                  f"- server: {meta.get('server', {}).get('machine_type') or '?'}"
                  f", {meta.get('server', {}).get('nproc', '?')} CPUs, kernel {meta.get('server', {}).get('kernel', '?')}"
                  f", interpreter {meta.get('server', {}).get('interpreter', '?')}",
                  ""]
    lines += ["Throughput is requests/second: mean of the repetitions, with the "
              "half-width of the 95% confidence interval (Student t). Scaling is the "
              "ratio to the 1-worker cell of the same engine and mode, with its 95% "
              "half-width. CPU columns are whole-machine busy %, averaged over runs.", ""]
    lines += ["| engine | mode | workers | body B | batch cap | n | req/s | ± 95% CI | CV % | scaling | p50 ms | p99 ms | server CPU % | busiest core % | client CPU % | syscalls/req | compl/enter | flags |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for key in order:
        engine, mode, workers, resp_size, max_batch = key
        runs = groups[key]
        good = [r for r in runs if r.get("status") == "ok"]
        rps = [v for v in (_num(r, "rps") for r in good) if not math.isnan(v)]
        m, sd = mean_sd(rps)
        hw = ci95(rps)
        cv = 100 * sd / m if rps and m and not math.isnan(sd) else float("nan")
        base = groups.get((engine, mode, 1, resp_size, max_batch), [])
        base_rps = [v for v in (_num(r, "rps") for r in base if r.get("status") == "ok")
                    if not math.isnan(v)]
        scaling = "-"
        if workers != 1 and rps and base_rps:
            ratio, rhw = ratio_ci95(rps, base_rps)
            scaling = f"{ratio:.2f}×" + ("" if math.isnan(rhw) else f" ± {rhw:.2f}")
        elif workers == 1 and rps:
            scaling = "1.00×"
        req = sum(_num(r, "srv_requests") for r in good if not math.isnan(_num(r, "srv_requests")))
        sysc = sum(_num(r, "srv_syscalls") for r in good if not math.isnan(_num(r, "srv_syscalls")))
        ent = sum(_num(r, "srv_enters") for r in good if not math.isnan(_num(r, "srv_enters")))
        comp = sum(_num(r, "srv_completions") for r in good if not math.isnan(_num(r, "srv_completions")))
        spr = sysc / req if req and sysc else float("nan")
        cpe = comp / ent if ent and comp else float("nan")
        client_cpu = _avg(good, "client_cpu_pct")
        flags = []
        if len(good) < len(runs):
            flags.append(f"{len(runs) - len(good)} failed run(s)")
        if not math.isnan(client_cpu) and client_cpu > 85:
            flags.append("client CPU > 85%: load generator may be the limit")
        if not math.isnan(cv) and cv > 5:
            flags.append("CV > 5%")
        if any(_num(r, "socket_errors") > 0 or _num(r, "non_2xx") > 0 for r in good):
            flags.append("socket errors or non-2xx responses")
        if any(_num(r, "srv_handler_errors") > 0 for r in good):
            flags.append("handler errors")
        if not good:
            notes = sorted({r.get("note", "") for r in runs if r.get("note")})
            flags.append("no successful run" + (": " + "; ".join(notes) if notes else ""))
        lines.append(
            f"| {engine} | {mode} | {workers} | {resp_size} | {max_batch or 'none'} | {len(rps)} "
            f"| {_f(m)} | {_f(hw)} | {_f(cv, 1)} | {scaling} "
            f"| {_f(_avg(good, 'lat_p50_ms'), 2)} | {_f(_avg(good, 'lat_p99_ms'), 2)} "
            f"| {_f(_avg(good, 'server_cpu_pct'), 1)} | {_f(_avg(good, 'server_max_core_pct'), 1)} "
            f"| {_f(client_cpu, 1)} | {_f(spr, 3)} | {_f(cpe, 1)} | {'; '.join(flags)} |")
    lines.append("")
    return "\n".join(lines)


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def _ints(text):
    return [int(x) for x in text.replace(",", " ").split()]


def _strs(text):
    return text.replace(",", " ").split()


def build_cells(args):
    preset = EXPERIMENTS[args.experiment]
    engines = _strs(args.engines) if args.engines else preset["engines"]
    modes = _strs(args.modes) if args.modes else preset["modes"]
    workers = _ints(args.workers) if args.workers else preset["workers"]
    sizes = _ints(args.resp_sizes) if args.resp_sizes else preset.get("resp_sizes", [13])
    batches = _ints(args.max_batch) if args.max_batch else preset.get("max_batch", [0])
    return [(e, m, w, s, b) for e in engines for m in modes for w in workers
            for s in sizes for b in batches]


def describe_client(wrk):
    info = {"kernel": os.uname().release, "nproc": os.cpu_count(),
            "python": sys.version.split()[0]}
    info["cpu_model"] = sh("grep -m1 'model name' /proc/cpuinfo | cut -d: -f2")[1].strip()
    info["machine_type"] = sh(_GCE_MACHINE_TYPE, timeout=10)[1].strip()
    info["wrk"] = (sh([wrk, "-v"])[1].strip().splitlines() or [""])[0]
    code, commit = sh(["git", "-C", REPO, "rev-parse", "HEAD"])
    info["git_commit"] = commit.strip() if code == 0 else ""
    if code == 0:
        info["git_dirty"] = bool(sh(["git", "-C", REPO, "status", "--porcelain",
                                     "--untracked-files=no"])[1].strip())
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--experiment", choices=sorted(EXPERIMENTS))
    ap.add_argument("--summarize", metavar="DIR",
                    help="rebuild summary.md from DIR/runs.csv and exit")
    ap.add_argument("--local", action="store_true",
                    help="run the server as a local subprocess (smoke test only)")
    ap.add_argument("--server", default=os.environ.get("SERVER"),
                    help="ssh target of the server machine (user@host) [$SERVER]")
    ap.add_argument("--server-ip", default=os.environ.get("SERVER_IP"),
                    help="server address reachable from this client [$SERVER_IP]")
    ap.add_argument("--image", default=os.environ.get("IMAGE", "uringpy:gil"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--duration", type=int, default=20, help="seconds per measured run")
    ap.add_argument("--warmup", type=int, default=5, help="seconds, discarded")
    ap.add_argument("--conns", type=int, default=400)
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--wrk", default="wrk")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("--engines")
    ap.add_argument("--modes")
    ap.add_argument("--workers")
    ap.add_argument("--resp-sizes")
    ap.add_argument("--max-batch")
    args = ap.parse_args(argv)

    if args.summarize:
        meta_path = os.path.join(args.summarize, "meta.json")
        meta = json.load(open(meta_path)) if os.path.exists(meta_path) else None
        text = summarize(read_rows(os.path.join(args.summarize, "runs.csv")), meta)
        with open(os.path.join(args.summarize, "summary.md"), "w") as f:
            f.write(text)
        print(text)
        return 0

    if not args.experiment:
        ap.error("--experiment is required (or use --summarize DIR)")
    if not shutil.which(args.wrk):
        sys.exit(f"[!] {args.wrk} not found on this machine")
    if args.local:
        server = Local(args.port)
        url = f"http://127.0.0.1:{args.port}/"
    else:
        if not args.server or not args.server_ip:
            ap.error("give --server and --server-ip (or SERVER / SERVER_IP), or --local")
        server = Remote(args.server, args.image, args.port)
        url = f"http://{args.server_ip}:{args.port}/"
        code, out = server.run("docker --version")
        if code != 0:
            sys.exit(f"[!] cannot run docker on {args.server}: {out.strip()}")

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1 << 31)
    rng = random.Random(seed)
    cells = build_cells(args)
    started = datetime.datetime.now(datetime.timezone.utc)
    out_dir = os.path.join(args.out, f"{args.experiment}-{started.strftime('%Y%m%dT%H%M%SZ')}")
    os.makedirs(out_dir, exist_ok=True)

    meta = {"experiment": args.experiment, "started_utc": started.isoformat(timespec="seconds"),
            "params": {"reps": args.reps, "duration": args.duration, "warmup": args.warmup,
                       "conns": args.conns, "threads": args.threads, "seed": seed,
                       "port": args.port, "url": url},
            "cells": [list(c) for c in cells],
            "client": describe_client(args.wrk), "server": server.describe()}
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    total = len(cells) * args.reps
    per_run = args.duration + args.warmup + 8
    print(f"# {args.experiment}: {len(cells)} cells x {args.reps} repetitions = {total} runs, "
          f"about {total * per_run / 60:.0f} min. Results: {out_dir}", flush=True)

    rows, done = [], 0
    csv_path = os.path.join(out_dir, "runs.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for rep in range(1, args.reps + 1):
            order = list(cells)
            rng.shuffle(order)
            for cell in order:
                done += 1
                row = run_one(server, cell, args, url)
                row.update(experiment=args.experiment, rep=rep, order=done)
                writer.writerow(row)
                f.flush()
                rows.append({k: row.get(k, "") for k in CSV_FIELDS})
                rps = row.get("rps", float("nan"))
                print(f"[{done}/{total}] rep {rep} {cell[0]}/{cell[1]} w={cell[2]} "
                      f"size={cell[3]} batch={cell[4] or 'none'}: "
                      f"{row['status']} {_f(rps)} req/s "
                      f"(server CPU {_f(row.get('server_cpu_pct', float('nan')), 0)}%, "
                      f"client CPU {_f(row.get('client_cpu_pct', float('nan')), 0)}%)"
                      + (f"  {row['note']}" if row.get("note") else ""), flush=True)

    meta["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    text = summarize(rows, meta)
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write(text)
    print()
    print(text)
    print(f"Raw data: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
