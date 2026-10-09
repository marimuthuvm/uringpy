#!/usr/bin/env bash
# Supplementary experiments, on the images of the main run.
#
# Three things the main run (run_paper_experiments.sh) could not give, because
# of resource limits of the server container:
#
#   load      1600 connections. The container allowed 1024 open files, fewer
#             than the connections offered, so the main run's 1600-connection
#             runs did not measure what they were meant to.
#   loops     the asyncio event loop built on io_uring (uringcore) next to
#             asyncio and uvloop. It could not register its buffers under the
#             container's limit on locked memory.
#   handler   handler sizes between the two smallest of the main run (5, 10 and
#             20 added iterations), to locate where worker threads stop keeping
#             up with one process per worker.
#
# Nothing on the server is rebuilt: the server runs the images uringpy:<BASE>
# and uringpy:<BASE>-loops that the earlier scripts built. The only difference
# from the main run is the pair of limits in LIMITS below, which the driver
# passes to `docker run` and records in every meta.json.
#
# Run on the CLIENT machine, in a clean checkout:
#
#     BASE_COMMIT=<commit of the paper's images> \
#         nohup setsid bash benchmarks/run_supplement.sh > ~/supplement-run.log 2>&1 < /dev/null &
#
# It takes the same lock as the other run scripts.
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
LIMITS="--ulimit nofile=65536:65536 --ulimit memlock=-1:-1"
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
GIL_IMAGE="uringpy:${BASE_COMMIT}"
LOOPS_IMAGE="uringpy:${BASE_COMMIT}-loops"
say "commit $COMMIT  images $GIL_IMAGE $LOOPS_IMAGE  limits: $LIMITS"

for image in "$GIL_IMAGE" "$LOOPS_IMAGE"; do
    if ! "${SSH[@]}" "docker image inspect $image > /dev/null 2>&1"; then
        say "image $image is not on the server"
        exit 1
    fi
done

# What the limits were in the main run, and what they are now.
show='echo "open files $(ulimit -n), locked memory $(ulimit -l) kB"'
say "container limits, default: $("${SSH[@]}" "docker run --rm $GIL_IMAGE sh -c '$show'" 2>&1 | tail -n 1)"
say "container limits, raised:  $("${SSH[@]}" "docker run --rm $LIMITS $GIL_IMAGE sh -c '$show'" 2>&1 | tail -n 1)"
versions='import importlib.metadata as m
for name in ("uvloop", "uringcore", "uringloop", "Cython"):
    try:
        print(name, m.version(name), end="; ")
    except m.PackageNotFoundError:
        print(name, "not installed", end="; ")'
say "packages: $("${SSH[@]}" "docker run --rm $LOOPS_IMAGE python3 -c '$versions'" 2>&1 | tail -n 1)"

# The load generator needs a file descriptor per connection as well.
ulimit -n 65536 2>/dev/null || ulimit -n "$(ulimit -Hn)" 2>/dev/null
if [ "$(ulimit -n)" -lt 4096 ]; then
    say "the client's open-file limit is $(ulimit -n): too low for 1600 connections"
    exit 1
fi

START_MARK="$(mktemp)"
run() {    # run <label> <image> <driver arguments...>
    local label="$1" image="$2"
    shift 2
    say "start  $label"
    if IMAGE="$image" python3 benchmarks/bench_matrix.py --reps "$REPS" --docker-opts "$LIMITS" "$@"; then
        say "done   $label"
    else
        say "FAILED $label (driver exit status $?)"
        FAILED="$FAILED $label"
    fi
}
FAILED=""

# 1. 1600 connections, the engines of the load experiment.
run load-1600 "$GIL_IMAGE" --experiment load --conns-list 1600

# 2. The io_uring-based asyncio loops that start under the raised limits.
engines="asyncio uvloop"
found=""
for loop in uringcore uringloop; do
    out="$("${SSH[@]}" "timeout 60 docker run --rm --security-opt seccomp=unconfined $LIMITS $LOOPS_IMAGE \
        python3 -c \"import sys; sys.path.insert(0, 'benchmarks'); import sharded_server as s; s._new_loop('$loop').close(); print('loop-ok')\" 2>&1 | tail -n 1")"
    case "$out" in
        *loop-ok*) say "$loop: available"; engines="$engines $loop"; found="yes" ;;
        *) say "$loop: NOT available: $(printf '%s' "$out" | cut -c1-200)" ;;
    esac
done
if [ -n "$found" ]; then
    run loops "$LOOPS_IMAGE" --experiment loops --engines "$engines" --workers "1 2 4"
else
    say "skip   loops: neither io_uring loop starts"
fi

# 3. Handler sizes between the two smallest of the main run. As there, the two
#    baselines are measured as processes only.
run handler-fine "$GIL_IMAGE" --experiment handler --handler-work "5 10 20" --workers "1 4" \
    --exclude "*-proto-app/thread/*"

cd "$REPO/benchmarks/results" || exit 1
names=()
for f in *-uringpy-"${BASE_COMMIT}"*; do
    [ -d "$f" ] && [ "$f" -nt "$START_MARK" ] && names+=("$f")
done
rm -f "$START_MARK"
if [ "${#names[@]}" -gt 0 ]; then
    tar -czf "$HOME/results-supplement-${BASE_COMMIT}.tgz" "${names[@]}"
    say "packed ${#names[@]} folder(s) into ~/results-supplement-${BASE_COMMIT}.tgz"
    for f in "${names[@]}"; do
        say "  $f: $(grep -c ',ok,' "$f/runs.csv") of $(($(wc -l < "$f/runs.csv") - 1)) runs ok"
    done
fi
if [ -z "$FAILED" ]; then say "ALL DONE"; else say "FINISHED, failed:$FAILED"; fi
