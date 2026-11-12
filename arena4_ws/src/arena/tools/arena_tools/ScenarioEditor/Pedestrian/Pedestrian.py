import numpy as np
from enum import Enum
from typing import Optional
from arena_tools.utils.HelperFunctions import *


class PedestrianStartupMode(Enum):
    DEFAULT = 0
    WAIT_TIMER = 1
    TRIGGER_ZONE = 2


class PedestrianWaypointMode(Enum):
    LOOP = 0
    RANDOM = 1


class PedestrianAgentType(Enum):
    ADULT = 0
    CHILD = 1
    ELDER = 2
    FORKLIFT = 3
    SERVICEROBOT = 4


class InteractiveObstacleType(Enum):
    SHELF = 0


class PedestrianInteractiveObstacle:
    def __init__(self):
        self.obstacleType = InteractiveObstacleType.SHELF
        #   TODO...


class Pedestrian:
    def __init__(self, name="Pedestrian") -> None:
        self.name = name

        # set default values (derived from pedestrian_msgs/Ped.msg)
        self.id = 0
        self.pos = np.zeros(3)
        self.type = "adult"
        self.model = "actor1"
        self.custom_properties:list[dict] = []

        self.waypoints = []  # list of 2D numpy arrays

    def __eq__(self, other):
        if not isinstance(other, Pedestrian):
            return NotImplemented

        if self.name != other.name:
            return False

        if self.id != other.id:
            return False
        if not np.allclose(self.pos, other.pos):
            return False
        if self.type != other.type:
            return False
        if self.model != other.model:
            return False
        if len(self.waypoints) != len(other.waypoints):
            return False
        if not np.all(
            [np.allclose(wpa, wpb) for wpa, wpb in zip(self.waypoints, other.waypoints)]
        ):
            return False
            
        custom_properties_fset = set(frozenset(d.items()) for d in self.custom_properties)
        other_custom_properties_fset = set(frozenset(d.items()) for d in other.custom_properties)
        if custom_properties_fset != other_custom_properties_fset:
            return False

        return True

    def toDict(self):
        d = {}

        d["name"] = self.name

        d["id"] = self.id
        d["pos"] = [float(val) for val in self.pos]
        d["type"] = self.type
        d["model"] = self.model
        d["waypoints"] = [[float(val) for val in wp] for wp in self.waypoints]
        if len(self.custom_properties) > 0:
            for property in self.custom_properties:
                property_name = list(property.keys())[0]
                value = property.get(property_name)
                d[property_name] = value

        return d

    @staticmethod
    def fromDict(d: dict):
        if d.get("name"):
            a = Pedestrian(d["name"])
        else:
            a = Pedestrian()

        if d.get("type"):
            a.type = d["type"]
        if d.get("model"):
            a.model = d["model"]
        if d.get("id"):
            a.id = d["id"]
        a.pos = np.array(d["pos"])
        a.waypoints = [np.array(wp) for wp in d["waypoints"]]

        for property_name in list(d.keys()):
            if property_name not in ["name", "type", "model", "id", "pos", "waypoints"]:
                property_value = d.get(property_name)
                a.addCustomProperty(property_name, property_value)

        return a
    
    def addCustomProperty(self, key, value):
        self.custom_properties.append({key:value})

    def editCustomProperty(self, key, new_key:Optional[None]=None, new_value:Optional[None]=None):
        if new_key:
            for property in self.custom_properties:
                if list(property.keys())[0] == key:
                    property = {new_key:property.get(key)}
                    break
            if new_value:
                raise NotImplementedError
            
        if new_value:
            for property in self.custom_properties:
                if list(property.keys())[0] == key:
                    property = {key:new_value}
            if new_key:
                raise NotImplementedError

    def removeCustomProperty(self, key):
        for idx, property in enumerate(self.custom_properties):
            if list(property.keys())[0] == key:
                self.custom_properties.pop(idx)
                break

    def getPedMsg(self):
        try:
            from pedestrian_msgs.msg import Ped
            from geometry_msgs.msg import Point
        except BaseException:
            return None

        msg = Ped()

        msg.id = self.id
        msg.pos = Point(self.pos[0], self.pos[1], 0)
        msg.type = self.type
        msg.yaml_file = self.yaml_file
        msg.number_of_peds = self.number_of_peds
        msg.vmax = self.vmax

        msg.start_up_mode = self.start_up_mode
        msg.wait_time = self.wait_time
        msg.trigger_zone_radius = self.trigger_zone_radius

        msg.chatting_probability = self.chatting_probability
        msg.tell_story_probability = self.tell_story_probability
        msg.group_talking_probability = self.group_talking_probability
        msg.talking_and_walking_probability = self.talking_and_walking_probability
        msg.requesting_service_probability = self.requesting_service_probability
        msg.requesting_guide_probability = self.requesting_guide_probability
        msg.requesting_follower_probability = self.requesting_follower_probability

        msg.max_talking_distance = self.max_talking_distance
        msg.max_servicing_radius = self.max_servicing_radius

        msg.talking_base_time = self.talking_base_time
        msg.tell_story_base_time = self.tell_story_base_time
        msg.group_talking_base_time = self.group_talking_base_time
        msg.talking_and_walking_base_time = self.talking_and_walking_base_time
        msg.receiving_service_base_time = self.receiving_service_base_time
        msg.requesting_service_base_time = self.requesting_service_base_time

        msg.force_factor_desired = self.force_factor_desired
        msg.force_factor_obstacle = self.force_factor_obstacle
        msg.force_factor_social = self.force_factor_social
        msg.force_factor_robot = self.force_factor_robot

        msg.waypoints = [Point(wp[0], wp[1], 0) for wp in self.waypoints]
        msg.waypoint_mode = self.waypoint_mode

        return msg
