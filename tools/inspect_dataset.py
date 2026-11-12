#!/usr/bin/env python3
"""Print a summary of a recorded dataset and optionally render a contact sheet.

    python tools/inspect_dataset.py data/run_XXXX
    python tools/inspect_dataset.py data/run_XXXX --sheet sheet.png --episode 0

The contact sheet shows, for evenly spaced steps of one episode, the camera
frame (top) and a robot-centred bird's-eye view (bottom): LiDAR points (white),
pedestrians (red), navigation target (green), commanded velocity (yellow).
"""
import argparse

import numpy as np

from wm_dataset import SocialNavDataset, load_episode


def birdseye(ep, k, size=192, span=6.0):
    import cv2
    img = np.zeros((size, size, 3), np.uint8)
    sc = size / (2 * span)

    def px(x, y):      # robot frame (x forward, y left) -> pixel (forward = up)
        return int(size / 2 - y * sc), int(size / 2 - x * sc)

    n = ep['lidar'].shape[1]
    a0, da = ep['attrs']['lidar_angle_min'], ep['attrs']['lidar_angle_increment']
    ang = a0 + np.arange(n) * da
    r = ep['lidar'][k]
    m = r < ep['attrs']['lidar_range_max'] - 1e-3
    for x, y in zip(r[m] * np.cos(ang[m]), r[m] * np.sin(ang[m])):
        cv2.circle(img, px(x, y), 0, (255, 255, 255), -1)
    x0, y0, yaw = ep['pose'][k]
    c, s = np.cos(yaw), np.sin(yaw)
    for p in ep['peds'][k]:
        if p[4] > 0:
            dx, dy = p[0] - x0, p[1] - y0
            cv2.circle(img, px(c * dx + s * dy, -s * dx + c * dy), int(0.25 * sc), (60, 60, 255), 1)
    cv2.circle(img, px(*ep['goal_rel'][k]), 4, (60, 255, 60), -1)
    cv2.circle(img, px(0, 0), int(0.3 * sc), (255, 160, 0), 1)
    cv2.arrowedLine(img, px(0, 0), px(ep['cmd'][k][0] * 1.5, ep['cmd'][k][1] * 1.5), (0, 255, 255), 1)
    return img


def contact_sheet(path, out, cols=8):
    import cv2
    ep = load_episode(path)
    T = len(ep['time'])
    tiles = []
    for k in np.linspace(0, T - 1, cols).round().astype(int):
        rgb = cv2.resize(ep['rgb'][k][:, :, ::-1], (192, 144), interpolation=cv2.INTER_NEAREST)
        cv2.putText(rgb, f't={ep["time"][k] - ep["time"][0]:.1f}s', (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        tiles.append(np.vstack([rgb, birdseye(ep, k)]))
    cv2.imwrite(out, np.hstack(tiles))
    a = ep['attrs']
    print(f'wrote {out}: episode {a["episode_id"]} ({a["scenario"]}, {a["outcome"]}, {T} steps)')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('root')
    p.add_argument('--sheet', help='write a PNG contact sheet of one episode')
    p.add_argument('--episode', type=int, default=0, help='episode index for --sheet')
    a = p.parse_args()

    ds = SocialNavDataset(a.root)
    print(ds.summary())
    print(f'{"episode":34s} {"scenario":16s} {"outcome":10s} steps  peds  dt[s]  |cmd-vel|')
    for e in ds.episodes:
        ep = load_episode(e.path, ('cmd', 'vel', 'time'))
        err = np.abs(ep['cmd'][:-1] - ep['vel'][1:]).mean()
        print(f'{e.episode_id:34s} {e.scenario:16s} {e.outcome:10s} {e.length:5d} '
              f'{e.meta["num_pedestrians"]:5d}  {e.meta["dt_mean"]:.3f}  {err:.3f}')
    if a.sheet and ds.episodes:
        contact_sheet(ds.episodes[a.episode].path, a.sheet)


if __name__ == '__main__':
    main()
