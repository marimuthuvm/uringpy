#!/usr/bin/env bash
# Multi-core scaling benchmark for the GIL-aware thesis.
#
# Sweeps worker-thread count for both engines (same process model: N threads,
# SO_REUSEPORT) and reports req/s per worker count. The thesis prediction:
#   uringpy (nogil C reactor) scales ~linearly with workers;
#   asyncio (Python per event) plateaus, GIL-bound.
#
# Run inside the image (io_uring needs an unrestricted seccomp profile):
#   docker run --rm --security-opt seccomp=unconfined uringpy:gil \
#       bash benchmarks/sharded_bench.sh
#
# Env: DURATION (s), CONNS, THREADS (wrk), WORKERS ("1 2 4 8").
set -u

DURATION="${DURATION:-10}"
CONNS="${CONNS:-200}"
THREADS="${THREADS:-8}"
WORKERS="${WORKERS:-1 2 4 8}"
HOST=127.0.0.1
PORT=8080
URL="http://${HOST}:${PORT}/"

command -v wrk >/dev/null 2>&1 || { echo "[!] wrk missing"; exit 1; }

run_one() {  # $1=engine $2=workers -> "req/s p50 p99"
    local engine="$1" w="$2"
    URINGPY_STATS=1 python3 benchmarks/sharded_server.py \
        --engine "$engine" --workers "$w" --port "$PORT" >/tmp/srv.log 2>&1 &
    local pid=$! ok=0
    for _ in $(seq 1 50); do curl -s -o /dev/null "$URL" && { ok=1; break; }; sleep 0.1; done
    if [ "$ok" -eq 0 ]; then kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; echo "NA - -"; return; fi
    local out
    out="$(wrk -t"${THREADS}" -c"${CONNS}" -d"${DURATION}s" --latency "$URL" 2>/dev/null)"
    kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; sleep 0.5
    echo "$out" | awk '/Requests\/sec/{r=$2} / 50%/{p50=$2} / 99%/{p99=$2} END{printf "%s %s %s", r, p50, p99}'
}

echo "# Multi-core scaling: uringpy (nogil C reactor) vs asyncio (Python per event)"
echo "- kernel: $(uname -r)   cpus: $(nproc)   python: $(python3 -V 2>&1 | awk '{print $2}')"
echo "- params: duration=${DURATION}s conns=${CONNS} wrk-threads=${THREADS} workers=[${WORKERS}]"
echo

printf "| workers |"
for e in uringpy asyncio; do printf " %s req/s | %s P99 |" "$e" "$e"; done
echo
echo "| ---: | ---: | ---: | ---: | ---: |"

declare -A base
for w in ${WORKERS}; do
    printf "| %s |" "$w"
    for e in uringpy asyncio; do
        cell="$(run_one "$e" "$w")"
        rps="$(echo "$cell" | awk '{print $1}')"
        p99="$(echo "$cell" | awk '{print $3}')"
        [ "$w" = "$(echo "$WORKERS" | awk '{print $1}')" ] && base[$e]="$rps"
        scale=""
        if [ -n "${base[$e]:-}" ] && echo "$rps" | grep -qE '^[0-9.]+$'; then
            scale="$(awk -v r="$rps" -v b="${base[$e]}" 'BEGIN{if(b>0)printf " (%.2fx)", r/b}')"
        fi
        printf " %s%s | %s |" "$rps" "$scale" "$p99"
    done
    echo
done

echo
echo "Scaling factor is relative to that engine's own 1-worker throughput."
echo "Thesis holds if uringpy's factor tracks worker count while asyncio's flattens."
