#!/usr/bin/env bash
# Rigorous cross-runtime HTTP benchmark: the identical asyncio server under every
# available event loop, driven by wrk over a concurrency sweep with repeats,
# reporting mean req/s (+ spread) and tail latency. The fair comparison is among
# the drop-in asyncio loops (asyncio, uvloop, uringcore, uringloop), which run
# byte-identical server code; uringpy uses a distinct custom-loop server and is
# reported separately, NOT as an apples-to-apples row.
#
# Usage (inside the cross image):
#   bash benchmarks/crossruntime/run.sh
# Env: DURATION (s), REPS, CONNS ("50 200 1000"), THREADS.
set -u

DURATION="${DURATION:-15}"
REPS="${REPS:-3}"
CONNS="${CONNS:-50 200 1000}"
THREADS="${THREADS:-4}"
HOST=127.0.0.1
PORT=8080
URL="http://${HOST}:${PORT}/"

command -v wrk >/dev/null 2>&1 || { echo "[!] wrk missing"; exit 1; }

# One measured cell: mean req/s over REPS at concurrency $C, plus last P50/P99.
measure() {  # $1=start-cmd -> "mean±sd p50 p99" or "NA"
    local cmd="$1"
    bash -c "$cmd" >/dev/null 2>&1 &
    local pid=$! ok=0
    for _ in $(seq 1 50); do curl -s -o /dev/null "${URL}" && { ok=1; break; }; sleep 0.1; done
    if [ "$ok" -eq 0 ]; then kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; echo "NA - -"; return; fi
    local vals="" p50="" p99="" out
    for _ in $(seq 1 "${REPS}"); do
        out="$(wrk -t"${THREADS}" -c"${C}" -d"${DURATION}s" --latency "${URL}" 2>/dev/null)"
        vals="${vals} $(echo "$out" | awk '/Requests\/sec/{print $2}')"
        p50="$(echo "$out" | awk '/ 50%/{print $2}')"; p99="$(echo "$out" | awk '/ 99%/{print $2}')"
    done
    kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; sleep 0.4
    echo "$vals" | awk -v p50="$p50" -v p99="$p99" '{
        n=NF; s=0; for(i=1;i<=n;i++)s+=$i; m=s/n;
        v=0; for(i=1;i<=n;i++)v+=($i-m)*($i-m); sd=(n>1)?sqrt(v/(n-1)):0;
        printf "%.0f+/-%.0f %s %s", m, sd, p50, p99
    }'
}

echo "# Cross-runtime Python io_uring benchmark (rigorous)"
echo "- kernel: $(uname -r)   cpus: $(nproc)   python: $(python3 -V 2>&1 | awk '{print $2}')"
echo "- params: duration=${DURATION}s reps=${REPS} conns=[${CONNS}] threads=${THREADS}"
echo "- fair set: asyncio, uvloop, uringcore, uringloop (identical server, loop swapped)"
echo

for C in ${CONNS}; do
    echo "## ${C} connections"
    echo
    echo "| runtime | req/s (mean+/-sd) | P50 | P99 |"
    echo "| ------- | --------------: | --: | --: |"
    for lp in asyncio uvloop uringcore uringloop; do
        if [ "$lp" = "asyncio" ] || python3 -c "import ${lp}" >/dev/null 2>&1; then
            cell="$(measure "python3 benchmarks/crossruntime/aio_server.py --loop ${lp} --port ${PORT}")"
            echo "| ${lp} | $(echo "$cell" | awk '{print $1}') | $(echo "$cell" | awk '{print $2}') | $(echo "$cell" | awk '{print $3}') |"
        else
            echo "| ${lp} | not installed | - | - |"
        fi
    done
    cell="$(measure "python3 benchmarks/echo_server.py --engine uringpy --port ${PORT}")"
    echo "| uringpy* | $(echo "$cell" | awk '{print $1}') | $(echo "$cell" | awk '{print $2}') | $(echo "$cell" | awk '{print $3}') |"
    echo
done

echo "*uringpy uses a distinct custom-loop server (no asyncio streams); it is NOT"
echo "directly comparable to the asyncio-family rows and is shown for reference only."
echo "All numbers produced by wrk; absent loops reported as not installed, never faked."
