
# fmt: off
# Use the isaacsim to import SimulationApp
from isaacsim import SimulationApp


# Setting the config for simulation and make an simulation.
# wm_social_robot patch: headless mode and renderer from the environment (set by
# wm_bringup: gui:=, isaac_renderer:=). Upstream: {"renderer": "Wireframe", "headless": False}
import os as _os
CONFIG = {
    "renderer": _os.environ.get("ARENA_ISAAC_RENDERER", "RayTracedLighting"),
    "headless": _os.environ.get("ARENA_ISAAC_HEADLESS", "0") == "1",
}
#import parent directory
from pathlib import Path
import sys
simulation_app = SimulationApp(CONFIG)
parent_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(parent_dir))


# Import Isaac Sim dependencies
import carb
import omni.usd
import omni.timeline
from omni.isaac.core.world import World
from omni.isaac.core.utils import prims
from omni.isaac.core import SimulationContext
from pxr import Sdf, Gf, UsdLux
import yaml
from omni.isaac.core.utils import extensions, stage
from isaac_utils.utils.assets import get_assets_root_path_safe

from omni.isaac.core.utils.prims import set_prim_attribute_value
from omni.importer.urdf import _urdf
import omni.kit.commands as commands
from omni.isaac.core.utils.rotations import euler_angles_to_quat
from omni.isaac.core.utils.stage import get_current_stage, open_stage
import random

EXTENSIONS_PEOPLE = [
    'omni.anim.people', 
    'omni.anim.navigation.bundle', 
    'omni.anim.timeline',
    'omni.anim.graph.bundle', 
    'omni.anim.graph.core', 
    'omni.anim.graph.ui',
    'omni.anim.retarget.bundle', 
    'omni.anim.retarget.core',
    'omni.anim.retarget.ui', 
    'omni.kit.scripting',
    'omni.graph.nodes',
    'omni.anim.curve.core',
    'omni.anim.navigation.core'
]

for ext_people in EXTENSIONS_PEOPLE:
    extensions.enable_extension(ext_people)

# Update the simulation app with the new extensions
simulation_app.update()

# -------------------------------------------------------------------------------------------------
# These lines are needed to restart the USD stage and make sure that the people extension is loaded
# -------------------------------------------------------------------------------------------------
omni.usd.get_context().new_stage()

extensions.disable_extension("omni.isaac.ros_bridge")
extensions.enable_extension("omni.isaac.ros2_bridge")

import rclpy
import numpy as np

#imprt navmesh gen
import omni.anim.navigation.core as nav

#Import world generation dependencies
import omni.anim.graph.core as ag
import omni.replicator.core as rep
import omni.syntheticdata._syntheticdata as sd

from isaacsim_msgs.srv import ImportUsd, ImportYaml
from isaacsim_msgs.srv import Pedestrian
from pedestrian.simulator.logic.people_manager import PeopleManager

#Import robot models
from isaac_utils.robot_graphs import assign_robot_model

#Import services
from isaac_utils.services import spawn_wall
from isaac_utils.services import move_prim
from isaac_utils.services import get_prim_attr
from isaac_utils.services import delete_prim
from isaac_utils.services import convert_urdf_to_usd
from isaac_utils.services import import_obstacle
from isaac_utils.services import spawn_ped
from isaac_utils.services import move_ped
from isaac_utils.services import delete_all_characters

#Import sensors
from isaac_utils.sensors import imu_setup,publish_imu, contact_sensor_setup, publish_contact_sensor_info, camera_set_up,publish_camera_tf,publish_depth,publish_camera_info,publish_pointcloud_from_depth,publish_rgb, lidar_setup,publish_lidar 

# other imports
from isaac_utils.utils import geom

from isaac_utils.graphs.time import PublishTime

import random

# fmt: on
# ======================================Base======================================
# Setting up world and enable ros2_bridge extentions.
# BACKGROUND_STAGE_PATH = "/background"
# BACKGROUND_USD_PATH = "/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd"
plane_material_paths = [
                'https://omniverse-content-production.s3.us-west-2.amazonaws.com/Materials/2023_1/Base/Wood/Walnut_Planks.mdl',
                # 'https://omniverse-content-production.s3.us-west-2.amazonaws.com/Materials/2023_1/vMaterials_2/Ceramic/Ceramic_Tiles_Glazed_Diamond.mdl',
                # 'https://omniverse-content-production.s3.us-west-2.amazonaws.com/Materials/2023_1/vMaterials_2/Ceramic/Ceramic_Tiles_Glazed_Diamond.mdl'
                ]
# wm_social_robot patch: physics at 60 Hz, but render (RTX lidar, cameras,
# people animation, ROS publishers) only every ARENA_ISAAC_RENDER_HZ: rendering
# is the bottleneck (60 RTX frames per simulated second gave ~0.25x real time).
_RENDER_HZ = float(_os.environ.get("ARENA_ISAAC_RENDER_HZ", "60"))
world = World(physics_dt=1.0 / 60.0, rendering_dt=1.0 / _RENDER_HZ)
# wm_social_robot patch: optional full environment USD (e.g. NVIDIA's hospital),
# set by wm_bringup from worlds/<world>/isaac.yaml. It replaces the ground plane
# (its own floor has colliders) and must be on the stage before the navmesh
# volume is created below, so the volume and the people navmesh cover it.
_ENV_USD = _os.environ.get("ARENA_ISAAC_ENV_USD", "")
_stage = omni.usd.get_context().get_stage()
if _ENV_USD:
    if "://" not in _ENV_USD and not _ENV_USD.startswith("/"):
        _ENV_USD = f"{get_assets_root_path_safe()}/Isaac/Environments/{_ENV_USD}"
    _env_prim = prims.create_prim("/World/Environment", "Xform", usd_path=_ENV_USD,
                                  position=np.array([0.0, 0.0, -float(_os.environ.get("ARENA_ISAAC_ENV_FLOOR_Z", "0"))]))
    for _ in range(30):
        simulation_app.update()
    carb.log_warn(f"[wm] environment {_ENV_USD} loaded: {bool(_env_prim and _env_prim.IsValid())}")
    # hide ceilings/roofs (ARENA_ISAAC_ENV_HIDE, comma separated name parts): the
    # scene is lit by its dome light, which the ceiling blocks (interior is dark)
    _hide = [s for s in _os.environ.get("ARENA_ISAAC_ENV_HIDE", "").split(",") if s]
    if _hide:
        from pxr import UsdGeom as _UsdGeom, UsdPhysics as _UsdPhysics, Usd as _Usd
        _n = 0
        for _p in _stage.Traverse():
            if _p.GetPath().HasPrefix("/World/Environment") and any(s in _p.GetName() for s in _hide):
                _UsdGeom.Imageable(_p).MakeInvisible()
                _n += 1
                # no collisions either (the follow camera's raycast and nothing
                # else reaches the ceiling); instance proxies cannot be edited
                for _c in _Usd.PrimRange(_p, _Usd.TraverseInstanceProxies()):
                    if _c.HasAPI(_UsdPhysics.CollisionAPI) and not _c.IsInstanceProxy():
                        _UsdPhysics.CollisionAPI(_c).GetCollisionEnabledAttr().Set(False)
        carb.log_warn(f"[wm] hid {_n} environment prims matching {_hide}")
else:
    world.scene.add_ground_plane(size=100, z_position=0.0)
plane_mdl_path = random.choice(plane_material_paths)
plane_mtl_name = plane_mdl_path.split('/')[-1][:-4]
plane_mtl_path = "/World/Looks/PlaneMaterial"
plane_mtl = _stage.GetPrimAtPath(plane_mtl_path)
if not _ENV_USD and not (plane_mtl and plane_mtl.IsValid()):
    create_res = omni.kit.commands.execute('CreateMdlMaterialPrimCommand',
                                                mtl_url=plane_mdl_path,
                                                mtl_name=plane_mtl_name,
                                                mtl_path=plane_mtl_path)

    bind_res = omni.kit.commands.execute('BindMaterialCommand',
                                            prim_path="/World/groundPlane",
                                            material_path=plane_mtl_path)
simulation_app.update()  # update the simulation once for update ros2_bridge.
simulation_context = SimulationContext(stage_units_in_meters=1.0)  # currently we use 1m for simulation.
light_1 = prims.create_prim(
    "/World/Light_1",
    "DomeLight",
    position=np.array([1.0, 1.0, 1.0]),
    attributes={
        "inputs:texture:format": "latlong",
        "inputs:intensity": 1000.0,
        "inputs:color": (1.0, 1.0, 1.0)
    }
)
assets_root_path = get_assets_root_path_safe()


def _set_lights(lights):
    """wm_social_robot patch: {prim path: intensity}, e.g. to dim an environment's
    own dome light (ARENA_ISAAC_ENV_LIGHTS, JSON; set from worlds/<world>/isaac.yaml)."""
    st = omni.usd.get_context().get_stage()
    for path, value in (lights or {}).items():
        attr = st.GetPrimAtPath(path).GetAttribute("inputs:intensity")
        if attr:
            attr.Set(float(value))
        carb.log_warn(f"[wm] light {path} intensity={value} ({'ok' if attr else 'not found'})")


if _os.environ.get("ARENA_ISAAC_ENV_LIGHTS"):
    import json as _json
    _set_lights(_json.loads(_os.environ["ARENA_ISAAC_ENV_LIGHTS"]))

# Navmesh config and baking
simulation_app.update()
stage = omni.usd.get_context().get_stage()

omni.kit.commands.execute("CreateNavMeshVolumeCommand",
                          parent_prim_path=Sdf.Path("/World"),
                          layer=stage.GetRootLayer()
                          )
simulation_app.update()

omni.kit.commands.execute(
    'ChangeSetting',
    path='/exts/omni.anim.navigation.core/navMesh/config/agentRadius',
    value=35.0)

omni.kit.commands.execute(
    'ChangeSetting',
    path='/exts/omni.anim.people/navigation_settings/dynamic_avoidance_enabled',
    value=True)
omni.kit.commands.execute(
    'ChangeSetting',
    path='/exts/omni.anim.people/navigation_settings/navmesh_enabled',
    value=True)

inav = nav.acquire_interface()
x = inav.start_navmesh_baking()
simulation_app.update()

# stage.add_reference_to_stage(assets_root_path, BACKGROUND_USD_PATH)

# Setting up URDF importer.
status, import_config = commands.execute("URDFCreateImportConfig")
import_config.merge_fixed_joints = False
import_config.convex_decomp = False
import_config.import_inertia_tensor = False
import_config.self_collision = False
import_config.fix_base = False
import_config.distance_scale = 1
import_config.make_default_prim = True
import_config.default_drive_type = (_urdf.UrdfJointTargetType.JOINT_DRIVE_VELOCITY)
extension_path = _urdf.ImportConfig()

# list devices.
robots = []
environments = []
robot_positions = []
robot_orientation = []
environment_positions = []
environment_orientation = []

# ================================================================================
# ============================read yaml file===============================


def read_yaml_config(yaml_path):
    with open(yaml_path, 'r') as file:
        config = yaml.safe_load(file)
    return config


def yaml_importer(request, response):
    # Read configuration from YAML file
    yaml_path = request.yaml_path
    config = read_yaml_config(yaml_path)

    # Extract parameters
    name = config['robot']['name']
    model = config['robot']['model']
    usd_path = config['robot']['usd_path']
    prim_path = config['robot']['prim_path']
    control = config['robot']['control']
    position = config['robot']['position']
    orientation = config['robot']['orientation']

    # Prepare the request for ImportUsd service
    yaml_request = ImportUsd.Request()
    yaml_request.name = name
    yaml_request.model = model
    yaml_request.usd_path = usd_path
    yaml_request.prim_path = prim_path
    yaml_request.control = control
    yaml_request.position = np.array(position, dtype=np.float32)
    yaml_request.orientation = np.array(orientation, dtype=np.float32)

    usd_response = usd_importer(yaml_request, response)

    # Pass the response back (optional, depending on how you want to structure your service)
    response.ret = usd_response.ret
    return response

# ============================usd importer service================================
# Usd importer (service) -> bool.


def usd_importer(request, response):
    name = request.name
    model = request.model
    usd_path = request.usd_path
    prim_path = request.prim_path + "/" + name

    model_prim = prims.create_prim(
        prim_path=f"/World/{name}",
        position=np.array(geom.Translation.parse(request.pose.position).tuple()),
        orientation=np.array(geom.Rotation.parse(request.pose.orientation).quat()),
        usd_path=usd_path,
        semantic_label=model,
    )

    response.ret = True
    if not request.control:
        environments.append(prim_path)
        return response
    camera_prim_path = prim_path + "/camera_link"
    camera = camera_set_up(camera_prim_path, "Camera")
    camera.initialize()
    publish_camera_info(name, camera, 20)
    publish_depth(name, camera, 20)
    publish_rgb(name, camera, 20)
    publish_pointcloud_from_depth(name, camera, 20)
    publish_camera_tf(name, prim_path, camera)

    lidar_prim_path = prim_path + "/base_scan"
    lidar = lidar_setup(lidar_prim_path, "Lidar")
    publish_lidar(name, prim_path, lidar)

    links = ["wheel_left_link", "wheel_right_link"]
    for link in links:
        imu_prim_path = prim_path + "/" + link + "/" + "IMU"
        contact_prim_path = prim_path + "/" + link + "/" + "ContactSensor"
        imu = imu_setup(imu_prim_path)
        contact_sensor = contact_sensor_setup(contact_prim_path)
        publish_contact_sensor_info(name, prim_path, link, contact_sensor)
        publish_imu(name, prim_path, link, imu)

    robots.append(prim_path)

    model = assign_robot_model(name, prim_path, model)

    # publish joint_states and control
    model.control_and_publish_joint_states()
    model.publish_odom_and_tf()

    world.reset()
    return response

# Usd importer service callback.


def import_yaml(controller):
    service = controller.create_service(
        srv_type=ImportYaml,
        srv_name='isaac/import_yaml',
        callback=yaml_importer
    )
    return service


def import_usd(controller):
    service = controller.create_service(
        srv_type=ImportUsd,
        srv_name='isaac/import_usd',
        callback=usd_importer
    )
    return service


def time_publisher(controller):
    PublishTime('/World/publish_time')


# =================================================================================

# ===================================controller====================================
# create controller node for isaacsim.


def create_controller(time=120):
    # init controller.
    controller = rclpy.create_node('controller')
    # init services.
    time_publisher(controller)
    import_usd(controller)
    convert_urdf_to_usd(controller)
    get_prim_attr(controller)
    move_prim(controller)
    delete_prim(controller)
    spawn_wall(controller)
    import_yaml(controller)
    import_obstacle(controller)
    spawn_ped(controller)
    move_ped(controller)
    delete_all_characters(controller)
    
    return controller

# update the simulation.


_CAMERA = {"mode": _os.environ.get("ARENA_ISAAC_CAMERA", "free"), "eye": None, "tick": 0, "log": 0,
           "back": 3.5, "height": 2.2, "ahead": 2.0, "mtime": None}
_FOLLOW_PRIM = _os.environ.get("ARENA_ISAAC_FOLLOW_PRIM", "/World/jackal/base_link")
# optional live tuning: yaml with back/height/ahead [m], mode, follow (prim path),
# look ([eye xyz, target xyz]), dome / lights (intensities), exposure
_CAMERA_FILE = "/tmp/arena_isaac_camera.yaml"


def _camera_tuning():
    try:
        mt = _os.path.getmtime(_CAMERA_FILE)
    except OSError:
        return
    if mt == _CAMERA["mtime"]:
        return
    _CAMERA["mtime"] = mt
    try:
        with open(_CAMERA_FILE) as f:
            cfg = yaml.safe_load(f) or {}
        for k in ("back", "height", "ahead"):
            if k in cfg:
                _CAMERA[k] = float(cfg[k])
        if cfg.get("mode") in ("follow", "free"):
            _CAMERA["mode"] = cfg["mode"]
        if cfg.get("follow"):  # prim path to follow instead of the robot, e.g. a pedestrian
            _CAMERA["prim"] = str(cfg["follow"])
        if cfg.get("look"):  # [eye x, y, z, target x, y, z]: fixed view (switches to free mode)
            from omni.isaac.core.utils.viewports import set_camera_view
            e = [float(v) for v in cfg["look"]]
            _CAMERA["mode"] = "free"
            set_camera_view(eye=np.array(e[:3]), target=np.array(e[3:6]), camera_prim_path="/OmniverseKit_Persp")
        if "dome" in cfg:
            _set_lights({"/World/Light_1": cfg["dome"]})
        _set_lights(cfg.get("lights"))
        if "exposure" in cfg:  # RTX tonemapper film ISO (default 100)
            import carb.settings as _cs
            _cs.get_settings().set("/rtx/post/tonemap/filmIso", float(cfg["exposure"]))
        carb.log_warn(f"[wm] camera tuning {cfg}")
    except Exception as e:
        carb.log_warn(f"[wm] camera tuning: {e}")


def follow_camera():
    """wm_social_robot patch: chase camera behind the robot (ARENA_ISAAC_CAMERA=follow),
    like the Arena hospital video. Also logs the robot pose every ~10 s."""
    _CAMERA["tick"] += 1
    if _CAMERA["tick"] % 30 == 0:
        _camera_tuning()
    if _CAMERA["mode"] != "follow":
        return
    if _CAMERA["tick"] % 2:
        return
    prim = omni.usd.get_context().get_stage().GetPrimAtPath(_CAMERA.get("prim") or _FOLLOW_PRIM)
    if not prim or not prim.IsValid():
        return
    try:
        from omni.isaac.core.utils.viewports import set_camera_view
        m = omni.usd.get_world_transform_matrix(prim)
        pos = np.array(m.ExtractTranslation())
        fwd = np.array(m.ExtractRotationMatrix().GetRow(0))[:2]
        up_z = float(m.ExtractRotationMatrix().GetRow(2)[2])
        n = np.linalg.norm(fwd)
        fwd = fwd / n if n > 1e-3 else np.array([1.0, 0.0])
        h = np.array([fwd[0], fwd[1], 0.0])
        eye = pos - _CAMERA["back"] * h + np.array([0.0, 0.0, _CAMERA["height"]])
        target = pos + _CAMERA["ahead"] * h + np.array([0.0, 0.0, 0.3])
        # keep the camera on the robot's side of walls: raycast robot -> camera
        try:
            from omni.physx import get_physx_scene_query_interface
            origin = pos + np.array([0.0, 0.0, 0.6])
            d = eye - origin
            dist = float(np.linalg.norm(d))
            hit = get_physx_scene_query_interface().raycast_closest(
                carb.Float3(*origin.tolist()), carb.Float3(*(d / dist).tolist()), dist)
            if hit["hit"] and float(hit["position"][2]) < 2.5 \
                    and not str(hit["rigidBody"]).startswith(_FOLLOW_PRIM.rsplit("/", 1)[0]):
                eye = origin + d / dist * max(0.3, hit["distance"] - 0.25)
        except Exception:
            pass
        if _CAMERA["eye"] is not None and np.linalg.norm(eye - _CAMERA["eye"]) < 5.0:
            eye = _CAMERA["eye"] + 0.08 * (eye - _CAMERA["eye"])
        _CAMERA["eye"] = eye
        set_camera_view(eye=eye, target=target, camera_prim_path="/OmniverseKit_Persp")
        _CAMERA["log"] += 1
        if _CAMERA["log"] % 100 == 1:
            carb.log_warn(f"[wm] robot at ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}) upright={up_z:.2f}")
    except Exception as e:  # cosmetic only
        carb.log_warn(f"[wm] follow camera: {e}")


def run():
    simulation_app.update()
    simulation_context.play()
    follow_camera()
# =================================================================================

# ======================================main=======================================


def main(arg=None):
    rclpy.init()
    controller = create_controller()
    while simulation_app.is_running():
        try:
            run()
            rclpy.spin_once(controller, timeout_sec=0.0)
        except KeyboardInterrupt:
            controller.get_logger().warn('received KeyboardInterrupt, shutting down')
            break
        except BaseException as e:
            controller.get_logger().warn(f'encountered {repr(e)}, ignoring')
            # raise
        simulation_app.update()
    controller.destroy_node()
    # rclpy.shutdown()
    return


# =================================================================================
if __name__ == "__main__":
    main()
