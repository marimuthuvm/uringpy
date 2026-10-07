#!/usr/bin/env bash
# The `loops` experiment: asyncio, uvloop and the io_uring-based asyncio loops
# (uringcore, uringloop) on one server script, as threads and as processes.
#
# Run on the CLIENT machine after run_paper_experiments.sh, in a clean checkout:
#
#     BASE_COMMIT=<commit of the paper's images> \
#         nohup setsid bash benchmarks/run_loops_experiment.sh > ~/loops-run.log 2>&1 < /dev/null &
#
# It builds uringpy:<BASE_COMMIT>-loops on the server from Dockerfile.loops, on
# top of the image uringpy:<BASE_COMMIT> that the paper's experiments used,
# reports which loops could be installed, and runs the experiment at 1, 2 and 4
# workers. It takes the same lock as run_paper_experiments.sh, so the two
# cannot run at the same time.
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
say "commit $COMMIT  base image $BASE  image $IMAGE"

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
for loop in uvloop uringcore uringloop; do
    out="$("${SSH[@]}" "timeout 60 docker run --rm --security-opt seccomp=unconfined $IMAGE \
        python3 -c \"import sys; sys.path.insert(0, 'benchmarks'); import sharded_server as s; s._new_loop('$loop').close(); print('loop-ok')\" 2>&1 | tail -n 1")"
    case "$out" in
        *loop-ok*) say "$loop: available" ;;
        *) say "$loop: NOT available: $(printf '%s' "$out" | cut -c1-200)" ;;
    esac
done

say "start  loops"
IMAGE="$IMAGE" python3 benchmarks/bench_matrix.py --experiment loops --workers 1,2,4 --reps "$REPS"
status=$?
cd "$REPO/benchmarks/results" || exit 1
names=()
for f in loops-uringpy-"${BASE_COMMIT}"-loops-*; do
    [ -e "$f" ] && names+=("$f")
done
if [ "${#names[@]}" -gt 0 ]; then
    tar -czf "$HOME/results-loops-${BASE_COMMIT}.tgz" "${names[@]}"
    say "packed ${#names[@]} folder(s) into ~/results-loops-${BASE_COMMIT}.tgz"
fi
[ "$status" -eq 0 ] && say "ALL DONE" || say "FINISHED with driver exit status $status"
