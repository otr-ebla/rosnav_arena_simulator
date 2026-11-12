import carb
import omni.anim.navigation.core as nav
from isaac_utils.utils.path import pedestrian_path
from pedestrian.simulator.logic.people.person import Person
from pedestrian.simulator.logic.people_manager import PeopleManager
from rclpy.qos import QoSProfile

from isaacsim_msgs.msg import NavPed
from isaacsim_msgs.srv import MovePed

from .utils import safe

profile = QoSProfile(depth=2000)


@safe()
def move_pedestrian(request: MovePed.Request, response: MovePed.Response):
    for nav_command in request.nav_list:
        nav_command: NavPed

        usd_path = pedestrian_path(nav_command.path)

        # /Characters/D_gazebo_actor_1/ManRoot/male_adult_police_04
        person = PeopleManager.get_people_manager().get_person(usd_path)
        assert isinstance(person, Person), f"Person not found for path: {usd_path}"
        walk_to(person, nav_command.goal_pose, nav_command.velocity)

    response.ret = True
    return response


def _snap(navmesh, point):
    """Closest navmesh point to `point` (unchanged if the query fails)."""
    try:
        out = carb.Float3(0.0, 0.0, 0.0)
        navmesh.query_closest_point(carb.Float3(*[float(v) for v in point[:3]]), out)
        if abs(out.x) + abs(out.y) + abs(out.z) > 0.0:
            return [out.x, out.y, out.z]
    except Exception as e:
        carb.log_warn(f"navmesh snap failed for {point}: {e}")
    return list(point)


def walk_to(person: Person, goal_pose, velocity):
    """Send `person` walking to `goal_pose` (navmesh path when available)."""
    start = person._state.position.tolist()
    goal = [float(v) for v in goal_pose]
    path_points = None
    navmesh = nav.acquire_interface().get_navmesh()
    if navmesh:
        # wm_social_robot patch: snap start/goal onto the navmesh first; Arena's
        # points (spawn z=0.1, goals near walls) are often just off it, and then
        # the query failed and the person walked straight through walls.
        start, goal = _snap(navmesh, start), _snap(navmesh, goal)
        navmesh_path = navmesh.query_shortest_path(start, goal)
        if navmesh_path:
            path_points = navmesh_path.get_points()
        else:
            carb.log_error(f"NavMesh could not query points {start} -> {goal}")
    # wm_social_robot patch: the navmesh baked at startup is often not available
    # in Isaac Sim 4.2 ("NavMesh not available, baking failed"); upstream then
    # silently dropped the command and the pedestrian stood still. Fall back to
    # a straight line from the current position to the goal.
    if not path_points:
        path_points = [start, goal]
    carb.log_warn(f"[wm] pedestrian {getattr(person, '_stage_prefix', '?')}: "
                  f"({start[0]:.1f}, {start[1]:.1f}) -> ({goal[0]:.1f}, {goal[1]:.1f}), "
                  f"{len(path_points)} path points{'' if navmesh else ' (no navmesh: straight line)'}")
    person.update_target_position(path_points, velocity if velocity > 0 else 1.0)


def move_ped(controller):
    service = controller.create_service(
        srv_type=MovePed,
        qos_profile=profile,
        srv_name="isaac/move_pedestrians",
        callback=move_pedestrian,
    )
    return service
