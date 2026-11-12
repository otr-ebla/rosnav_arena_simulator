import shapely
import yaml
import os
from typing import List, Set, Dict


class Zone():

    def __init__(self, label: str, category: List[str] = [], polygon: List[List[List[float]]] = [], properties: Dict = dict()):
        self.label = label
        self.category = category
        self.polygon  = shapely.MultiPolygon([shapely.Polygon(poly) for poly in polygon])
        self.properties = properties
    
    def toDict(self):
        d = dict()
        d["label"] = self.label
        d["category"] = self.category
        d["polygon"] = [[list(coord) for coord in (polygon.exterior.coords[:-1] if shapely.is_ccw(polygon.exterior) else polygon.reverse().exterior.coords[:-1])] for polygon in self.polygon.geoms]
        for key in self.properties:
            d[key] = self.properties[key]
        return d

class ZonesData():

    def __init__(self, path: str = ""):
        self.path = path
        self.zones : List[Zone] = []
        if path != "":
            self.load(path)
    
    def toList(self) -> List[Dict]:
        return [zone.toDict() for zone in self.zones]
    
    def getCategories(self) -> Set[str]:
        categories = set()
        for zone in self.zones:
            categories.update(zone.category)
        return categories

    def load(self, path: str):
        if os.path.exists(path):
            self.path = path
            with open(path, "r") as file:
                data = yaml.safe_load(file)

            for zone in data:
                z = Zone(zone["label"], zone["category"], zone["polygon"], {k:v for k,v in zone.items() if k not in ["label", "category", "polygon"]})
                self.zones.append(z)

    def saveToFile(self, path:str) -> bool:
        self.path = path

        if self.path == "":
            return False
        _, file_extension = os.path.splitext(self.path)
        with open(self.path, "w") as file:
            data = self.toList()
            if file_extension == ".yaml":
                yaml.safe_dump(data, file, default_flow_style=False, sort_keys= False)
            else:
                raise Exception("wrong format. file needs to have 'yaml' file ending.")

        return True