import numpy as np

class Robot:
    def __init__(self, name="Robot") -> None:
        # set default values
        self.name = name
        self.id = 0
        self.start = np.array([0.0, 0.0, 0.7])
        self.goal = np.array([0.0, 0.0, 0.7])
        self.model = "jackal"

    def __eq__(self, other):
        if not isinstance(other, Robot):
            return NotImplemented
        
        if self.name != other.name:
            return False
        if self.id != other.id:
            return False
        if not np.allclose(self.start, other.start):
            return False
        if not np.allclose(self.goal, other.goal):
            return False
        if self.model != other.model:
            return False
        
        return True
    
    def toDict(self):
        d = {}

        d["start"] = [float(val) for val in self.start]
        d["goal"] = [float(val) for val in self.goal]

        return d

    @staticmethod
    def fromDict(d:dict)->"Robot":
        if d.get("name"):
            agent = Robot(d["name"])
        else:
            agent = Robot()
            
        agent.start = np.array(d["start"])
        agent.goal = np.array(d["goal"])
        
        return agent