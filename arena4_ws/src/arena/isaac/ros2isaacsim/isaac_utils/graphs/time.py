import omni.graph.core as og
from isaac_utils.graphs import Graph
from omni.isaac.core.utils import extensions

extensions.enable_extension("omni.isaac.core_nodes")
extensions.enable_extension("omni.isaac.ros2_bridge")


def PublishTime(graph_path: str):
    graph = Graph(graph_path)

    on_playback_tick = graph.node('on_playback_tick', 'omni.graph.action.OnPlaybackTick')
    read_simulation_time = graph.node('read_simulation_time', 'omni.isaac.core_nodes.IsaacReadSimulationTime')
    publish_clock = graph.node('publish_clock', 'omni.isaac.ros2_bridge.ROS2PublishClock')

    on_playback_tick.connect('tick', publish_clock, 'execIn')
    read_simulation_time.connect('simulationTime', publish_clock, 'timeStamp')

    graph.execute(og.Controller())
