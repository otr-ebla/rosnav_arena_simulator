#!/bin/bash
# Smoke-test simulations headless, one after the other, inside the container:
#   tools/test_worlds.sh [seconds] [launch args...]
#   tools/test_worlds.sh 90 sim:=gazebo peds:=8 render:=ogre2
# WORLDS="hospital factory" tools/test_worlds.sh ...   to test a subset.
# For each world: start wm_bringup/sim.launch.py, wait, run tools/sim_check.py,
# stop everything. Logs go to /tmp/test_worlds/<world>.log.
WAIT="${1:-90}"; shift || true
. "$WM_PROJECT_DIR/docker/arena_env.bash"
WORLDS="${WORLDS:-$(ls "$(ros2 pkg prefix arena_simulation_setup)/share/arena_simulation_setup/worlds")}"
mkdir -p /tmp/test_worlds
for w in $WORLDS; do
    echo "=================== world:=$w $*"
    timeout -s INT $((WAIT + 60)) ros2 launch wm_bringup sim.launch.py world:="$w" "$@" \
        > "/tmp/test_worlds/$w.log" 2>&1 &
    sleep "$WAIT"
    python3 "$WM_PROJECT_DIR/tools/sim_check.py" --duration 15
    echo "tracebacks in log: $(grep -c Traceback "/tmp/test_worlds/$w.log")" \
         " gazebo errors: $(grep -c '\[Err\]' "/tmp/test_worlds/$w.log")"
    arena_stop >/dev/null
    wait
done
