#!/usr/bin/env python3
"""Print every TF edge (parent -> child, translation, yaw/roll) seen for a few seconds."""
import math, sys, time
import rclpy
from rclpy.qos import QoSProfile, DurabilityPolicy
from tf2_msgs.msg import TFMessage
rclpy.init(); n = rclpy.create_node('tf_dump'); edges = {}
def cb(static):
    def f(m):
        for t in m.transforms:
            q = t.transform.rotation; tr = t.transform.translation
            roll = math.degrees(math.atan2(2*(q.w*q.x+q.y*q.z), 1-2*(q.x*q.x+q.y*q.y)))
            yaw = math.degrees(math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)))
            edges[(t.header.frame_id, t.child_frame_id)] = (static, tr.x, tr.y, tr.z, roll, yaw)
    return f
n.create_subscription(TFMessage, '/tf', cb(False), 100)
n.create_subscription(TFMessage, '/tf_static', cb(True), QoSProfile(depth=100, durability=DurabilityPolicy.TRANSIENT_LOCAL))
t0 = time.time()
while time.time() - t0 < float(sys.argv[1] if len(sys.argv) > 1 else 3):
    rclpy.spin_once(n, timeout_sec=0.1)
for (p, c), (s, x, y, z, r, yw) in sorted(edges.items()):
    print(f"{'S' if s else 'D'} {p:>28} -> {c:<32} ({x:7.2f},{y:7.2f},{z:6.2f}) roll {r:6.1f} yaw {yw:6.1f}")
