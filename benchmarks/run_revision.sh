#!/usr/bin/env bash
# Experiments added in revision: GIL hand-offs counted by the interpreter, a
# server with more cores, and the io_uring-based asyncio loops on a Python
# version they support.
#
# Run on the CLIENT machine, in a clean checkout of the commit to be measured:
#
#     PROFILE=small nohup setsid bash benchmarks/run_revision.sh > ~/revision-small.log 2>&1 < /dev/null &
#     PROFILE=large nohup setsid bash benchmarks/run_revision.sh > ~/revision-large.log 2>&1 < /dev/null &
#
# PROFILE=small  on the four-core server of the main run:
#   handoffs   the thread-mode configurations of factorial, app, gilbatch and
#              part of handler again, now with the interpreter's own count of
#              GIL hand-offs (uringpy._gilstat), so hand-offs are observed and
#              not only inferred. These cells repeat main-run cells, which also
#              shows whether the new image changed anything else.
#   py313      an image built from the same recipe with CPython 3.13, plus
#              uringcore and uringloop: a check that each loop serves the load
#              (benchmarks/check_loop.py), then the loops that pass against
#              asyncio, uvloop and uringpy, without and with a handler.
# PROFILE=large  on a server with more cores (the same VMs, resized):
#   scaling, factorial, app and handler at 1, 4 and all cores of the server,
#   threads and processes, with the hand-off counter.
#
# Results go to benchmarks/results-revision/<PROFILE>/ (kept apart from the
# main run's folders, which make_tables.py pools) and are packed into
# ~/results-revision-<PROFILE>-<commit>.tgz. Finished stages are recorded in
# ~/revision-<PROFILE>-<commit>.done, so running the script again continues
# where it stopped. The expectations for these runs are written in
# benchmarks/EXPERIMENTS.md ("Revision experiments") at the commit measured.
#
# Environment: PROFILE (required), REPS (default 5), ONLY (stage names),
# PY313 (default 3.13.7), CONNS (large profile; default 100 per server core).
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
# shellcheck disable=SC1091
[ -f "$HOME/bench.env" ] && . "$HOME/bench.env"
: "${SERVER:?set SERVER=user@host}"
: "${SERVER_IP:?set SERVER_IP}"
: "${PROFILE:?set PROFILE=small or PROFILE=large}"
export SERVER SERVER_IP
REPS="${REPS:-5}"
ONLY="${ONLY:-}"
PY313="${PY313:-3.13.7}"
LIMITS="--ulimit nofile=65536:65536 --ulimit memlock=-1:-1"
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "$SERVER")
say() { echo "== $(date -u +%H:%M:%SZ) $*"; }

case "$PROFILE" in small|large) ;; *) say "PROFILE must be small or large"; exit 1 ;; esac

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
IMAGE="uringpy:${COMMIT}"
IMAGE313="uringpy:${COMMIT}-313"
LOOPS313="uringpy:${COMMIT}-313-loops"
OUT="$REPO/benchmarks/results-revision/$PROFILE"
OUT313="$REPO/benchmarks/results-revision/${PROFILE}-py313"   # kept apart: other interpreter
DONE="$HOME/revision-${PROFILE}-${COMMIT}.done"
DAY="$(date -u +%Y%m%d)"
FAILED=""
mkdir -p "$OUT"; [ "$PROFILE" = small ] && mkdir -p "$OUT313"
touch "$DONE"

CORES="$("${SSH[@]}" nproc)"
CLIENT_CORES="$(nproc)"
say "commit $COMMIT  profile $PROFILE  server cores $CORES  client cores $CLIENT_CORES  reps $REPS"

# The load generator needs a file descriptor per connection.
ulimit -n 65536 2>/dev/null || ulimit -n "$(ulimit -Hn)" 2>/dev/null

wanted() {
    [ -z "$ONLY" ] && return 0
    case " $ONLY " in *" $1 "*) return 0 ;; esac
    return 1
}

stage() {  # stage <name> <command...>: run once, record success
    local name="$1"; shift
    wanted "$name" || return 0
    if grep -qxF "$name" "$DONE"; then
        say "skip   $name (already done)"
        return 0
    fi
    say "start  $name"
    if "$@"; then
        echo "$name" >> "$DONE"
        say "done   $name"
        return 0
    fi
    say "FAILED $name"
    FAILED="$FAILED $name"
    return 1
}

send_tree() {
    local dir="uringpy-build-${COMMIT}"
    git archive --format=tar HEAD \
        | "${SSH[@]}" "rm -rf ~/$dir && mkdir -p ~/$dir && tar -xf - -C ~/$dir"
}

build_main() {  # the GIL image of this commit, unless it is already there
    if "${SSH[@]}" "docker image inspect $IMAGE > /dev/null 2>&1"; then
        say "image $IMAGE exists"
    else
        send_tree || return 1
        "${SSH[@]}" "cd ~/uringpy-build-${COMMIT} && docker build -q -f Dockerfile.bench -t $IMAGE ." \
            || return 1
    fi
    # The hand-off counter must be readable, or this run measures nothing new.
    "${SSH[@]}" "docker run --rm $IMAGE python3 -c 'import sys; from uringpy import _gilstat; \
        print(\"python\", sys.version.split()[0], \"gil switch counter\", _gilstat.switch_count())'"
}

build_313() {
    send_tree || return 1
    "${SSH[@]}" "cd ~/uringpy-build-${COMMIT} \
        && docker build -q -f Dockerfile.bench --build-arg PYVER=$PY313 -t $IMAGE313 . \
        && docker build -f Dockerfile.loops --build-arg BASE=$IMAGE313 -t $LOOPS313 . 2>&1 \
           | grep -E '\[loops\]|\[warn\]|ERROR' | sort -u" || return 1
    "${SSH[@]}" "docker image inspect $LOOPS313 > /dev/null 2>&1" || return 1
    "${SSH[@]}" "docker run --rm $LOOPS313 python3 -c 'import sys; from uringpy import _gilstat; \
        print(\"python\", sys.version.split()[0], \"gil switch counter\", _gilstat.switch_count())'"
}

run_tests() {  # run_tests <image>
    local out
    out="$("${SSH[@]}" "docker run --rm --network host --security-opt seccomp=unconfined \
        $1 python3 -m pytest -q 2>&1 | tail -n 15")"
    say "tests $1: $(printf '%s\n' "$out" | tail -n 1)"
    case "$(printf '%s\n' "$out" | tail -n 1)" in
        *failed*|*error*) printf '%s\n' "$out"; return 1 ;;
        *passed*) return 0 ;;
    esac
    printf '%s\n' "$out"
    return 1
}

bench() {  # bench <image> <experiment> [driver options...]
    local image="$1" experiment="$2" out="$OUT"; shift 2
    [ "$image" = "$LOOPS313" ] && out="$OUT313"
    IMAGE="$image" python3 benchmarks/bench_matrix.py --experiment "$experiment" \
        --reps "$REPS" --out "$out" "$@"
}

# Which loops serve the load on Python 3.13: each is checked inside the image
# with the same limits it is then measured with. The passing ones are listed
# in $OUT/loops-313-passed.
check_loops() {
    local file="$OUT313/loopcheck-${COMMIT}-313-${DAY}.txt" passed="" engine
    {
        echo "# benchmarks/check_loop.py in $LOOPS313 (CPython $PY313), docker run $LIMITS"
        echo "# packages: $("${SSH[@]}" "docker run --rm $LOOPS313 python3 benchmarks/check_loop.py --versions")"
        for engine in asyncio-proto uvloop-proto uringcore uringcore-proto uringloop uringloop-proto; do
            echo "== $engine"
            if "${SSH[@]}" "timeout 600 docker run --rm --security-opt seccomp=unconfined $LIMITS \
                    $LOOPS313 python3 benchmarks/check_loop.py --engine $engine" 2>&1; then
                passed="$passed $engine"
            fi
        done
    } > "$file" 2>&1
    echo "$passed" > "$OUT313/loops-313-passed"
    say "loops that pass on $PY313:$passed"
    grep -E '^\[(check|result)\]' "$file" | sed 's/^/   /'
    return 0
}

loops313() {  # the loops that passed, against the baselines, on 3.13
    local passed engines
    passed="$(cat "$OUT313/loops-313-passed" 2>/dev/null)"
    engines="asyncio asyncio-proto uvloop uvloop-proto uringpy"
    case " $passed " in *" uringcore "*) engines="$engines uringcore" ;; esac
    case " $passed " in *" uringcore-proto "*) engines="$engines uringcore-proto" ;; esac
    case " $passed " in *" uringloop "*) engines="$engines uringloop" ;; esac
    case " $passed " in *" uringloop-proto "*) engines="$engines uringloop-proto" ;; esac
    say "engines: $engines"
    bench "$LOOPS313" loops --engines "$engines" --modes "thread process" --workers "1 2 4" \
        --docker-opts "$LIMITS"
}

loops313_app() {
    local passed engines
    passed="$(cat "$OUT313/loops-313-passed" 2>/dev/null)"
    engines="asyncio-proto-app uvloop-proto-app uringpy-app uringpy-app-batch"
    case " $passed " in *" uringcore-proto "*) engines="$engines uringcore-proto-app" ;; esac
    bench "$LOOPS313" app --engines "$engines" --modes "thread process" --workers "1 4" \
        --docker-opts "$LIMITS"
}

if [ "$PROFILE" = small ]; then
    stage build      build_main               || exit 1
    stage tests      run_tests "$IMAGE"       || exit 1
    # Hand-offs counted by the interpreter, in the configurations of the main
    # run (same machine, connections and repetitions; threads only, since one
    # process per worker has nobody to hand the GIL to).
    stage h-factorial bench "$IMAGE" factorial --modes thread
    stage h-app       bench "$IMAGE" app --modes thread
    stage h-gilbatch  bench "$IMAGE" gilbatch --workers "1 4"
    stage h-handler   bench "$IMAGE" handler --engines "uringpy-app uringpy-app-batch" \
                          --modes thread --workers "1 4" --handler-work "0 5 10 20 30 100"
    # The io_uring-based asyncio loops on a version they support.
    stage build313   build_313                 || exit 1
    stage tests313   run_tests "$IMAGE313"
    stage check313   check_loops
    stage loops313   loops313
    stage app313     loops313_app
else
    CONNS="${CONNS:-$((100 * CORES))}"
    # Workers: powers of two up to the server's cores, and the cores themselves.
    W=""; n=1
    while [ "$n" -lt "$CORES" ]; do W="$W $n"; n=$((n * 2)); done
    W="${W# } $CORES"
    WS="1 4"; [ "$CORES" -gt 8 ] && WS="$WS 8"; [ "$CORES" -gt 4 ] && WS="$WS $CORES"
    say "connections $CONNS  workers $W (scaling), $WS (others)"
    stage build      build_main               || exit 1
    stage tests      run_tests "$IMAGE"       || exit 1
    stage L-scaling   bench "$IMAGE" scaling --engines "uringpy asyncio-proto uvloop-proto" \
                          --workers "$W" --conns "$CONNS" --docker-opts "--ulimit nofile=65536:65536"
    stage L-factorial bench "$IMAGE" factorial --workers "$WS" --conns "$CONNS" \
                          --docker-opts "--ulimit nofile=65536:65536"
    stage L-app       bench "$IMAGE" app --engines "uringpy-app uringpy-app-batch c-epoll-app c-epoll-app-batch asyncio-proto-app uvloop-proto-app" \
                          --workers "$WS" --conns "$CONNS" --exclude "*-proto-app/thread/*" \
                          --docker-opts "--ulimit nofile=65536:65536"
    stage L-handler   bench "$IMAGE" handler --engines "uringpy-app uringpy-app-batch" \
                          --modes "thread process" --workers "1 $CORES" --handler-work "0 10 30 100" \
                          --conns "$CONNS" --docker-opts "--ulimit nofile=65536:65536"
fi

cd "$REPO/benchmarks/results-revision" || exit 1
packed="$PROFILE"; [ -n "$(ls -A "${PROFILE}-py313" 2>/dev/null)" ] && packed="$packed ${PROFILE}-py313"
# shellcheck disable=SC2086
tar -czf "$HOME/results-revision-${PROFILE}-${COMMIT}.tgz" $packed
say "packed benchmarks/results-revision/{$packed} into ~/results-revision-${PROFILE}-${COMMIT}.tgz"
for d in $packed; do for d in "$d"/*/; do
    [ -f "$d/runs.csv" ] || continue
    total=$(($(wc -l < "$d/runs.csv") - 1))
    ok=$(awk -F, 'NR==1{for(i=1;i<=NF;i++)if($i=="status")c=i} NR>1&&$c=="ok"{n++} END{print n+0}' "$d/runs.csv")
    echo "   $d: $ok of $total runs ok"
done; done
if [ -n "$FAILED" ]; then
    say "FINISHED with failed stages:$FAILED"
    exit 1
fi
say "ALL DONE"
