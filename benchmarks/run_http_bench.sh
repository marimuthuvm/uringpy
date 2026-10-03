#!/usr/bin/env bash
# Load-driven HTTP benchmark: starts each server, hits it with wrk, and prints a
# comparison table. Runs entirely inside the container (all three servers + wrk
# share one host, so the comparison is fair). Every number comes from wrk.
#
# Usage (inside container):
#   benchmarks/run_http_bench.sh [DURATION] [CONNECTIONS] [THREADS]
# Defaults: 15s, 200 connections, 4 threads.
set -u

DURATION="${1:-15}"
CONNECTIONS="${2:-200}"
THREADS="${3:-4}"
HOST=127.0.0.1
PORT=8080
URL="http://${HOST}:${PORT}/"

if ! command -v wrk >/dev/null 2>&1; then
    echo "[!] wrk not found in image" >&2
    exit 1
fi

run_one() {
    local engine="$1"
    echo "=================================================================="
    echo ">> engine=${engine}  duration=${DURATION}s  conns=${CONNECTIONS}  threads=${THREADS}"
    python3 benchmarks/echo_server.py --engine "${engine}" --host 0.0.0.0 --port "${PORT}" &
    local srv_pid=$!

    # Wait for the port to accept connections (max ~5s).
    for _ in $(seq 1 50); do
        if curl -s -o /dev/null "${URL}"; then break; fi
        sleep 0.1
    done

    wrk -t"${THREADS}" -c"${CONNECTIONS}" -d"${DURATION}s" --latency "${URL}"
    local rc=$?

    kill "${srv_pid}" 2>/dev/null
    wait "${srv_pid}" 2>/dev/null
    sleep 0.5
    return $rc
}

for engine in asyncio uvloop uringpy; do
    run_one "${engine}"
done

echo "=================================================================="
echo "Done. Numbers above are produced by wrk; nothing is hand-authored."
