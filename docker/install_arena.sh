#!/bin/bash
# SUPERSEDED (kept for reference): the image is now based on ros:humble and the
# workspace is ../arena4_ws, built with `./run.sh setup` + `./run.sh ws-build`.
# Arena's upstream installer used below compiles ROS 2 itself from source and
# uses pyenv/Poetry; do not run it in the current image.
#
# Run INSIDE the container: installs Arena-Rosnav (branch humble) with its own
# installer into ~/arena4_ws. Re-running resumes where it stopped.
#
#   INSTALL_ISAAC=Y bash install_arena.sh     # also install Isaac Sim 4.2 (~20 GB)
#
# The installer asks, in order: workspace dir, then one question per optional
# component (gazebo, isaac, planners). Those answers are supplied below; run
# Arena's install.sh by hand instead if you want to answer them yourself.
set -eo pipefail

export ARENA_WS_DIR="${ARENA_WS_DIR:-$HOME/arena4_ws}"
export ARENA_BRANCH="${ARENA_BRANCH:-humble}"
export RCFILE="$HOME/.bashrc"
INSTALL_ISAAC="${INSTALL_ISAAC:-N}"

mkdir -p "$ARENA_WS_DIR" && cd "$ARENA_WS_DIR"
curl -fsSL "https://raw.githubusercontent.com/Arena-Rosnav/arena-rosnav/${ARENA_BRANCH}/installers/install.sh" -o install.sh

#       ws dir | gazebo | isaac            | planners
printf '\nY\n%s\nY\n' "$INSTALL_ISAAC" | bash -i install.sh 2>&1 | tee -a "$ARENA_WS_DIR/install.log"

echo
echo "Arena-Rosnav installed in $ARENA_WS_DIR. To use it:"
echo "  cd $ARENA_WS_DIR && . arena.bash"
