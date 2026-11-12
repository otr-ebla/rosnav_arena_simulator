#!/usr/bin/env python3
"""Check a running Arena simulation: message rates of the streams needed for
the world-model dataset, number of pedestrians and whether they move.

Run inside the container while a simulation is up:
    python3 ~/wm_social_robot/tools/sim_check.py [--duration 10] [--robot jackal]
"""
import argparse
import math
import time

import rclpy
from hunav_msgs.msg import Agents
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=10.0)
    ap.add_argument('--robot', default='jackal')
    ap.add_argument('--ns', default='/task_generator_node')
    a = ap.parse_args()

    rclpy.init()
    node = rclpy.create_node('wm_sim_check')
    r = f'{a.ns}/{a.robot}'
    streams = {
        '/clock': Clock,
        f'{r}/lidar': LaserScan,
        f'{r}/odom': Odometry,
        f'{r}/cmd_vel': Twist,
        f'{a.ns}/human_states': Agents,
    }
    counts = {t: 0 for t in streams}
    peds = {'max': 0, 'first': {}, 'last': {}}
    sim_t = []

    def cb(topic):
        def f(msg):
            counts[topic] += 1
            if topic == '/clock':
                sim_t.append(msg.clock.sec + msg.clock.nanosec * 1e-9)
            elif topic.endswith('human_states'):
                people = [ag for ag in msg.agents if ag.type == ag.PERSON]
                peds['max'] = max(peds['max'], len(people))
                for ag in people:
                    p = (ag.position.position.x, ag.position.position.y)
                    peds['first'].setdefault(ag.id, p)
                    peds['last'][ag.id] = p
        return f

    for t, typ in streams.items():
        node.create_subscription(typ, t, cb(t), qos_profile_sensor_data if typ is LaserScan else 10)

    t0 = time.monotonic()
    while time.monotonic() - t0 < a.duration:
        rclpy.spin_once(node, timeout_sec=0.1)
    wall = time.monotonic() - t0

    print(f'--- {wall:.1f} s wall time')
    for t, n in counts.items():
        print(f'{t:45s} {n / wall:7.1f} Hz' if n else f'{t:45s}   no messages')
    if len(sim_t) > 1:
        print(f'real-time factor                              {(sim_t[-1] - sim_t[0]) / wall:7.2f}')
    moved = [math.dist(peds['first'][i], peds['last'][i]) for i in peds['last']]
    print(f'pedestrians (max seen)                        {peds["max"]:7d}')
    if moved:
        print(f'pedestrian displacement [m] min/mean/max     '
              f'{min(moved):.2f} / {sum(moved) / len(moved):.2f} / {max(moved):.2f}')
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
