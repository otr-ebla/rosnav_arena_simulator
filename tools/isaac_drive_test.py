"""Isaac Sim drive test for a wheeled robot URDF (as Arena imports it).

Imports the URDF like ros2isaacsim's UrdfToUsd (velocity drives), drives it
with Isaac's DifferentialController (as Arena's control graph does) and prints
commanded vs actual linear/yaw speed. Used to tune the Jackal's skid steering.

Inside the container:
    arena_isaac_env; unset DISPLAY
    $ISAAC_PATH/python.sh tools/isaac_drive_test.py /tmp/jackal_arena.urdf \
        [--env Hospital/hospital.usd --x -11.3 --y 15.2] [--sep 0.54] [--damping D] [--friction MU]
"""
import argparse
import functools
import math

print = functools.partial(print, flush=True)  # Isaac exits without flushing stdout

ap = argparse.ArgumentParser()
ap.add_argument("urdf")
ap.add_argument("--env", default="", help="environment USD below Isaac/Environments (default: ground plane)")
ap.add_argument("--x", type=float, default=0.0)
ap.add_argument("--y", type=float, default=0.0)
ap.add_argument("--floor-z", type=float, default=0.035)
ap.add_argument("--sep", type=float, default=0.36 * 1.5, help="wheel separation given to the controller [m]")
ap.add_argument("--radius", type=float, default=0.098)
ap.add_argument("--damping", type=float, default=None, help="override wheel drive damping")
ap.add_argument("--friction", type=float, default=None, help="wheel physics material friction (static=dynamic)")
ap.add_argument("--kinematic", action="store_true",
                help="set the base's planar velocity from the command every physics step (wheels only spin)")
args = ap.parse_args()

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402
import omni.kit.commands as commands  # noqa: E402
import omni.usd  # noqa: E402
from omni.isaac.core import World  # noqa: E402
from omni.isaac.core.articulations import Articulation  # noqa: E402
from omni.isaac.core.utils import prims  # noqa: E402
from omni.isaac.nucleus import get_assets_root_path  # noqa: E402
from omni.isaac.core.utils.types import ArticulationAction  # noqa: E402
from omni.isaac.wheeled_robots.controllers import DifferentialController  # noqa: E402
from pxr import Usd, UsdPhysics, UsdShade, Sdf  # noqa: E402

world = World(physics_dt=1 / 60, rendering_dt=1 / 20, stage_units_in_meters=1.0)
if args.env:
    prims.create_prim("/World/Environment", "Xform",
                      usd_path=f"{get_assets_root_path()}/Isaac/Environments/{args.env}",
                      position=np.array([0.0, 0.0, -args.floor_z]))
else:
    world.scene.add_default_ground_plane()
for _ in range(20):
    app.update()

_, cfg = commands.execute("URDFCreateImportConfig")
cfg.set_merge_fixed_joints(False)
cfg.set_convex_decomp(False)
cfg.set_import_inertia_tensor(False)
cfg.set_make_default_prim(False)
cfg.set_distance_scale(1.0)
cfg.set_fix_base(False)
cfg.set_default_drive_type(2)
cfg.set_self_collision(False)
_, path = commands.execute("URDFParseAndImportFile", urdf_path=args.urdf, import_config=cfg, dest_path="")
commands.execute("MovePrim", path_from=path, path_to="/World/robot", keep_world_transform=True)
stage = omni.usd.get_context().get_stage()

wheels = []
for p in Usd.PrimRange(stage.GetPrimAtPath("/World/robot")):
    if "wheel" in p.GetName() and p.HasAPI(UsdPhysics.DriveAPI, "angular"):
        d = UsdPhysics.DriveAPI(p, "angular")
        if args.damping is not None:
            d.GetDampingAttr().Set(args.damping)
        wheels.append(p.GetName())
        print(f"DRIVE {p.GetName()} stiffness={d.GetStiffnessAttr().Get()} damping={d.GetDampingAttr().Get()} "
              f"maxForce={d.GetMaxForceAttr().Get()}")

if args.friction is not None:
    mat_path = "/World/WheelMaterial"
    UsdShade.Material.Define(stage, mat_path)
    m = UsdPhysics.MaterialAPI.Apply(stage.GetPrimAtPath(mat_path))
    m.CreateStaticFrictionAttr(args.friction)
    m.CreateDynamicFrictionAttr(args.friction)
    from pxr import PhysxSchema
    PhysxSchema.PhysxMaterialAPI.Apply(stage.GetPrimAtPath(mat_path)).CreateFrictionCombineModeAttr().Set("min")
    for p in Usd.PrimRange(stage.GetPrimAtPath("/World/robot"), Usd.TraverseInstanceProxies()):
        if "wheel" in str(p.GetPath()) and p.HasAPI(UsdPhysics.CollisionAPI) and not p.IsInstanceProxy():
            print("FRICTION", p.GetPath())
            UsdShade.MaterialBindingAPI.Apply(p).Bind(UsdShade.Material(stage.GetPrimAtPath(mat_path)),
                                                       UsdShade.Tokens.weakerThanDescendants, "physics")

robot = Articulation("/World/robot")
world.reset()
robot.initialize()
robot.set_world_pose(position=np.array([args.x, args.y, 0.08]))
names = robot.dof_names
print("DOFS", names)
left = [names.index(n) for n in names if "left_wheel" in n]
right = [names.index(n) for n in names if "right_wheel" in n]
ctrl = DifferentialController("diff", wheel_radius=args.radius, wheel_base=args.sep)


def pose():
    pos, q = robot.get_world_pose()
    yaw = math.atan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2))
    return np.array(pos), yaw


for _ in range(40):
    world.step(render=False)
print(f"SETUP sep={args.sep} damping={args.damping} friction={args.friction} kinematic={args.kinematic} env={args.env or 'ground'}")
for v, w in [(0.25, 0.0), (0.0, 1.0), (0.0, -1.0), (0.25, 0.5), (0.25, -0.5), (0.2, 1.0), (0.25, 0.2), (0.25, -0.2)]:
    lr = ctrl.forward(np.array([v, w])).joint_velocities
    vel = np.zeros(len(names))
    vel[left], vel[right] = lr[0], lr[1]
    p0, y0 = pose()
    steps = 120  # 2 s
    for i in range(steps):
        robot.apply_action(ArticulationAction(joint_velocities=vel))
        if args.kinematic:
            _, q = robot.get_world_pose()
            yaw = math.atan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2))
            vz = robot.get_linear_velocity()[2]
            robot.set_linear_velocity(np.array([v * math.cos(yaw), v * math.sin(yaw), vz]))
            av = robot.get_angular_velocity()
            robot.set_angular_velocity(np.array([av[0], av[1], w]))
        world.step(render=False)
        if i == 29:
            p0, y0 = pose()  # skip the first 0.5 s (acceleration)
    p1, y1 = pose()
    dt = (steps - 30) / 60
    dyaw = math.atan2(math.sin(y1 - y0), math.cos(y1 - y0))
    print(f"CMD v={v:5.2f} w={w:5.2f} -> actual v={np.linalg.norm((p1 - p0)[:2]) / dt:5.2f} "
          f"w={dyaw / dt:5.2f}  z={p1[2]:.3f}")
    vel[:] = 0
    robot.apply_action(ArticulationAction(joint_velocities=vel))
    for _ in range(60):
        world.step(render=False)
app.close()
