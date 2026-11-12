"""Headless Isaac Sim check of Arena's pedestrian characters (ros2isaacsim).

Spawns a few characters with Arena's Person class, sends them walking along a
straight line, renders frames from a fixed camera and prints their positions
and bounding boxes. Run inside the container (takes ~2-3 min):

    arena_isaac_env; unset DISPLAY
    /opt/isaac-sim/python.sh $WM_PROJECT_DIR/tools/isaac_ped_check.py [out_dir]

Output: <out_dir>/frame_XXXX.png (default /tmp/isaac_ped_check)
"""
import os
import sys

from isaacsim import SimulationApp

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/isaac_ped_check"
app = SimulationApp({"headless": True, "renderer": "RayTracedLighting", "width": 1280, "height": 720})

ROS2ISAACSIM = os.path.join(os.environ.get("ARENA_WS_DIR", os.path.expanduser("~/wm_social_robot/arena4_ws")),
                            "src/arena/isaac/ros2isaacsim")
sys.path.insert(0, ROS2ISAACSIM)

from omni.isaac.core.utils import extensions  # noqa: E402

for ext in ["omni.anim.people", "omni.anim.navigation.bundle", "omni.anim.timeline", "omni.anim.graph.bundle",
            "omni.anim.graph.core", "omni.anim.retarget.bundle", "omni.anim.retarget.core", "omni.kit.scripting",
            "omni.graph.nodes", "omni.anim.curve.core", "omni.anim.navigation.core"]:
    extensions.enable_extension(ext)
app.update()

import omni.usd  # noqa: E402

omni.usd.get_context().new_stage()
app.update()

import numpy as np  # noqa: E402
from omni.isaac.core.utils import prims  # noqa: E402
from omni.isaac.core.utils.viewports import set_camera_view  # noqa: E402
from omni.isaac.core.world import World  # noqa: E402
from omni.isaac.sensor import Camera  # noqa: E402
from PIL import Image  # noqa: E402
from pxr import Usd, UsdGeom  # noqa: E402

world = World(stage_units_in_meters=1.0)
world.scene.add_ground_plane(size=100, z_position=0.0)
prims.create_prim("/World/Light_1", "DomeLight", attributes={"inputs:intensity": 1000.0})
app.update()

from pedestrian.simulator.logic.people.person import Person  # noqa: E402

people = {
    "D_gazebo_actor_1": ("original_female_adult_business_02", [0.0, -1.0, 0.0], [5.0, -1.0, 0.0]),
    "D_gazebo_actor_2": ("original_male_adult_police_04", [5.0, 1.0, 0.0], [0.0, 1.0, 0.0]),
}
persons = {}
for name, (model, start, goal) in people.items():
    p = Person(world, f"/World/pedestrians/{name}", model, start, 0.0)
    p.update_target_position([start, goal], 1.0)
    persons[name] = p
    print(f"[check] spawned {name} model={model} skel_root={p.character_skel_root_stage_path}", flush=True)

cam = Camera(prim_path="/World/check_cam", resolution=(1280, 720))
cam.initialize()
set_camera_view(eye=np.array([2.5, -7.0, 3.0]), target=np.array([2.5, 0.0, 0.9]), camera_prim_path="/World/check_cam")

world.reset()
world.play()
os.makedirs(OUT, exist_ok=True)
stage = omni.usd.get_context().get_stage()
bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"])
for i in range(601):
    world.step(render=True)
    if i % 100 == 0:
        for name, p in persons.items():
            r = bbox.ComputeWorldBound(stage.GetPrimAtPath(f"/World/pedestrians/{name}")).ComputeAlignedRange()
            print(f"[check] step {i:4d} {name}: graph={'yes' if p.character_graph else 'no'} "
                  f"pos={np.round(p.state.position, 2).tolist()} bbox_min={np.round(list(r.GetMin()), 2).tolist()} "
                  f"bbox_max={np.round(list(r.GetMax()), 2).tolist()}", flush=True)
            bbox.Clear()
        rgba = cam.get_rgba()
        if rgba is not None and rgba.size:
            Image.fromarray(rgba[:, :, :3].astype(np.uint8)).save(f"{OUT}/frame_{i:04d}.png")
print("[check] done", flush=True)
app.close()
