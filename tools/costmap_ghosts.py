#!/usr/bin/env python3
"""Lethal cells in Nav2's global costmap that are free in the static map
(obstacles seen by the sensors: people, or stale 'ghost' marks), as clusters."""
import sys
import numpy as np
import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSProfile, DurabilityPolicy
from scipy import ndimage
robot = sys.argv[1] if len(sys.argv) > 1 else 'jackal'
rclpy.init(); n = rclpy.create_node('wm_costmap_ghosts'); got = {}
n.create_subscription(OccupancyGrid, f'/task_generator_node/{robot}/global_costmap/costmap', lambda m: got.__setitem__('c', m), 1)
n.create_subscription(OccupancyGrid, '/task_generator_node/map', lambda m: got.__setitem__('m', m), QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
while len(got) < 2:
    rclpy.spin_once(n, timeout_sec=0.5)
c, m = got['c'], got['m']
C = np.array(c.data, dtype=np.int16).reshape(c.info.height, c.info.width)
M = np.array(m.data, dtype=np.int16).reshape(m.info.height, m.info.width)
print('costmap', C.shape, c.info.resolution, (c.info.origin.position.x, c.info.origin.position.y), ' map', M.shape)
if C.shape != M.shape:
    sys.exit('different sizes')
extra = (C == 100) & (M == 0)
lab, k = ndimage.label(ndimage.binary_dilation(extra, iterations=2))
print('lethal cells free in the map:', int(extra.sum()), 'clusters:', k)
r = c.info.resolution; ox, oy = c.info.origin.position.x, c.info.origin.position.y
sizes = ndimage.sum(extra, lab, range(1, k + 1))
for i in np.argsort(-sizes)[:15]:
    ys, xs = np.nonzero((lab == i + 1) & extra)
    print(f'  {int(sizes[i]):4d} cells at ({ox + xs.mean() * r:6.2f}, {oy + ys.mean() * r:6.2f})  extent {np.ptp(xs) * r:.1f} x {np.ptp(ys) * r:.1f} m')
