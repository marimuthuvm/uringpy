#!/usr/bin/env bash
# Response-size sweep (two-node): finds where the small-vs-large crossover sits.
# Small bodies stress per-request overhead (syscalls, GIL crossings) -> uringpy's
# C reactor wins; large bodies become bandwidth-bound -> engines converge. Runs on
# the CLIENT, drives the server over SSH (same model as twonode_bench.sh).
#
#   SERVER=user@<server-ip> SERVER_IP=<server-ip> bash benchmarks/bodysize_bench.sh
#
# Env: IMAGE PORT DURATION CONNS THREADS WORKERS(4) MODE(thread) ENGINES
#      SIZES ("64 1024 16384 65536 262144 1048576")
set -u

: "${SERVER:?set SERVER=user@server-host}"
: "${SERVER_IP:?set SERVER_IP=server-reachable-ip}"
IMAGE="${IMAGE:-uringpy:gil}"
PORT="${PORT:-8080}"
DURATION="${DURATION:-15}"
CONNS="${CONNS:-400}"
THREADS="${THREADS:-$(nproc)}"
WORKERS="${WORKERS:-4}"
MODE="${MODE:-thread}"
ENGINES="${ENGINES:-uringpy asyncio}"
SIZES="${SIZES:-64 1024 16384 65536 262144 1048576}"
URL="http://${SERVER_IP}:${PORT}/"
NAME=uringpy-srv
SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

command -v wrk >/dev/null 2>&1 || { echo "[!] wrk missing"; exit 1; }

run_cell() {  # $1=engine $2=resp_size -> "req/s MBps"
    $SSH "$SERVER" "docker rm -f $NAME >/dev/null 2>&1; \
        docker run -d --name $NAME --network host --security-opt seccomp=unconfined \
        -e RESP_SIZE=$2 $IMAGE python3 benchmarks/sharded_server.py \
        --engine $1 --mode $MODE --workers $WORKERS --host 0.0.0.0 --port $PORT >/dev/null"
    local ok=0
    for _ in $(seq 1 100); do curl -s -o /dev/null "$URL" && { ok=1; break; }; sleep 0.1; done
    if [ "$ok" -eq 0 ]; then $SSH "$SERVER" "docker rm -f $NAME >/dev/null 2>&1"; echo "NA -"; return; fi
    local out; out="$(wrk -t"$THREADS" -c"$CONNS" -d"${DURATION}s" "$URL" 2>/dev/null)"
    $SSH "$SERVER" "docker rm -f $NAME >/dev/null 2>&1"
    # req/s and throughput MB/s = req/s * body_size / 1e6
    echo "$out" | awk -v sz="$2" '/Requests\/sec/{r=$2} END{printf "%s %.1f", r, r*sz/1e6}'
}

echo "# Response-size sweep (two-node, ${MODE} x ${WORKERS} workers)"
echo "- server: $SERVER_IP  image: $IMAGE  kernel: $($SSH "$SERVER" 'uname -r')"
echo "- client: $(uname -m) $(nproc) cpus, wrk -t$THREADS -c$CONNS -d${DURATION}s"
echo

printf "| body bytes |"
for e in $ENGINES; do printf " %s req/s | %s MB/s |" "$e" "$e"; done
echo
printf "| ---: |"; for _ in $ENGINES; do printf " ---: | ---: |"; done; echo

for sz in $SIZES; do
    printf "| %s |" "$sz"
    for e in $ENGINES; do
        cell="$(run_cell "$e" "$sz")"
        printf " %s | %s |" "$(echo "$cell" | awk '{print $1}')" "$(echo "$cell" | awk '{print $2}')"
    done
    echo
done

echo
echo "Small bodies: per-request overhead dominates (uringpy's C reactor leads)."
echo "Large bodies: bandwidth-bound; req/s falls but MB/s saturates and engines converge."
