#!/usr/bin/env python3
"""Log Nav2 NavigateToPose results (succeeded / aborted / canceled) with the robot pose.

    python3 ~/wm_social_robot/tools/nav_goals.py [--duration 600] [--robot jackal]
"""
import argparse, time
import rclpy
from action_msgs.msg import GoalStatusArray
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener
NAMES = {1: 'accepted', 2: 'executing', 3: 'canceling', 4: 'SUCCEEDED', 5: 'canceled', 6: 'ABORTED'}
ap = argparse.ArgumentParser(); ap.add_argument('--duration', type=float, default=600); ap.add_argument('--robot', default='jackal')
a = ap.parse_args()
rclpy.init(); n = rclpy.create_node('wm_nav_goals'); tf = Buffer(); TransformListener(tf, n)
seen = {}; count = {}
def cb(m):
    for s in m.status_list:
        gid = bytes(s.goal_info.goal_id.uuid).hex()[:8]
        if seen.get(gid) == s.status:
            continue
        seen[gid] = s.status
        if s.status in (4, 5, 6):
            count[NAMES[s.status]] = count.get(NAMES[s.status], 0) + 1
        try:
            t = tf.lookup_transform('map', f'{a.robot}/base_link', Time()).transform.translation
            pos = f'({t.x:6.2f},{t.y:6.2f})'
        except Exception:
            pos = '(?)'
        print(f'{time.strftime("%H:%M:%S")} goal {gid} {NAMES.get(s.status, s.status):10s} robot {pos}  totals {count}', flush=True)
n.create_subscription(GoalStatusArray, f'/task_generator_node/{a.robot}/navigate_to_pose/_action/status', cb, 10)
t0 = time.time()
while time.time() - t0 < a.duration:
    rclpy.spin_once(n, timeout_sec=0.2)
print('final totals', count, flush=True)
