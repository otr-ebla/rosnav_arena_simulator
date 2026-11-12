# ROS 2 Humble + Arena-Rosnav environment, sourced by every interactive shell
# in the container (via /etc/bash.bashrc). Equivalent of Arena's
# tools/source.bash (a.k.a. arena.bash) without pyenv/Poetry: here ROS 2 comes
# from apt and Arena's Python dependencies are installed system-wide.
#
# Helper functions:
#   arena_import   clone/update the pinned dependency repos into arena4_ws/src
#   (apt dependencies are installed by rosdep when the image is built:
#    run ./run.sh build on the host after package.xml files change)
#   arena_build    colcon build of arena4_ws (extra args go to colcon)
#   arena_launch   ros2 launch arena_bringup arena.launch.py (extra args = launch args)
#   arena_stop     kill leftover Gazebo / Arena / Nav2 processes in the container

export WM_PROJECT_DIR="${WM_PROJECT_DIR:-$HOME/wm_social_robot}"
export ARENA_WS_DIR="${ARENA_WS_DIR:-$WM_PROJECT_DIR/arena4_ws}"
export ARENA_ROS_DISTRO="${ARENA_ROS_DISTRO:-humble}"
export GAZEBO_VERSION="${GAZEBO_VERSION:-harmonic}"
export GZ_VERSION="$GAZEBO_VERSION"

# Same middleware settings as Arena's source.bash. The container has its own
# network namespace (Docker bridge), so this domain cannot collide with other
# users of the machine.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-1}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
if [ -f "$HOME/.ros/fastdds.xml" ]; then
    export FASTRTPS_DEFAULT_PROFILES_FILE="$HOME/.ros/fastdds.xml"
else
    # UDP only: stale shared-memory locks of killed processes lost messages and
    # hung Nav2's lifecycle bring-up (see the comment in the file)
    export FASTRTPS_DEFAULT_PROFILES_FILE="$WM_PROJECT_DIR/docker/fastdds_udp.xml"
fi
export QT_SCREEN_SCALE_FACTORS=1     # stop RViz from flashing (Arena)
export COLCON_DEFAULTS_FILE="${COLCON_DEFAULTS_FILE:-$WM_PROJECT_DIR/docker/colcon-defaults.yaml}"

# keep the colcon build polite on a shared machine; override before building
export ARENA_BUILD_WORKERS="${ARENA_BUILD_WORKERS:-8}"
export MAKEFLAGS="${MAKEFLAGS:--j4}"

. "/opt/ros/${ARENA_ROS_DISTRO}/setup.bash"
if [ -f "$ARENA_WS_DIR/install/local_setup.bash" ]; then
    . "$ARENA_WS_DIR/install/local_setup.bash"
fi

_ARENA_REPOS="$ARENA_WS_DIR/src/arena/arena-rosnav/.repos"

# Imports the exact commits that were built and tested (arena4_ws/workspace.lock.repos,
# incl. arena-isaac whose upstream pin "master@a4beefe0" no longer resolves),
# or Arena's own .repos files if there is no lock file, then applies the local
# patches (patches/, see tools/arena_patches.sh).
arena_import() {
    ( cd "$ARENA_WS_DIR" || exit 1
      if [ -f workspace.lock.repos ]; then
          echo "== vcs import workspace.lock.repos"
          vcs import --recursive src < workspace.lock.repos || exit 1
      else
          for r in arena gazebo isaac; do
              echo "== vcs import $r.repos"
              vcs import --recursive --skip-existing src < "$_ARENA_REPOS/$r.repos" || exit 1
          done
      fi
      "$WM_PROJECT_DIR/tools/arena_patches.sh" apply )
}

# symlink-install, cmake args and skipped ROS 1 packages: docker/colcon-defaults.yaml
arena_build() {
    ( cd "$ARENA_WS_DIR" || exit 1
      colcon build --parallel-workers "$ARENA_BUILD_WORKERS" "$@" )
    local rc=$?
    [ -f "$ARENA_WS_DIR/install/local_setup.bash" ] && . "$ARENA_WS_DIR/install/local_setup.bash"
    return $rc
}

arena_launch() {
    ros2 launch arena_bringup arena.launch.py "$@"
}

# Isaac Sim 4.2 standalone build (copied into the image from nvcr.io). Only
# loaded for sim:=isaac, because it puts Isaac's bundled Python packages and
# libraries on PYTHONPATH / LD_LIBRARY_PATH (same as Arena's isaacsim setup.bash).
export ISAAC_PATH=/opt/isaac-sim
arena_isaac_env() {
    [ -f "$ISAAC_PATH/setup_python_env.sh" ] || { echo "Isaac Sim is not installed in this image" >&2; return 1; }
    export CARB_APP_PATH="$ISAAC_PATH/kit" EXP_PATH="$ISAAC_PATH/apps"
    export OMNI_KIT_ACCEPT_EULA="${OMNI_KIT_ACCEPT_EULA:-YES}"
    . "$ISAAC_PATH/setup_python_env.sh"
    # Under VirtualGL (GUI runs) dlopen() is interposed, so the ROS 2 bridge
    # plugin no longer finds libomni.isaac.ros2_bridge.humble.so next to itself
    # ("ROS2 Bridge startup failed"). Put its directory on the search path.
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$ISAAC_PATH/exts/omni.isaac.ros2_bridge/bin"
}

# One command for every simulator / world / pedestrian count / renderer:
#   arena_sim sim:=gazebo world:=hospital peds:=10 render:=ogre2 gui:=true
#   arena_sim sim:=isaac world:=hospital peds:=8 gui:=true
# (ros2 launch wm_bringup sim.launch.py --show-args lists all options)
# GUI runs go through VirtualGL (GPU OpenGL on the ThinLinc display).
arena_sim() {
    ( local a gui=0 isaac=0
      for a in "$@"; do
          case "$a" in
              gui:=true|gui:=1|rviz:=true|rviz:=1) gui=1 ;;
              sim:=isaac) isaac=1 ;;
          esac
      done
      if [ "$isaac" = 1 ]; then
          arena_isaac_env || exit 1
          # headless Isaac must not see the X display: it probes GLX on it and
          # the ThinLinc X server has no NVIDIA GLX (GLXBadFBConfig)
          [ "$gui" = 0 ] && unset DISPLAY
      fi
      # Gazebo and Isaac Sim windows both need VirtualGL here (without it Isaac
      # fails with GLXBadFBConfig on the ThinLinc X server)
      if [ "$gui" = 1 ] && command -v vglrun >/dev/null; then
          exec vglrun -d egl ros2 launch wm_bringup sim.launch.py "$@"
      fi
      exec ros2 launch wm_bringup sim.launch.py "$@" )
}

# Stop every simulation process left in the container (Gazebo server, Arena
# nodes, Nav2). The [x]yz patterns keep pgrep from matching this shell itself.
arena_stop() {
    local k='[g]z sim|[r]os2 launch|[t]ask_generator|[h]unav|[p]arameter_bridge|[n]av2_|[l]ifecycle_manager|[w]orld_generator|[p]edestrian_marker|[r]obot_state_publisher|[r]un_isaacsim|[i]saac-sim/kit|[r]viz2'
    # never signal shells: a `bash -c "... ros2 launch ..."` command line would
    # match the patterns, and no simulation process is a bash process
    _arena_pids() { pgrep -f "$k" | while read -r p; do
                        [ "$(ps -o comm= -p "$p" 2>/dev/null)" = bash ] || echo "$p"; done; }
    _arena_pids | xargs -r kill -INT 2>/dev/null
    local i; for i in $(seq 20); do [ -z "$(_arena_pids)" ] && break; sleep 1; done
    _arena_pids | xargs -r kill -9 2>/dev/null
    for i in $(seq 5); do [ -z "$(_arena_pids)" ] && break; sleep 1; done
    echo "simulation processes left: $(_arena_pids | wc -l)"
    unset -f _arena_pids
}

r2st() { ros2 service call "$1" "$(ros2 service type "$1")"; }   # from Arena

# Functions are deliberately not exported (export -f): they would end up in the
# environment of every child process, and Isaac Sim's process launcher fails on
# those BASH_FUNC_* variables. run.sh calls them in the shell that sourced this.
