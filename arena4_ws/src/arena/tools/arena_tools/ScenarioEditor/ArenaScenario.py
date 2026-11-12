import numpy as np
import os
import yaml
import json
from .Pedestrian.Pedestrian import Pedestrian
from .Robot.Robot import Robot
from ..utils.HelperFunctions import *


class ArenaScenario:
    def __init__(self):
        self.pedestrianAgents = []  # list of Pedestrian objects
        self.interactiveObstacles = []  # list of InteractiveObstacle messages
        self.staticObstacles = []  # list of 
        self.robotAgents = [] # list of Robot object
        self.mapPath = ""  # path to map file
        self.resets = 0
        self.path = ""  # path to file associated with this scenario

    def toDict(self):
        d = {}

        d["robots"] = {}
        d["obstacles"] = {}

        d["robots"] = [a.toDict() for a in self.robotAgents]
        d["obstacles"]["static"] = [o.toDict() for o in self.staticObstacles]
        d["obstacles"]["interactive"] = [o.toDict() for o in self.interactiveObstacles]
        d["obstacles"]["dynamic"] = [a.toDict() for a in self.pedestrianAgents]

        return d

    @staticmethod
    def fromDict(d: dict):
        scenario = ArenaScenario()
        scenario.loadFromDict(d)
        return scenario

    def loadFromDict(self, d: dict):
        if d.get("obstacles") and d.get("obstacles").get("dynamic"):
            self.pedestrianAgents = [Pedestrian.fromDict(
                a) for a in d["obstacles"]["dynamic"]]
        else:
            print("There are no dynamic obstacles in this scenario!")
            self.pedestrianAgents = []
            # self.interactiveObstacles = ...TODO
        if d.get("robots"):
            self.robotAgents = [Robot.fromDict(a) for a in d["robots"]]
        else:
            print("There are no robots in this scenario!")
            self.robotAgents = []

    def saveToFile(self, path_in: str = "") -> bool:
        '''
        Save Scenario in file.
        - path_in: path to save file
        - format: format of save file, can be "json" or "yaml"
        '''
        if os.path.exists(path_in):  # TODO is this not always false when it's a new filename?
            self.path = path_in

        if self.path == "":
            return False

        _, file_extension = os.path.splitext(self.path)
        with open(self.path, "w") as file:
            data = self.toDict()
            if file_extension == ".json":
                json.dump(data, file, indent=4)
            elif file_extension == ".yaml":
                yaml.dump(data, file, default_flow_style=None)
            else:
                raise Exception(
                    "wrong format. file needs to have 'json' or 'yaml' file ending.")

        return True

    def loadFromFile(self, path_in: str):
        if os.path.exists(path_in):
            _, file_extension = os.path.splitext(path_in)
            with open(path_in, "r") as f:
                data = None
                if file_extension == ".json":
                    data = json.load(f)
                elif file_extension == ".yaml":
                    data = yaml.safe_load(f)
                else:
                    raise Exception(
                        "wrong format. file needs to have 'json' or 'yaml' file ending.")

                self.loadFromDict(data)
                self.path = path_in

        else:
            raise Exception(f"file '{path_in}' does not exist")
