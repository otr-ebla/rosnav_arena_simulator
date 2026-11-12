import os
import arena_simulation_setup.entities.robot
from .differential import differential


class Control:
    def __init__(
        self,
        prim_path: str,
        cmd_vel_topic: str,
    ):
        self.prim_path: str = prim_path
        self.cmd_vel_topic: str = cmd_vel_topic

    def parse(self, robot_model: str) -> bool:
        """
        Gets configuration for give robot type and spawns controllers.
        Args:
            prim_path(str): Path to target prim.
            robot_model(str): The name of the robot model.
            cmd_vel_topic(str): The ROS2 topic for controlling the robot.
        Returns:
            bool: True if the graph was created successfully, False otherwise.
        """
        robot = arena_simulation_setup.entities.robot.Robot(robot_model)

        for controller_name, config in robot.control['controller_manager']['ros__parameters'].items():
            if isinstance(config, dict) and config.get('type') == 'diff_drive_controller/DiffDriveController':
                if not self._parse_differential(controller_name, robot.control[controller_name]['ros__parameters']):
                    return False

        return True

    def _parse_differential(
        self,
        controller_name: str,
        diff_drive_config: dict,
    ):
        # wm_social_robot patch: upstream swapped min/max (the controller got
        # maxAngularSpeed = angular.z.min_velocity = -4 and the robot did not
        # turn), and ignored the skid-steer wheel_separation_multiplier.
        wheel_distance = diff_drive_config['wheel_separation'] * diff_drive_config.get('wheel_separation_multiplier', 1.0)
        wheel_radius = diff_drive_config['wheel_radius']
        max_linear_speed = abs(diff_drive_config['linear.x.max_velocity'])
        min_linear_speed = diff_drive_config['linear.x.min_velocity']
        max_angular_speed = abs(diff_drive_config['angular.z.max_velocity'])
        min_angular_speed = diff_drive_config['angular.z.min_velocity']

        left_wheels = diff_drive_config['left_wheel_names']
        right_wheels = diff_drive_config['right_wheel_names']
        # wm_social_robot patch: skid-steer robots (several wheels per side, e.g.
        # Jackal) barely turn in Isaac through wheel friction (measured with
        # tools/isaac_drive_test.py: 0.25 m/s + 0.5 rad/s -> 0.04 rad/s). Default:
        # kinematic planar drive of the base (see kinematic.py), the wheel graph
        # below then only spins the wheels. ARENA_ISAAC_DRIVE=wheels: pure wheel
        # physics, with the separation scaled by ARENA_ISAAC_SKID_FACTOR (1.85
        # gives in-place turns at the commanded rate, arcs stay poor).
        drive = os.environ.get('ARENA_ISAAC_DRIVE', 'kinematic')
        if drive == 'kinematic':
            from .kinematic import kinematic_drive
            kinematic_drive(self.prim_path, self.cmd_vel_topic, max_linear_speed, max_angular_speed)
        elif len(left_wheels) > 1:
            wheel_distance *= float(os.environ.get('ARENA_ISAAC_SKID_FACTOR', '1.85'))

        for i, (left_wheel, right_wheel) in enumerate(zip(left_wheels, right_wheels)):
            if not differential(
                graph_path=os.path.join(self.prim_path, f'{controller_name}_{i}'),
                prim_path=self.prim_path,
                cmd_vel_topic=self.cmd_vel_topic,
                joint_names=[left_wheel, right_wheel],
                wheel_distance=wheel_distance,
                wheel_radius=wheel_radius,
                max_linear_speed=max_linear_speed,
                min_linear_speed=min_linear_speed,
                max_angular_speed=max_angular_speed,
                min_angular_speed=min_angular_speed,
            ):
                return False
        return True


__all__ = ['Control']
