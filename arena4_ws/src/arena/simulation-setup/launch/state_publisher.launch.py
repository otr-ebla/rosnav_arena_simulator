
import launch
import launch_ros.actions
from arena_bringup.substitutions import LaunchArgument, YAMLFileSubstitution
from arena_bringup.future import PythonExpression
from launch.substitutions import PathJoinSubstitution, Command

from launch_ros.substitutions import FindPackageShare
import launch.actions


def generate_launch_description():
    ss_root = FindPackageShare('arena_simulation_setup')

    namespace = LaunchArgument('namespace')
    frame = LaunchArgument('frame')
    robot = LaunchArgument("robot")

    control_yaml = YAMLFileSubstitution(
        PathJoinSubstitution([
            ss_root,
            'entities',
            'robots',
            robot.substitution,
            'control.yaml',
        ])
    )

    urdf_path = PathJoinSubstitution([
        ss_root,
        'entities',
        'robots',
        robot.substitution,
        'urdf',
        PythonExpression(['"', robot.substitution, '.urdf"']),
    ])

    urdf_content = Command(['cat ', urdf_path])

    robot_state_pub_node = launch_ros.actions.Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        parameters=[
            {'use_sim_time': True},
            {'robot_description': launch_ros.parameter_descriptions.ParameterValue(urdf_content, value_type=str)},
            {'frame_prefix': launch_ros.parameter_descriptions.ParameterValue(frame.substitution, value_type=str)},
        ],
    )

    joint_state_pub_node = launch_ros.actions.Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        output='screen',
        parameters=[
            {'use_sim_time': True},
            {'robot_description': launch_ros.parameter_descriptions.ParameterValue(urdf_content, value_type=str)},
        ],
        remappings=[('/joint_states', '/joint_states')]
    )

    ld = launch.LaunchDescription([
        frame,
        robot,
        namespace,
        robot_state_pub_node,
        joint_state_pub_node,
    ])
    return ld


if __name__ == '__main__':
    generate_launch_description()
