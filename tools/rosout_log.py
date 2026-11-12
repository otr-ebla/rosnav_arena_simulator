#!/usr/bin/env python3
"""Write /rosout (all nodes' log messages, also of nodes whose console output is hidden) to stdout."""
import sys
import rclpy
from rcl_interfaces.msg import Log
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
L = {10: 'DEBUG', 20: 'INFO', 30: 'WARN', 40: 'ERROR', 50: 'FATAL'}
skip = sys.argv[1:] or ['out of bounds of the costmap', 'Aborting handle']
rclpy.init()
n = rclpy.create_node('wm_rosout_log')
def cb(m):
    if any(s in m.msg for s in skip):
        return
    print(f"{m.stamp.sec}.{m.stamp.nanosec // 1000000:03d} {L.get(m.level, m.level)} [{m.name}] {m.msg}", flush=True)
n.create_subscription(Log, '/rosout', cb, QoSProfile(depth=1000, reliability=ReliabilityPolicy.RELIABLE,
                                                       durability=DurabilityPolicy.TRANSIENT_LOCAL))
rclpy.spin(n)
