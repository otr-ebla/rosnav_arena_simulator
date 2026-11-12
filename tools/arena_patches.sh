#!/bin/bash
# Local fixes/extensions to upstream Arena repositories, kept as patch files in
# ../patches/ so they survive a fresh `vcs import` of the pinned commits.
#
#   tools/arena_patches.sh status   which patches are applied
#   tools/arena_patches.sh apply    apply all patches that are not applied yet
#   tools/arena_patches.sh save     re-export patches from the working trees (after editing)
#
# One patch per repository: patches/<path relative to arena4_ws/src, / -> __>.patch
# Works on the host or in the container (only needs git).
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
SRC="$ROOT/arena4_ws/src"
PATCHES="$ROOT/patches"
REPOS=(arena/arena-rosnav arena/simulation-setup arena/isaac gazebo/hunav_gz_plugin)

pfile() { echo "$PATCHES/${1//\//__}.patch"; }

case "${1:-status}" in
    save)
        mkdir -p "$PATCHES"
        # stage everything (new files, renames, binaries like map .pgm) so the patch
        # is complete; --binary keeps binary files, -M records moves as renames
        for r in "${REPOS[@]}"; do
            git -C "$SRC/$r" add -A
            if [ -n "$(git -C "$SRC/$r" diff --cached --stat)" ]; then
                git -C "$SRC/$r" diff --cached -M --binary > "$(pfile "$r")"
                echo "saved   $(basename "$(pfile "$r")")  ($(git -C "$SRC/$r" diff --cached --shortstat))"
            fi
        done ;;
    apply|status)
        for r in "${REPOS[@]}"; do
            p="$(pfile "$r")"; [ -f "$p" ] || continue
            if git -C "$SRC/$r" apply --reverse --check "$p" 2>/dev/null; then
                echo "applied     $r"
            elif git -C "$SRC/$r" apply --check "$p" 2>/dev/null; then
                if [ "$1" = apply ]; then git -C "$SRC/$r" apply --index "$p"; echo "applying    $r: done"
                else echo "NOT applied $r"; fi
            else
                echo "CONFLICT    $r: $(basename "$p") does not apply cleanly" >&2; exit 1
            fi
        done ;;
    *) sed -n '2,11p' "$0"; exit 1 ;;
esac
