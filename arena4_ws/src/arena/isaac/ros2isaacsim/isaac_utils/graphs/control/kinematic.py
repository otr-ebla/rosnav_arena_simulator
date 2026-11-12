"""wm_social_robot patch: kinematic planar drive for wheeled robots in Isaac Sim.

Skid-steer robots (Jackal: four wheels, no steering) hardly follow Twist
commands in PhysX: turning while driving has a large dead band (0.25 m/s +
0.2 rad/s gave 0.03 rad/s, measured with tools/isaac_drive_test.py), so Nav2's
controller oscillated and reported "Failed to make progress".

Here the robot base gets the commanded planar velocity (v along its heading,
yaw rate w) at every physics step, like Gazebo's planar-move plugin; vertical
motion, roll/pitch and collisions stay physical (the robot still stops at
walls). The wheels get a frictionless material (combine mode min) and keep
spinning from the differential-drive graph, for the visuals and joint states.
A command older than 0.5 s of simulated time counts as zero.

Enabled by default; ARENA_ISAAC_DRIVE=wheels keeps pure wheel physics.
"""
import math

import carb
import numpy as np
import rclpy
import rclpy.executors
from geometry_msgs.msg import Twist
from omni.isaac.core import World
from omni.isaac.core.articulations import Articulation
from omni.usd import get_context
from pxr import PhysxSchema, Usd, UsdPhysics, UsdShade

CMD_TIMEOUT = 0.5  # [s] simulated time

_drives = {}


def _frictionless_wheels(prim_path: str) -> int:
    stage = get_context().get_stage()
    mat_path = f"{prim_path}/wm_frictionless_wheels"
    UsdShade.Material.Define(stage, mat_path)
    mat_prim = stage.GetPrimAtPath(mat_path)
    m = UsdPhysics.MaterialAPI.Apply(mat_prim)
    m.CreateStaticFrictionAttr(0.0)
    m.CreateDynamicFrictionAttr(0.0)
    PhysxSchema.PhysxMaterialAPI.Apply(mat_prim).CreateFrictionCombineModeAttr().Set("min")
    n = 0
    for p in Usd.PrimRange(stage.GetPrimAtPath(prim_path), Usd.TraverseInstanceProxies()):
        if "wheel" in str(p.GetPath()) and p.HasAPI(UsdPhysics.CollisionAPI) and not p.IsInstanceProxy():
            UsdShade.MaterialBindingAPI.Apply(p).Bind(UsdShade.Material(mat_prim),
                                                       UsdShade.Tokens.weakerThanDescendants, "physics")
            n += 1
    return n


class KinematicDrive:
    def __init__(self, prim_path: str, cmd_vel_topic: str, max_linear: float, max_angular: float):
        self.prim_path = prim_path
        self.max_linear = abs(max_linear) or 2.0
        self.max_angular = abs(max_angular) or 4.0
        self.cmd = (0.0, 0.0)
        self.age = 1e9
        self.art = None
        name = prim_path.strip("/").replace("/", "_")
        self.node = rclpy.create_node(f"wm_kinematic_drive_{name}")
        self.node.create_subscription(Twist, cmd_vel_topic, self._on_cmd, 10)
        # own executor: the global one is spun by run_isaacsim's main loop
        self.executor = rclpy.executors.SingleThreadedExecutor()
        self.executor.add_node(self.node)
        wheels = _frictionless_wheels(prim_path)
        World.instance().add_physics_callback(f"wm_kinematic_drive_{name}", self._step)
        carb.log_warn(f"[wm] kinematic drive for {prim_path} on {cmd_vel_topic} "
                      f"({wheels} frictionless wheel colliders)")

    def _on_cmd(self, msg: Twist):
        self.cmd = (float(np.clip(msg.linear.x, -self.max_linear, self.max_linear)),
                    float(np.clip(msg.angular.z, -self.max_angular, self.max_angular)))
        self.age = 0.0

    def _step(self, step_size: float):
        self.executor.spin_once(timeout_sec=0.0)
        self.age += step_size
        v, w = self.cmd if self.age <= CMD_TIMEOUT else (0.0, 0.0)
        try:
            if self.art is None:
                if not get_context().get_stage().GetPrimAtPath(self.prim_path).IsValid():
                    return
                self.art = Articulation(self.prim_path)
                self.art.initialize()
            _, q = self.art.get_world_pose()  # w, x, y, z
            yaw = math.atan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2))
            lin = self.art.get_linear_velocity()
            ang = self.art.get_angular_velocity()
            self.art.set_linear_velocity(np.array([v * math.cos(yaw), v * math.sin(yaw), lin[2]]))
            self.art.set_angular_velocity(np.array([ang[0], ang[1], w]))
        except Exception as e:  # physics view not ready yet, robot deleted, ...
            self.art = None
            carb.log_verbose(f"[wm] kinematic drive {self.prim_path}: {e}")


def kinematic_drive(prim_path: str, cmd_vel_topic: str, max_linear: float, max_angular: float):
    if prim_path in _drives:
        return _drives[prim_path]
    _drives[prim_path] = KinematicDrive(prim_path, cmd_vel_topic, max_linear, max_angular)
    return _drives[prim_path]
