#!/usr/bin/env python3
"""Statistics of one LaserScan: range limits, number of valid/inf/short returns."""
import math, sys
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
topic = sys.argv[1] if len(sys.argv) > 1 else '/task_generator_node/jackal/lidar'
rclpy.init(); n = rclpy.create_node('wm_scan_stats'); got = []
n.create_subscription(LaserScan, topic, lambda m: got.append(m), qos_profile_sensor_data)
while not got:
    rclpy.spin_once(n, timeout_sec=0.5)
m = got[0]; r = list(m.ranges)
fin = [x for x in r if math.isfinite(x)]
print(f"frame {m.header.frame_id}  n={len(r)}  angle [{math.degrees(m.angle_min):.0f},{math.degrees(m.angle_max):.0f}]"
      f"  range_min {m.range_min} range_max {m.range_max}")
print(f"finite {len(fin)}  inf/nan {len(r)-len(fin)}  min {min(fin) if fin else None:.3f}  "
      f"< 0.3 m: {sum(1 for x in fin if x < 0.3)}  < 0.5 m: {sum(1 for x in fin if x < 0.5)}")
short = [(round(math.degrees(m.angle_min + i * m.angle_increment)), round(x, 2)) for i, x in enumerate(r) if math.isfinite(x) and x < 0.5]
print("short returns (deg, m):", short[:40])
