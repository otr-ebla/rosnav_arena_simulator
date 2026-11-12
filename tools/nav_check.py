#!/usr/bin/env python3
"""Follow the robot during a running Arena simulation: its pose in the map
(TF map -> base_link), the current goal, distance to it, and episode resets.

Inside the container while a simulation is up:
    python3 ~/wm_social_robot/tools/nav_check.py [--duration 120] [--robot jackal]
"""
import argparse
import math
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.duration import Duration
from rclpy.time import Time
from std_msgs.msg import Empty
from tf2_ros import Buffer, TransformListener


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=120.0)
    ap.add_argument('--robot', default='jackal')
    ap.add_argument('--ns', default='/task_generator_node')
    ap.add_argument('--every', type=float, default=5.0)
    a = ap.parse_args()

    rclpy.init()
    node = rclpy.create_node('wm_nav_check')
    tf = Buffer(cache_time=Duration(seconds=10))
    TransformListener(tf, node)
    st = {'goal': None, 'resets': 0}

    def on_goal(m):
        st['goal'] = (m.pose.position.x, m.pose.position.y)
        print(f'[goal] new goal ({m.pose.position.x:.2f}, {m.pose.position.y:.2f})', flush=True)

    def on_reset(_):
        st['resets'] += 1
        print(f'[reset] episode reset #{st["resets"]}', flush=True)

    for t in (f'{a.ns}/{a.robot}/goal_pose', f'{a.ns}/goal', f'/{a.robot}/goal_pose', '/goal_pose'):
        node.create_subscription(PoseStamped, t, on_goal, 10)
    node.create_subscription(Empty, f'{a.ns}/task_reset', on_reset, 10)
    node.create_subscription(Empty, '/reset_end', on_reset, 10)

    frames = ['base_link', f'{a.robot}/base_link']
    t0 = last = time.time()
    path = 0.0
    prev = None
    while time.time() - t0 < a.duration:
        rclpy.spin_once(node, timeout_sec=0.1)
        if time.time() - last < a.every:
            continue
        last = time.time()
        pose = None
        for fr in frames:
            try:
                tr = tf.lookup_transform('map', fr, Time())
                pose = (tr.transform.translation.x, tr.transform.translation.y, fr)
                break
            except Exception:
                pass
        if pose is None:
            print('[pose] no TF map -> base_link yet', flush=True)
            continue
        if prev:
            path += math.dist(prev, pose[:2])
        prev = pose[:2]
        g = st['goal']
        d = f'{math.dist(g, pose[:2]):.2f} m to goal' if g else 'no goal seen'
        print(f'[pose] t={time.time() - t0:5.0f}s  ({pose[0]:6.2f}, {pose[1]:6.2f})  '
              f'driven {path:6.2f} m  {d}', flush=True)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
