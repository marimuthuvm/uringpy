#!/usr/bin/env bash
# The `loops` experiment: asyncio, uvloop and the asyncio loop built on
# io_uring (uringcore) under one server script, as threads and as processes.
#
# Run on the CLIENT machine after run_paper_experiments.sh, in a clean checkout:
#
#     BASE_COMMIT=<commit of the paper's images> \
#         nohup setsid bash benchmarks/run_loops_experiment.sh > ~/loops-run.log 2>&1 < /dev/null &
#
# It builds uringpy:<BASE_COMMIT>-loops on the server from Dockerfile.loops, on
# top of the image uringpy:<BASE_COMMIT> that the paper's experiments used. The
# only file of this checkout that enters the image is the server script
# (benchmarks/sharded_server.py), whose loader for these loops is newer than
# the one in the base image.
#
# Two earlier attempts found what uringcore needs here, and both settings are
# passed to `docker run` through the driver and recorded in meta.json:
#
#   --ulimit memlock=-1:-1          it registers its buffers with the kernel, and
#                                   the container's default limit on locked
#                                   memory (8 MiB) is too small for that;
#   -e URINGCORE_BUFFER_COUNT=...   with its default buffer pool it fails with
#                                   "No buffers available" once a few hundred
#                                   connections are open, and the server exits.
#                                   The value is given to the buffer_count
#                                   parameter of its engine (see _new_loop in
#                                   sharded_server.py).
#
# uringloop is attempted too; it does not start on Python 3.14.
# Before measuring, each loop must survive a three-second run with the full
# number of connections. The script takes the same lock as the other run
# scripts, so no two of them can run at the same time.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
# shellcheck disable=SC1091
[ -f "$HOME/bench.env" ] && . "$HOME/bench.env"
: "${SERVER:?set SERVER=user@host}"
: "${SERVER_IP:?set SERVER_IP}"
: "${BASE_COMMIT:?set BASE_COMMIT to the commit of the base images}"
export SERVER SERVER_IP
REPS="${REPS:-5}"
BUFFERS="${URINGCORE_BUFFER_COUNT:-4096}"
OPTS="--ulimit nofile=65536:65536 --ulimit memlock=-1:-1 -e URINGCORE_BUFFER_COUNT=$BUFFERS"
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "$SERVER")
say() { echo "== $(date -u +%H:%M:%SZ) $*"; }

exec 9> "$HOME/.uringpy-paper-run.lock"
if ! flock -n 9; then
    say "another run holds the lock: not starting"
    exit 1
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    say "tracked files differ from the commit: commit or discard them first"
    exit 1
fi

COMMIT="$(git rev-parse --short=7 HEAD)"
BASE="uringpy:${BASE_COMMIT}"
IMAGE="uringpy:${BASE_COMMIT}-loops"
DIR="uringpy-loops-${COMMIT}"
say "commit $COMMIT  base image $BASE  image $IMAGE  options: $OPTS"

if ! "${SSH[@]}" "docker image inspect $BASE > /dev/null 2>&1"; then
    say "base image $BASE is not on the server"
    exit 1
fi
git archive --format=tar HEAD \
    | "${SSH[@]}" "rm -rf ~/$DIR && mkdir -p ~/$DIR && tar -xf - -C ~/$DIR" || exit 1
say "building $IMAGE"
"${SSH[@]}" "cd ~/$DIR && docker build -f Dockerfile.loops --build-arg BASE=$BASE -t $IMAGE . 2>&1 \
    | grep -E '\[loops\]|\[warn\]|ERROR|error:' | sort -u" || true
if ! "${SSH[@]}" "docker image inspect $IMAGE > /dev/null 2>&1"; then
    say "the image was not built"
    exit 1
fi

# Which loops can be created at all, and with what buffer pool.
candidates=""
for loop in uringcore uringloop; do
    out="$("${SSH[@]}" "timeout 60 docker run --rm --security-opt seccomp=unconfined $OPTS $IMAGE \
        python3 -c \"import sys; sys.path.insert(0, 'benchmarks'); import sharded_server as s; s._new_loop('$loop').close(); print('loop-ok')\" 2>&1 | tail -n 3")"
    case "$out" in
        *loop-ok*)
            say "$loop: starts. $(printf '%s' "$out" | grep -F "[$loop]" | cut -c1-200)"
            candidates="$candidates $loop" ;;
        *) say "$loop: NOT available: $(printf '%s' "$out" | tail -n 1 | cut -c1-200)" ;;
    esac
done

# Which of them serve the full number of connections: four short runs each (one
# and four workers, as threads and as processes), kept out of the results.
SCRATCH="$(mktemp -d)"
engines="asyncio uvloop"
found=""
for loop in $candidates; do
    IMAGE="$IMAGE" python3 benchmarks/bench_matrix.py --experiment loops --engines "$loop" \
        --workers "1 4" --reps 1 --duration 3 --warmup 1 --docker-opts "$OPTS" \
        --out "$SCRATCH/$loop" > "$SCRATCH/$loop.log" 2>&1
    ok="$(cat "$SCRATCH/$loop"/*/runs.csv 2>/dev/null | grep -c ',ok,')"
    if [ "$ok" -eq 4 ]; then
        say "$loop: serves 400 connections in all four trial runs"
        engines="$engines $loop"
        found="yes"
    else
        say "$loop: only $ok of 4 trial runs succeeded: $(grep -a -m1 -E 'failed|no-start' "$SCRATCH/$loop.log" | cut -c1-220)"
    fi
done
rm -rf "$SCRATCH"
if [ -z "$found" ]; then
    say "no io_uring loop serves the load: nothing to measure"
    exit 1
fi

say "start  loops ($engines)"
IMAGE="$IMAGE" python3 benchmarks/bench_matrix.py --experiment loops --engines "$engines" \
    --workers "1 2 4" --reps "$REPS" --docker-opts "$OPTS"
status=$?
cd "$REPO/benchmarks/results" || exit 1
newest="$(ls -d loops-uringpy-"${BASE_COMMIT}"-loops-* 2>/dev/null | sort | tail -n 1)"
if [ -n "$newest" ]; then
    tar -czf "$HOME/results-loops-${BASE_COMMIT}.tgz" "$newest"
    say "packed $newest into ~/results-loops-${BASE_COMMIT}.tgz"
    say "  $(grep -c ',ok,' "$newest/runs.csv") of $(($(wc -l < "$newest/runs.csv") - 1)) runs ok"
fi
if [ "$status" -eq 0 ]; then say "ALL DONE"; else say "FINISHED with driver exit status $status"; fi
