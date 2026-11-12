"""Single entry point for Arena-Rosnav simulations.

    ros2 launch wm_bringup sim.launch.py sim:=gazebo world:=hospital peds:=10 render:=ogre2 gui:=true

Wraps arena_bringup/launch/arena.launch.py: translates a few user-level
arguments into Arena's launch arguments and into a parameter override file
for the task generator. Any other Arena argument (local_planner, tm_robots,
env_n, ...) can be given as well and is passed through unchanged.
For GUI windows on this machine run it through `vglrun -d egl` (the
`arena_sim` shell function does that automatically).
"""

import json
import os
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            LogInfo, OpaqueFunction, SetEnvironmentVariable)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

TRUE = ('1', 'true', 'yes', 'on')


def _listdir(path):
    try:
        return sorted(d for d in os.listdir(path)
                      if os.path.isdir(os.path.join(path, d)) and not d.startswith('.'))
    except FileNotFoundError:
        return []


def _range(text, name):
    """'8' -> [8, 8]; '5-10' or '5,10' -> [5, 10]."""
    parts = text.replace(',', '-').split('-')
    try:
        values = [int(p) for p in parts if p.strip() != '']
    except ValueError:
        raise RuntimeError(f"{name}:={text!r}: expected N or MIN-MAX")
    if len(values) == 1:
        values *= 2
    if len(values) != 2 or min(values) < 0:
        raise RuntimeError(f"{name}:={text!r}: expected N or MIN-MAX")
    return sorted(values)


def _setup(context):
    cfg = {k: LaunchConfiguration(k).perform(context) for k in (
        'sim', 'world', 'robot', 'peds', 'ped_model', 'obstacles',
        'gui', 'rviz', 'render', 'isaac_renderer', 'seed', 'ped_rate', 'obstacle_models', 'human',
        'camera', 'isaac_hz')}
    if cfg['camera'] not in ('follow', 'free'):
        raise RuntimeError("camera:= must be follow or free")

    ss = get_package_share_directory('arena_simulation_setup')
    worlds = _listdir(os.path.join(ss, 'worlds'))
    robots = _listdir(os.path.join(ss, 'entities', 'robots'))
    peds_models = _listdir(os.path.join(ss, 'entities', 'obstacles', 'dynamic'))
    if cfg['world'] not in worlds:
        raise RuntimeError(f"world:={cfg['world']} unknown; available: {', '.join(worlds)}")
    if cfg['robot'] not in robots:
        raise RuntimeError(f"robot:={cfg['robot']} unknown; available: {', '.join(robots)}")
    models = [m for m in cfg['ped_model'].split(',') if m]
    for m in models:
        if m not in peds_models:
            raise RuntimeError(f"ped_model:={m} unknown; available: {', '.join(peds_models)}")
    if cfg['sim'] not in ('gazebo', 'isaac', 'dummy'):
        raise RuntimeError("sim:= must be gazebo, isaac or dummy")
    if cfg['render'] not in ('ogre', 'ogre2'):
        raise RuntimeError("render:= must be ogre or ogre2")

    gui = cfg['gui'].lower() in TRUE
    rviz = cfg['rviz'].lower() in TRUE
    # Arena: 0 = simulator GUI + RViz, 1 = RViz only, 2 = nothing
    headless = '0' if gui else ('1' if rviz else '2')

    # Isaac-only worlds (worlds/<world>/isaac.yaml): Isaac loads a full
    # environment USD (e.g. NVIDIA's hospital) instead of walls from the map
    isaac_env = {}
    isaac_yaml = os.path.join(ss, 'worlds', cfg['world'], 'isaac.yaml')
    if os.path.isfile(isaac_yaml):
        with open(isaac_yaml) as f:
            isaac_env = yaml.safe_load(f) or {}
        if cfg['sim'] != 'isaac':
            raise RuntimeError(f"world:={cfg['world']} is an Isaac Sim scene ({isaac_env.get('usd')}); "
                               f"use sim:=isaac")
    # static obstacles: default 3-5, none in full Isaac scenes (they have their own furniture)
    if not cfg['obstacles']:
        cfg['obstacles'] = '0' if isaac_env else '3-5'

    # parameter overrides for the task generator (random obstacle task)
    random_task = {
        'dynamic': {'n': _range(cfg['peds'], 'peds')},
        'static': {'n': _range(cfg['obstacles'], 'obstacles')},
        'seed': int(cfg['seed']),
    }
    if models:
        random_task['dynamic']['models'] = models

    # static obstacle models. Isaac Sim needs a USD version of each model;
    # only some Arena models ship one (others would need Arena's sdf2usd
    # converter, which is not installed), so for sim:=isaac the default is the
    # set of models that have entities/obstacles/static/<model>/usd/<model>.usd.
    static_dir = os.path.join(ss, 'entities', 'obstacles', 'static')
    static_all = _listdir(static_dir)
    static_usd = [m for m in static_all
                  if os.path.isfile(os.path.join(static_dir, m, 'usd', f'{m}.usd'))]
    obstacle_models = [m for m in cfg['obstacle_models'].split(',') if m]
    for m in obstacle_models:
        if m not in static_all:
            raise RuntimeError(f"obstacle_models: {m} unknown; available: {', '.join(static_all)}")
        if cfg['sim'] == 'isaac' and m not in static_usd:
            raise RuntimeError(f"obstacle_models: {m} has no USD model (needed by Isaac); "
                               f"usable with Isaac: {', '.join(static_usd)}")
    if not obstacle_models and cfg['sim'] == 'isaac':
        obstacle_models = static_usd
    if obstacle_models:
        # separate list objects: PyYAML would otherwise write an alias,
        # which the ROS 2 parameter parser rejects
        random_task['static']['models'] = list(obstacle_models)
        random_task['interactive'] = {'models': list(obstacle_models)}
    overrides = {'/**': {'ros__parameters': {'task': {'random': random_task}}}}
    fd, params_file = tempfile.mkstemp(prefix='wm_sim_', suffix='.yaml')
    with os.fdopen(fd, 'w') as f:
        yaml.safe_dump(overrides, f)

    # pedestrian simulator: HuNav (social force + behaviour trees) drives the
    # Gazebo actors; in Isaac Sim, Arena's isaac human simulator spawns NVIDIA's
    # animated characters (Arena's own default for isaac is hunav, whose
    # non-Gazebo path spawns only one agent)
    human = cfg['human'] or {'gazebo': 'hunav', 'isaac': 'isaac'}.get(cfg['sim'], 'dummy')

    arena_args = {
        'human': human,
        'sim': cfg['sim'],
        'world': cfg['world'],
        'robot': cfg['robot'],
        'headless': headless,
        'extra_parameter_file': params_file,
        # Gazebo (patched gazebo.launch.py)
        'render_engine': cfg['render'],
        # server-only + ogre2: render sensors on the GPU through EGL, no display needed
        'headless_rendering': 'true' if (not gui and cfg['render'] == 'ogre2') else 'false',
    }

    return [
        LogInfo(msg=f"[wm_sim] sim={cfg['sim']} human={human} world={cfg['world']} robot={cfg['robot']} "
                    f"peds={random_task['dynamic']['n']} obstacles={random_task['static']['n']} "
                    f"render={cfg['render'] if cfg['sim'] == 'gazebo' else cfg['isaac_renderer']} "
                    f"ped_rate={cfg['ped_rate']} gui={gui} rviz={rviz or gui} overrides={params_file}"),
        # Isaac Sim (patched ros2isaacsim/run_isaacsim.py)
        # HuNav pedestrian update rate in the Gazebo plugin (patched hunav.py)
        SetEnvironmentVariable('ARENA_HUNAV_UPDATE_RATE', cfg['ped_rate']),
        SetEnvironmentVariable('ARENA_ISAAC_HEADLESS', '0' if gui else '1'),
        SetEnvironmentVariable('ARENA_ISAAC_RENDERER', cfg['isaac_renderer']),
        SetEnvironmentVariable('ARENA_ISAAC_CAMERA', cfg['camera']),
        SetEnvironmentVariable('ARENA_ISAAC_RENDER_HZ', cfg['isaac_hz']),
        SetEnvironmentVariable('ARENA_ISAAC_FOLLOW_PRIM', f"/World/{cfg['robot']}/base_link"),
        SetEnvironmentVariable('ARENA_ISAAC_ENV_USD', str(isaac_env.get('usd', ''))),
        SetEnvironmentVariable('ARENA_ISAAC_ENV_FLOOR_Z', str(isaac_env.get('floor_z', 0.0))),
        SetEnvironmentVariable('ARENA_ISAAC_ENV_HIDE', ','.join(isaac_env.get('hide', []) or [])),
        SetEnvironmentVariable('ARENA_ISAAC_ENV_LIGHTS', json.dumps(isaac_env.get('lights') or {})),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(
                get_package_share_directory('arena_bringup'), 'launch', 'arena.launch.py')),
            launch_arguments=arena_args.items(),
        ),
    ]


def generate_launch_description():
    args = [
        ('sim', 'gazebo', 'simulator: gazebo | isaac | dummy'),
        ('world', 'map_empty', 'world directory in arena_simulation_setup/worlds '
                               '(factory, generated, hospital, house17, ignc, map_empty, small_warehouse; '
                               'Isaac only: isaac_hospital = NVIDIA hospital scene)'),
        ('robot', 'jackal', 'robot directory in arena_simulation_setup/entities/robots'),
        ('peds', '1-3', 'pedestrians per episode: N or MIN-MAX (random obstacle task)'),
        ('ped_model', '', 'pedestrian model(s), comma separated (Gazebo: gazebo_actor, actor1, actor2); '
                          'empty = Arena default from task_generator.yaml'),
        ('obstacles', '', 'static obstacles per episode: N or MIN-MAX; empty = 3-5 (0 in Isaac-only scenes)'),
        ('obstacle_models', '', 'static obstacle model(s), comma separated; empty = Arena default '
                                '(Gazebo) / all models with a USD version (Isaac)'),
        ('gui', 'false', 'open the simulator window (Gazebo GUI / Isaac Sim) and RViz'),
        ('rviz', 'false', 'open RViz only (ignored when gui:=true)'),
        ('render', 'ogre', 'Gazebo render engine: ogre (Arena default) | ogre2 (PBR, GPU headless)'),
        ('isaac_renderer', 'RayTracedLighting', 'Isaac Sim renderer: RayTracedLighting | PathTracing'),
        ('camera', 'follow', 'Isaac Sim window camera: follow (chase camera behind the robot) | free'),
        ('isaac_hz', '20', 'Isaac Sim render/sensor rate per simulated second (physics stays 60 Hz); '
                           '60 = upstream (every physics step, ~0.25x real time)'),
        ('seed', '-1', 'random seed of the task generator (-1 = random)'),
        ('human', '', 'pedestrian simulator: hunav | isaac | dummy; empty = hunav for gazebo, isaac for isaac'),
        ('ped_rate', '50', 'Gazebo: pedestrian (HuNav) update rate in Hz of simulated time '
                           '(upstream: 1000 = every physics step, very slow in big worlds)'),
    ]
    return LaunchDescription([
        *(DeclareLaunchArgument(n, default_value=d, description=h) for n, d, h in args),
        OpaqueFunction(function=_setup),
    ])
