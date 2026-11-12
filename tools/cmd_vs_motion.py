#!/usr/bin/env python3
"""Compare commanded velocity (cmd_vel) with the robot's actual motion (TF map->base_link),
per second of simulated time."""
import math, sys, time
import rclpy
from geometry_msgs.msg import Twist
from rclpy.duration import Duration
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener
robot = sys.argv[1] if len(sys.argv) > 1 else 'jackal'
dur = float(sys.argv[2]) if len(sys.argv) > 2 else 30
rclpy.init(); n = rclpy.create_node('wm_cmd_vs_motion', parameter_overrides=[rclpy.parameter.Parameter('use_sim_time', value=True)])
tf = Buffer(cache_time=Duration(seconds=30)); TransformListener(tf, n)
cmds = []
n.create_subscription(Twist, f'/task_generator_node/{robot}/cmd_vel', lambda m: cmds.append((m.linear.x, m.angular.z)), 10)
prev = None; t0 = time.time()
while time.time() - t0 < dur:
    end = time.time() + 2.0
    while time.time() < end:
        rclpy.spin_once(n, timeout_sec=0.05)
    try:
        tr = tf.lookup_transform('map', f'{robot}/base_link', Time())
    except Exception as e:
        print('no tf', e); continue
    st = tr.header.stamp.sec + tr.header.stamp.nanosec * 1e-9
    q = tr.transform.rotation; yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    cur = (st, tr.transform.translation.x, tr.transform.translation.y, yaw)
    if prev and cur[0] > prev[0]:
        dt = cur[0] - prev[0]
        v = math.dist(cur[1:3], prev[1:3]) / dt
        w = math.atan2(math.sin(cur[3] - prev[3]), math.cos(cur[3] - prev[3])) / dt
        cv = sum(c[0] for c in cmds) / len(cmds) if cmds else float('nan')
        cw = sum(c[1] for c in cmds) / len(cmds) if cmds else float('nan')
        print(f'sim {cur[0]:8.1f}  pos ({cur[1]:6.2f},{cur[2]:6.2f})  cmd v={cv:5.2f} w={cw:5.2f}  actual v={v:5.2f} w={w:5.2f}  [{len(cmds)} cmds]', flush=True)
    prev = cur; cmds.clear()
