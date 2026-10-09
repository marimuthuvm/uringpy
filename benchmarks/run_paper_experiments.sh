#!/usr/bin/env bash
# Run every experiment of the paper at ONE commit, on both interpreter builds.
#
# Run on the CLIENT machine, in a checkout of the commit to be measured:
#
#     SERVER=user@10.0.0.2 SERVER_IP=10.0.0.2 \
#         nohup setsid bash benchmarks/run_paper_experiments.sh > ~/paper-run.log 2>&1 < /dev/null &
#
# SERVER and SERVER_IP may instead be exported by ~/bench.env. What it does:
#
#   1. refuses to start if tracked files differ from the commit, or if another
#      run holds the lock;
#   2. sends exactly this commit to the server (git archive) and builds the two
#      images there from Dockerfile.bench: uringpy:<commit> (GIL) and
#      uringpy:<commit>t (free-threaded);
#   3. runs the test suite inside each image and stops if it fails;
#   4. runs the contention probe and the handler thread control in the images;
#   5. runs the experiments below, in this order, 5 repetitions each;
#   6. packs the new result folders into ~/results-<commit>.tgz.
#
# Each finished stage is recorded in ~/paper-run-<commit>.done, so running the
# script again continues with the first stage that has not finished. A stage
# that fails is reported and the script goes on to the next one.
#
# About 2,000 runs, 18 hours. Do not use either machine for anything else while
# it runs: a second job on the client takes cores away from wrk.
#
# Environment: REPS (default 5), ONLY (space-separated stage names to run,
# default all), PROBE_REPS (default 20).

set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
# shellcheck disable=SC1091
[ -f "$HOME/bench.env" ] && . "$HOME/bench.env"
: "${SERVER:?set SERVER=user@host (ssh target of the server machine)}"
: "${SERVER_IP:?set SERVER_IP (address the client sends load to)}"
export SERVER SERVER_IP
REPS="${REPS:-5}"
PROBE_REPS="${PROBE_REPS:-20}"
ONLY="${ONLY:-}"
RESULTS="$REPO/benchmarks/results"
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "$SERVER")

say() { echo "== $(date -u +%H:%M:%SZ) $*"; }

exec 9> "$HOME/.uringpy-paper-run.lock"
if ! flock -n 9; then
    say "another run holds the lock: not starting"
    exit 1
fi

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    say "tracked files differ from the commit: commit or discard them first"
    git status --porcelain --untracked-files=no
    exit 1
fi

COMMIT="$(git rev-parse --short=7 HEAD)"
GIL_IMAGE="uringpy:${COMMIT}"
FT_IMAGE="uringpy:${COMMIT}t"
DONE="$HOME/paper-run-${COMMIT}.done"
DAY="$(date -u +%Y%m%d)"
FAILED=""
touch "$DONE"

say "commit $COMMIT  server $SERVER  images $GIL_IMAGE $FT_IMAGE  reps $REPS"

wanted() {  # is this stage selected by ONLY?
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

build_images() {
    local dir="uringpy-build-${COMMIT}"
    git archive --format=tar HEAD \
        | "${SSH[@]}" "rm -rf ~/$dir && mkdir -p ~/$dir && tar -xf - -C ~/$dir" || return 1
    "${SSH[@]}" "cd ~/$dir && docker build -q -f Dockerfile.bench -t $GIL_IMAGE . \
        && docker build -q -f Dockerfile.bench --build-arg FREE_THREADED=1 -t $FT_IMAGE ." || return 1
    "${SSH[@]}" "docker run --rm $GIL_IMAGE python3 -c 'import sys; print(sys.version)'; \
                 docker run --rm $FT_IMAGE  python3 -c 'import sys; print(sys.version)'"
}

run_tests() {  # run_tests <image>: up to three tries, the last lines go to the log
    local image="$1" try out
    for try in 1 2 3; do
        out="$("${SSH[@]}" "docker run --rm --network host --security-opt seccomp=unconfined \
            $image python3 -m pytest -q 2>&1 | tail -n 15")"
        say "tests $image (try $try): $(printf '%s\n' "$out" | tail -n 1)"
        case "$(printf '%s\n' "$out" | tail -n 1)" in
            *failed*|*error*) printf '%s\n' "$out" ;;
            *passed*) return 0 ;;
            *) printf '%s\n' "$out" ;;
        esac
    done
    return 1
}

run_probe() {  # run_probe <image> <tag>
    local out="$RESULTS/probe-$2-${DAY}.txt"
    "${SSH[@]}" "docker run --rm --security-opt seccomp=unconfined -e KMAX=3 -e REPS=$PROBE_REPS $1 \
        sh -c 'python3 benchmarks/setup_gilprobe.py build_ext --inplace >/dev/null 2>&1 \
               && python3 benchmarks/gil_experiment.py'" > "$out.tmp" 2>&1 || return 1
    mv "$out.tmp" "$out"
}

run_control() {
    local out="$RESULTS/handler-thread-control-${COMMIT}-${DAY}.txt" image work
    {
        echo "# Control for the handler sweep: benchmarks/handler_thread_control.py inside"
        echo "# each image on the server machine, 20000 calls per thread, commit $COMMIT."
        for image in "$GIL_IMAGE" "$FT_IMAGE"; do
            for work in 0 30 100 300 1000 3000; do
                echo "== $image HANDLER_WORK=$work"
                "${SSH[@]}" "docker run --rm -e HANDLER_WORK=$work $image \
                    python3 benchmarks/handler_thread_control.py" || return 1
            done
        done
    } > "$out.tmp" 2>&1 || return 1
    mv "$out.tmp" "$out"
}

bench() {  # bench <image> <experiment> [driver options...]
    local image="$1" experiment="$2"; shift 2
    IMAGE="$image" python3 benchmarks/bench_matrix.py --experiment "$experiment" \
        --reps "$REPS" "$@"
}

# --- preparation: any failure here stops the run -----------------------------
stage build      build_images          || exit 1
stage tests-gil  run_tests "$GIL_IMAGE" || exit 1
stage tests-ft   run_tests "$FT_IMAGE"  || exit 1
stage probe      run_probe "$GIL_IMAGE" "uringpy-${COMMIT}"
stage control    run_control

# --- experiments, the decisive ones first ------------------------------------
# GIL build
stage g-factorial bench "$GIL_IMAGE" factorial
stage g-gilbatch  bench "$GIL_IMAGE" gilbatch
stage g-app       bench "$GIL_IMAGE" app
stage g-load      bench "$GIL_IMAGE" load
stage g-scaling   bench "$GIL_IMAGE" scaling
stage g-handler   bench "$GIL_IMAGE" handler
# Free-threaded build: uvloop is not installed there (it is not ready for
# free threading), so its engines are left out.
stage t-scaling   bench "$FT_IMAGE" scaling --engines uringpy,asyncio,asyncio-proto
stage t-factorial bench "$FT_IMAGE" factorial --modes thread
stage t-app       bench "$FT_IMAGE" app \
    --engines uringpy-app,uringpy-app-batch,c-epoll-app,c-epoll-app-batch,asyncio-app,asyncio-proto-app
stage t-handler   bench "$FT_IMAGE" handler --engines uringpy-app --modes thread
# Small ones last
stage g-batch     bench "$GIL_IMAGE" batch
stage g-size      bench "$GIL_IMAGE" size

# --- pack what this commit produced -------------------------------------------
cd "$RESULTS" || exit 1
names=()
for f in *-uringpy-"${COMMIT}"-* *-uringpy-"${COMMIT}"t-* \
         handler-thread-control-"${COMMIT}"-*.txt; do
    [ -e "$f" ] && names+=("$f")
done
if [ "${#names[@]}" -gt 0 ]; then
    tar -czf "$HOME/results-${COMMIT}.tgz" "${names[@]}"
    say "packed ${#names[@]} items into ~/results-${COMMIT}.tgz"
    for d in "${names[@]}"; do
        [ -f "$d/runs.csv" ] || continue
        total=$(($(wc -l < "$d/runs.csv") - 1))
        ok=$(awk -F, 'NR==1{for(i=1;i<=NF;i++)if($i=="status")c=i} NR>1&&$c=="ok"{n++} END{print n+0}' "$d/runs.csv")
        echo "   $d: $ok of $total runs ok"
    done
fi

if [ -n "$FAILED" ]; then
    say "FINISHED with failed stages:$FAILED"
    exit 1
fi
say "ALL DONE"
