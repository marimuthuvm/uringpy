#!/usr/bin/env bash
# Scaling matrix for the GIL-aware thesis: {uringpy, asyncio} x {thread, process}
# across a worker-count sweep. Produces the honest figure the paper stands on.
#
# Interpretation:
#   thread mode  -> uringpy scales (nogil C reactor), asyncio collapses (shared GIL).
#   process mode -> both scale (independent GILs); uringpy's single-interpreter,
#                   shared-memory result is the novelty vs the process baseline.
#
# Single-node (load generator local -- convenient, but wrk competes for cores):
#   docker run --rm --security-opt seccomp=unconfined uringpy:gil \
#       bash benchmarks/scaling_matrix.sh
#
# Two-node (honest -- run wrk on a SEPARATE machine):
#   On the server host:  docker run ... uringpy:gil \
#       python3 benchmarks/sharded_server.py --engine uringpy --mode thread --workers 4
#   On the client host:  SERVER=<server-ip> bash benchmarks/scaling_matrix.sh --client-only
# Set REMOTE="user@host" to have this script launch wrk there over ssh.
set -u

DURATION="${DURATION:-10}"
CONNS="${CONNS:-200}"
THREADS="${THREADS:-8}"
WORKERS="${WORKERS:-1 2 4 8}"
MODES="${MODES:-thread process}"
ENGINES="${ENGINES:-uringpy asyncio}"
HOST="${HOST:-127.0.0.1}"
PORT=8080
URL="http://${HOST}:${PORT}/"
REMOTE="${REMOTE:-}"   # user@host to run wrk remotely; empty => local wrk

wrk_cmd() {  # emits the wrk invocation, locally or over ssh
    local cmd="wrk -t${THREADS} -c${CONNS} -d${DURATION}s --latency ${URL}"
    if [ -n "$REMOTE" ]; then ssh "$REMOTE" "$cmd" 2>/dev/null
    else bash -c "$cmd" 2>/dev/null; fi
}

command -v wrk >/dev/null 2>&1 || [ -n "$REMOTE" ] || { echo "[!] wrk missing"; exit 1; }

run_cell() {  # $1=engine $2=mode $3=workers -> "req/s p99 compl_per_enter"
    local engine="$1" mode="$2" w="$3"
    URINGPY_STATS=1 python3 benchmarks/sharded_server.py --engine "$engine" --mode "$mode" \
        --workers "$w" --host 0.0.0.0 --port "$PORT" >/tmp/srv.log 2>&1 &
    local pid=$! ok=0
    for _ in $(seq 1 50); do curl -s -o /dev/null "$URL" && { ok=1; break; }; sleep 0.1; done
    if [ "$ok" -eq 0 ]; then kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; echo "NA - -"; return; fi
    local out; out="$(wrk_cmd)"
    kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; sleep 0.5
    # Mean completions per io_uring_enter across workers (uringpy only; '-' else).
    local cpw
    cpw="$(awk '/^\[worker /{for(i=1;i<=NF;i++)if($i ~ /^completions_per_wait=/){split($i,a,"=");s+=a[2];n++}} END{if(n)printf "%.1f",s/n; else printf "-"}' /tmp/srv.log)"
    echo "$out" | awk -v cpw="$cpw" '/Requests\/sec/{r=$2} / 99%/{p99=$2} END{printf "%s %s %s", r, p99, cpw}'
}

echo "# Scaling matrix: uringpy (nogil C reactor) vs asyncio (Python per event)"
echo "- kernel: $(uname -r)   cpus: $(nproc)   python: $(python3 -V 2>&1 | awk '{print $2}')"
echo "- params: duration=${DURATION}s conns=${CONNS} wrk-threads=${THREADS} workers=[${WORKERS}]"
echo "- load: ${REMOTE:-local wrk (single-node)}"
echo

for engine in ${ENGINES}; do
    for mode in ${MODES}; do
        echo "## ${engine} / ${mode}"
        echo "| workers | req/s | scaling | P99 | compl/enter |"
        echo "| ---: | ---: | ---: | ---: | ---: |"
        base=""
        for w in ${WORKERS}; do
            cell="$(run_cell "$engine" "$mode" "$w")"
            rps="$(echo "$cell" | awk '{print $1}')"
            p99="$(echo "$cell" | awk '{print $2}')"
            cpw="$(echo "$cell" | awk '{print $3}')"
            [ -z "$base" ] && base="$rps"
            scale="-"
            echo "$rps" | grep -qE '^[0-9.]+$' && \
                scale="$(awk -v r="$rps" -v b="$base" 'BEGIN{if(b>0)printf "%.2fx", r/b}')"
            echo "| ${w} | ${rps} | ${scale} | ${p99} | ${cpw} |"
        done
        echo
    done
done

echo "Scaling is relative to that cell-group's 1-worker throughput."
echo "Expected: thread/uringpy scales, thread/asyncio flattens; process/* both scale."
