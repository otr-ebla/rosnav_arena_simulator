#!/bin/bash
# Host-side wrapper around the development container (no sudo needed on the host).
#
#   ./run.sh setup        first-time: build image, import Arena's pinned repos,
#                         rebuild image with their rosdep dependencies
#   ./run.sh build        (re)build the image (rerun after the workspace's package.xml change)
#   ./run.sh up           start the container in the background
#   ./run.sh shell        interactive shell in it (starts it if needed)
#   ./run.sh exec CMD...  run one command inside, with the ROS/Arena environment
#   ./run.sh import       vcs-import Arena's dependency repos into arena4_ws/src
#   ./run.sh ws-build [colcon args]   colcon build of arena4_ws
#   ./run.sh gpu-test     check that GPU, EGL and Vulkan work inside
#   ./run.sh stop         stop the container, keeping it
#   ./run.sh down         remove the container (volumes and image are kept)
set -euo pipefail

export PROJECT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
export USERNAME="$(id -un)" USER_UID="$(id -u)" USER_GID="$(id -g)"
export XAUTH_FILE="/tmp/wm_docker_${USERNAME}.xauth"
NAME="wm-${USERNAME}"
WS="$PROJECT_DIR/arena4_ws"
compose() { docker compose -f "$PROJECT_DIR/docker/compose.yaml" "$@"; }

xauth_file() {  # X cookie usable from another hostname (the container's)
    install -m 600 /dev/null "$XAUTH_FILE"
    if [ -n "${DISPLAY:-}" ] && command -v xauth >/dev/null; then
        xauth nlist "$DISPLAY" 2>/dev/null | sed 's/^..../ffff/' | xauth -f "$XAUTH_FILE" nmerge - 2>/dev/null || true
    fi
}

# Mount points of the build/install/log volumes inside the bind-mounted
# workspace. Created by the user because Docker's root cannot write on NFS.
mountpoints() { mkdir -p "$WS/src" "$WS/build" "$WS/install" "$WS/log"; }

# NVIDIA OptiX (RTX denoiser) and NGX (DLSS) user-space libraries for Isaac
# Sim. The container toolkit only injects what the host has installed, and this
# host lacks them; they must match the host driver version exactly. Fetched from
# the host's Debian repository with `apt-get download` (no sudo, nothing is
# installed on the host) into docker/nvidia-extra/, copied into the image.
nvidia_extra() {
    local ver dir tmp pkg v
    ver="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)" || return 0
    dir="$PROJECT_DIR/docker/nvidia-extra"
    [ -n "$ver" ] && [ -f "$dir/VERSION" ] && [ "$(cat "$dir/VERSION")" = "$ver" ] && return 0
    command -v apt-get >/dev/null || return 0
    tmp="$(mktemp -d)"; rm -rf "$dir"; mkdir -p "$dir"
    for pkg in libnvoptix1 libnvidia-ngx1; do
        v="$(apt-cache madison "$pkg" 2>/dev/null | awk -v ver="$ver" '$3 ~ "^"ver"-" {print $3; exit}')"
        if [ -z "$v" ]; then echo "nvidia-extra: no $pkg for driver $ver, skipped" >&2; continue; fi
        (cd "$tmp" && apt-get download -q "$pkg=$v" >/dev/null) && dpkg-deb -x "$tmp"/${pkg}_*.deb "$tmp/x"
    done
    find "$tmp/x" -type f \( -name '*.so*' -o -name '*.bin' \) -exec cp -a {} "$dir/" \; 2>/dev/null || true
    find "$tmp/x" -path '*nvidia-ngx-updater*' -prune -o -type d -name 'wine' -prune -o -type f -name 'nvngx*' -exec cp -a {} "$dir/" \; 2>/dev/null || true
    echo "$ver" > "$dir/VERSION"; rm -rf "$tmp"
    echo "nvidia-extra: $(ls "$dir" | grep -vc VERSION) files for driver $ver"
}

up()    { mountpoints; xauth_file; compose up -d; }
inside() { docker exec ${TTY:+-it} -e DISPLAY="${DISPLAY:-}" "$NAME" \
               bash -c '. "$WM_PROJECT_DIR/docker/arena_env.bash" && cd "$ARENA_WS_DIR" && "$@"' bash "$@"; }
[ -t 0 ] && [ -t 1 ] && TTY=1 || TTY=

cmd="${1:-shell}"; shift || true
case "$cmd" in
    build)    mountpoints; nvidia_extra; compose build ;;
    up)       up ;;
    shell)    up; docker exec -it -e DISPLAY="${DISPLAY:-}" -w "/home/$USERNAME/wm_social_robot/arena4_ws" "$NAME" bash ;;
    exec)     up; inside "$@" ;;
    import)   up; inside arena_import ;;
    ws-build) up; inside arena_build "$@" ;;
    setup)    mountpoints; nvidia_extra; compose build
              up; inside arena_import
              compose build; up
              echo; echo "Image ready. Next: ./run.sh ws-build" ;;
    gpu-test) up; docker exec "$NAME" bash -c '
                  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
                  echo "--- Vulkan";  vulkaninfo --summary 2>&1 | grep -E "deviceName|driverInfo"
                  echo "--- OpenGL through VirtualGL (vglrun -d egl)"
                  vglrun -d egl glxinfo -B 2>&1 | grep -E "OpenGL renderer"' ;;
    stop)     compose stop ;;
    down)     compose down ;;
    *)        sed -n '2,15p' "$0"; exit 1 ;;
esac
