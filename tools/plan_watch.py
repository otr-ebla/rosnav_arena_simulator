#!/usr/bin/env python3
"""Print, for every new global plan: length, goal, and the heading of its first 2 m
(to spot a plan flipping between alternative routes)."""
import math, sys, time
import rclpy
from nav_msgs.msg import Path
robot = sys.argv[1] if len(sys.argv) > 1 else 'jackal'
dur = float(sys.argv[2]) if len(sys.argv) > 2 else 30
rclpy.init(); n = rclpy.create_node('wm_plan_watch'); last = [0.0]
def cb(m):
    if time.time() - last[0] < 1.0 or not m.poses:
        return
    last[0] = time.time()
    p = [(q.pose.position.x, q.pose.position.y) for q in m.poses]
    L = sum(math.dist(a, b) for a, b in zip(p, p[1:]))
    k = next((i for i in range(len(p)) if math.dist(p[0], p[i]) > 2.0), len(p) - 1)
    hd = math.degrees(math.atan2(p[k][1] - p[0][1], p[k][0] - p[0][0]))
    print(f'{time.strftime("%H:%M:%S")} start ({p[0][0]:6.2f},{p[0][1]:6.2f}) goal ({p[-1][0]:6.2f},{p[-1][1]:6.2f}) '
          f'length {L:5.1f} m  first-2m heading {hd:6.0f} deg', flush=True)
n.create_subscription(Path, f'/task_generator_node/{robot}/plan', cb, 10)
t0 = time.time()
while time.time() - t0 < dur:
    rclpy.spin_once(n, timeout_sec=0.2)
