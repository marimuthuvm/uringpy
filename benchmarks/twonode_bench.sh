#!/usr/bin/env bash
# Two-node scaling benchmark -- quick single-pass look.
#
# For numbers that go into the paper use benchmarks/bench_matrix.py instead: it
# repeats every cell, interleaves the repetitions, and reports means with 95%
# confidence intervals, latency and CPU use on both machines.
#
# Run this ON THE CLIENT VM. It drives the server VM over SSH -- starting a fresh
# server container per cell, generating load locally with wrk, then stopping the
# server and scraping its completions-per-enter stats. Because the load generator
# and the server under test are on SEPARATE machines, this removes the
# co-location confound of the single-node matrix.
#
#   SERVER=user@<server-ip> SERVER_IP=<server-ip> bash benchmarks/twonode_bench.sh
#
# Required env:
#   SERVER      ssh target for the server VM (user@host)
#   SERVER_IP   server address reachable from this client on $PORT (private IP)
# Optional env:
#   FT=1        use the free-threaded image (uringpy:gil-ft) unless IMAGE is set
#   IMAGE (uringpy:gil) PORT (8080) DURATION (20) CONNS (400) THREADS (nproc)
#   WORKERS ("1 2 4") ENGINES ("uringpy asyncio") MODES ("thread process")
#   RESP_SIZE (13)  response body bytes, honoured by every engine
# Application workload (per-request Python handler, Table "Realistic workload"):
#   ENGINES="uringpy-app asyncio-app" SERVER=... SERVER_IP=... bash benchmarks/twonode_bench.sh
set -u

: "${SERVER:?set SERVER=user@server-host}"
: "${SERVER_IP:?set SERVER_IP=server-reachable-ip}"
_IMAGE_ENV="${IMAGE:-}"
IMAGE="${IMAGE:-uringpy:gil}"
# FT=1 selects the free-threaded image unless IMAGE was given explicitly.
if [ "${FT:-0}" = "1" ] && [ -z "$_IMAGE_ENV" ]; then IMAGE="uringpy:gil-ft"; fi
PORT="${PORT:-8080}"
DURATION="${DURATION:-20}"
CONNS="${CONNS:-400}"
THREADS="${THREADS:-$(nproc)}"
WORKERS="${WORKERS:-1 2 4}"
ENGINES="${ENGINES:-uringpy asyncio}"
MODES="${MODES:-thread process}"
RESP_SIZE="${RESP_SIZE:-13}"
URL="http://${SERVER_IP}:${PORT}/"
NAME=uringpy-srv
SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

command -v wrk >/dev/null 2>&1 || { echo "[!] wrk missing (run client-setup.sh)"; exit 1; }
$SSH "$SERVER" 'command -v docker >/dev/null' || { echo "[!] docker missing on server"; exit 1; }

contention() {  # $1=label $2=ssh-target (empty => local); warns on high steal/low idle
    local line
    if [ -z "$2" ]; then line="$(vmstat 1 2 2>/dev/null | tail -1)"
    else line="$($SSH "$2" 'vmstat 1 2' 2>/dev/null | tail -1)"; fi
    [ -z "$line" ] && { echo "  $1: vmstat unavailable"; return; }
    echo "$line" | awk -v l="$1" '{st=$NF; id=$(NF-2);
        printf "  %s: idle=%s%% steal=%s%%", l, id, st;
        if (st+0>2 || id+0<20) printf "   [!] contended -- results may be noisy";
        print ""}'
}

start_server() {  # $1=engine $2=mode $3=workers
    $SSH "$SERVER" "docker rm -f $NAME >/dev/null 2>&1; \
        docker run -d --name $NAME --network host \
        --security-opt seccomp=unconfined -e URINGPY_STATS=1 -e RESP_SIZE=$RESP_SIZE $IMAGE \
        python3 benchmarks/sharded_server.py --engine $1 --mode $2 \
        --workers $3 --host 0.0.0.0 --port $PORT >/dev/null"
}

stop_server_stats() {  # stops server, echoes mean completions/enter from its logs
    $SSH "$SERVER" "docker stop -t 5 $NAME >/dev/null 2>&1; \
        docker logs $NAME 2>&1; docker rm $NAME >/dev/null 2>&1" \
        | awk '/^\[worker /{for(i=1;i<=NF;i++)if($i ~ /^completions_per_wait=/){split($i,a,"=");s+=a[2];n++}}
               END{if(n)printf "%.1f",s/n; else printf "-"}'
}

run_cell() {  # $1=engine $2=mode $3=workers -> "req/s p99 compl_per_enter"
    start_server "$1" "$2" "$3"
    local ok=0
    for _ in $(seq 1 100); do curl -s -o /dev/null "$URL" && { ok=1; break; }; sleep 0.1; done
    if [ "$ok" -eq 0 ]; then stop_server_stats >/dev/null; echo "NA - -"; return; fi
    local out; out="$(wrk -t"$THREADS" -c"$CONNS" -d"${DURATION}s" --latency "$URL" 2>/dev/null)"
    local cpw; cpw="$(stop_server_stats)"
    echo "$out" | awk -v cpw="$cpw" '/Requests\/sec/{r=$2} / 99%/{p99=$2} END{printf "%s %s %s", r, p99, cpw}'
}

echo "# Two-node io_uring scaling (isolated load generator)"
echo "- server: $SERVER_IP  image: $IMAGE"
echo "- client: $(uname -m) $(nproc) cpus, wrk -t$THREADS -c$CONNS -d${DURATION}s"
echo "- response body size: ${RESP_SIZE} bytes"
echo "- server kernel: $($SSH "$SERVER" 'uname -r')  server cpus: $($SSH "$SERVER" 'nproc')"
pyinfo="$($SSH "$SERVER" "docker run --rm $IMAGE python3 -c 'import sys;g=getattr(sys,\"_is_gil_enabled\",None);print(sys.version.split()[0], \"gil_on\" if (g is None or g()) else \"gil_OFF\")'" 2>/dev/null)"
echo "- server interpreter: ${pyinfo:-unknown}"
echo "- contention preflight (idle/steal from vmstat):"
contention client ""
contention server "$SERVER"
echo

for engine in $ENGINES; do
    for mode in $MODES; do
        echo "## ${engine} / ${mode}"
        echo "| workers | req/s | scaling | P99 | compl/enter |"
        echo "| ---: | ---: | ---: | ---: | ---: |"
        base=""
        for w in $WORKERS; do
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
echo "Scaling is relative to each cell-group's 1-worker throughput."
echo "Load generator and server are on separate VMs: no co-location confound."
