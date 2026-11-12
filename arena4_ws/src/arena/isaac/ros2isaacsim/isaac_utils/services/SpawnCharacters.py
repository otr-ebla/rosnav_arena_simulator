import os
from isaac_utils.utils.path import pedestrian_path
from isaac_utils.utils.prim import ensure_path
from omni.isaac.core import World
from pedestrian.simulator.logic.people.person import Person
from rclpy.qos import QoSProfile

from isaacsim_msgs.srv import Pedestrian

from .utils import safe

profile = QoSProfile(depth=2000)

_SAFE_CHARACTERS = [
    "original_female_adult_business_02", "original_female_adult_medical_01",
    "original_female_adult_police_01", "original_female_adult_police_02",
    "original_female_adult_police_03", "original_male_adult_construction_01",
    "original_male_adult_construction_02", "original_male_adult_construction_03",
    "original_male_adult_construction_05", "original_male_adult_medical_01",
    "original_male_adult_police_04",
]


@safe()
def pedestrian_spawn(request, response):
    # Get service attributes
    world = World.instance()
    people = request.people

    for person in people:
        # wm_social_robot patch: the bare 'biped_demo' rig (and the non-'original_'
        # variants) crash omni.anim.graph (segfault in ag.get_character), never spawn them.
        if not person.character_name.startswith("original_"):
            import random
            import carb
            safe_name = random.choice(_SAFE_CHARACTERS)
            carb.log_warn(f"pedestrian {person.stage_prefix}: character '{person.character_name}' "
                          f"is not supported, using '{safe_name}'")
            person.character_name = safe_name
        usd_path = pedestrian_path(person.stage_prefix)
        ensure_path(os.path.dirname(usd_path))
        if not person.controller_stats:
            p = Person(world, usd_path, person.character_name, person.initial_pose, person.orientation)
            # inav = nav.acquire_interface()
            # navmesh = inav.get_navmesh()
            # if navmesh:
            #     navmesh_path = navmesh.query_shortest_path(person.initial_pose, person.goal_pose)
            #     if navmesh_path:
            #         path_points = navmesh_path.get_points()
            #         p.update_target_position(path_points, person.velocity)
            #     else:
            #         carb.log_error(f"NavMesh could not query points")
        else:
            p = Person(world, usd_path, person.character_name, person.initial_pose, person.orientation, person.controller_name)
        # wm_social_robot patch: Arena's IsaacHumanSimulator (human:=isaac)
        # passes the goal here and never calls isaac/move_pedestrians, so the
        # goal was ignored and every pedestrian stood still. Start walking now.
        goal = list(person.goal_pose)
        if any(abs(v) > 1e-6 for v in goal[:2]):
            from .MoveCharacters import walk_to
            walk_to(p, [goal[0], goal[1], 0.0], person.velocity)

    _frame_first_pedestrian(people)
    response.ret = True
    return response


_camera_aimed = False


def _frame_first_pedestrian(people):
    """wm_social_robot patch: point the GUI viewport at the first pedestrian
    (once, the camera can be moved freely afterwards). The default view is far
    from where Arena places the people, so they were not visible on start."""
    global _camera_aimed
    if _camera_aimed or not people or os.environ.get("ARENA_ISAAC_HEADLESS", "0") == "1":
        return
    _camera_aimed = True
    try:
        import numpy as np
        from omni.isaac.core.utils.viewports import set_camera_view
        x, y = float(people[0].initial_pose[0]), float(people[0].initial_pose[1])
        set_camera_view(eye=np.array([x - 7.0, y - 7.0, 5.0]), target=np.array([x, y, 0.8]),
                        camera_prim_path="/OmniverseKit_Persp")
    except Exception as e:  # cosmetic only, never break spawning
        import carb
        carb.log_warn(f"could not aim viewport at pedestrians: {e}")


def spawn_ped(controller):
    service = controller.create_service(
        srv_type=Pedestrian,
        qos_profile=profile,
        srv_name='isaac/spawn_pedestrian',
        callback=pedestrian_spawn
    )
    return service
