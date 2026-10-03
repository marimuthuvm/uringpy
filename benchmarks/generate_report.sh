#!/usr/bin/env bash
# Generate the full benchmark report: a concurrency sweep with multiple runs per
# point (throughput + P50/P99) for asyncio, uvloop, and uringpy, plus a syscall
# profile that quantifies the completion-batching claim (syscalls per request).
#
# Run inside the container:
#   bash benchmarks/generate_report.sh
# Env overrides: DURATION (s), REPS, CONNS ("50 200 1000"), THREADS.
set -u

DURATION="${DURATION:-15}"
REPS="${REPS:-3}"
CONNS="${CONNS:-50 200 1000}"
THREADS="${THREADS:-4}"
HOST=127.0.0.1
PORT=8080
URL="http://${HOST}:${PORT}/"
ENGINES="asyncio uvloop uringpy"

command -v wrk >/dev/null 2>&1 || { echo "[!] wrk missing"; exit 1; }

start_server() {  # $1=engine ; extra env passed by caller
    python3 benchmarks/echo_server.py --engine "$1" --host 0.0.0.0 --port "${PORT}" >/dev/null 2>&1 &
    SRV_PID=$!
    for _ in $(seq 1 50); do curl -s -o /dev/null "${URL}" && return 0; sleep 0.1; done
    return 1
}
stop_server() { kill -TERM "${SRV_PID}" 2>/dev/null; wait "${SRV_PID}" 2>/dev/null; sleep 0.5; }

echo "# uringpy benchmark report"
echo
echo "- host kernel: $(uname -r)"
echo "- cpus: $(nproc)"
echo "- python: $(python3 -V 2>&1 | awk '{print $2}')"
echo "- params: duration=${DURATION}s reps=${REPS} conns=[${CONNS}] threads=${THREADS}"
echo

echo "## Throughput / latency sweep (mean of ${REPS} runs)"
echo
echo "| engine | conns | req/s (mean) | req/s (min-max) | P50 | P99 |"
echo "| ------ | ----: | -----------: | --------------- | --: | --: |"
for engine in ${ENGINES}; do
    for c in ${CONNS}; do
        vals=""; p50last=; p99last=
        for _ in $(seq 1 "${REPS}"); do
            start_server "${engine}" || { echo "| ${engine} | ${c} | START-FAIL | | | |"; continue 2; }
            out="$(wrk -t"${THREADS}" -c"${c}" -d"${DURATION}s" --latency "${URL}" 2>/dev/null)"
            stop_server
            rps="$(echo "$out" | awk '/Requests\/sec/{print $2}')"
            p50last="$(echo "$out" | awk '/ 50%/{print $2}')"
            p99last="$(echo "$out" | awk '/ 99%/{print $2}')"
            vals="${vals} ${rps:-0}"
        done
        # mean / min / max computed in a single awk pass (no bc dependency)
        stats="$(echo "${vals}" | awk '{
            mn=$1; mx=$1; s=0;
            for (i=1;i<=NF;i++){ s+=$i; if($i<mn)mn=$i; if($i>mx)mx=$i }
            printf "%.0f %.0f %.0f", s/NF, mn, mx
        }')"
        mean="$(echo "$stats" | awk '{print $1}')"
        mn="$(echo "$stats" | awk '{print $2}')"
        mx="$(echo "$stats" | awk '{print $3}')"
        printf "| %s | %s | %s | %s-%s | %s | %s |\n" \
            "$engine" "$c" "$mean" "$mn" "$mx" "${p50last:-?}" "${p99last:-?}"
    done
done

echo
echo "## Syscall profile (strace -c, ${DURATION}s under load at 200 conns)"
echo
echo "Evidence for the completion-batching thesis: uringpy should issue far"
echo "fewer I/O syscalls per request than the epoll-based baselines."
echo
for engine in asyncio uringpy; do
    trace="/tmp/strace_${engine}.txt"
    strace -f -c -o "${trace}" python3 benchmarks/echo_server.py --engine "${engine}" --host 0.0.0.0 --port "${PORT}" >/dev/null 2>&1 &
    SRV_PID=$!
    for _ in $(seq 1 50); do curl -s -o /dev/null "${URL}" && break; sleep 0.1; done
    reqs="$(wrk -t"${THREADS}" -c200 -d"${DURATION}s" "${URL}" 2>/dev/null | awk '/Requests\/sec/{print $2}')"
    kill -TERM "${SRV_PID}" 2>/dev/null; wait "${SRV_PID}" 2>/dev/null; sleep 0.5
    echo "### ${engine} (approx ${reqs:-?} req/s)"
    echo '```'
    grep -E "io_uring_enter|recvfrom|sendto|epoll_wait|read|write|accept" "${trace}" 2>/dev/null | head -12
    echo '```'
    echo
done

echo "Report complete. All figures produced by wrk / strace on this host."
