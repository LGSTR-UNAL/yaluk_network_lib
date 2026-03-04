from dataclasses import dataclass
from typing import List, Optional
import math
from enum import Enum
from .IdentifiedObject import IdentifyObject
from .GeoTransform import CoordTransf, PointLatLng, PointXY


@dataclass
class PhaseName(Enum):
    A = "A"
    B = "B"
    C = "C"
    N = "N"
    M = "M"


class Element_id:
    def __init__(self):
        self.id = ""
        self.idx = 0
        self.Name = ""


class Node(IdentifyObject):
    def __init__(
        self,
        location: Optional[PointLatLng] = None,
        RPAT=20,
        configuration: str = "Default",
    ):
        super().__init__()
        self.geo_transformer = CoordTransf()
        self.initlocation = (
            location if location is not None else PointLatLng(6.1924, -75.3979)
        )
        xinit, yinit = self.geo_transformer.to_projected(
            self.initlocation.Lat, self.initlocation.Lng
        )
        self.initXY = PointXY(xinit, yinit)
        self.GeoLocation = PointLatLng(self.initlocation.Lat, self.initlocation.Lng)
        self.Phases_id: List = []
        self.Lines = []
        self.Transformers = []
        self.SurgeArresters = []
        self.Shunt_elements = []
        self.CFO = 0.0
        self.RatedVoltage = 0.0
        self.Directstrike = False
        self.Location_x = 0.0  # X Coordinate in meters from the initial location
        self.Location_y = 0.0  # Y Coordinate in meters from the initial location
        self.RPAT = RPAT
        self.Configuration = configuration

    @property
    def InitLatLong(self) -> PointLatLng:
        return self.initlocation

    @InitLatLong.setter
    def InitLatLong(self, value: PointLatLng):
        self.initlocation = value
        xinit, yinit = self.geo_transformer.to_projected(
            self.initlocation.Lat, self.initlocation.Lng
        )
        self.initXY = PointXY(xinit, yinit)

    @property
    def InitXY(self) -> PointXY:
        return self.initXY

    @InitXY.setter
    def InitXY(self, value: PointXY):
        self.initXY = value
        lat, lon = self.geo_transformer.to_geographic(self.initXY.X, self.initXY.Y)
        self.initlocation = PointLatLng(lat, lon)

    @property
    def Num_conductors(self):
        return len(self.Phases_id)

    @property
    def Location_X(self):  # X Coordinate in meters from the initial location
        return self.Location_x

    @Location_X.setter
    def Location_X(self, value):
        """value: Y coordinate in meters (relative or absolute)
        type: "rel" for relative to initial location, "abs" for absolute from the initial location
        """
        self.Location_x = value
        x = value + self.initXY.X
        y = self.Location_Y + self.initXY.Y
        lat, lon = self.geo_transformer.to_geographic(x, y)
        self.GeoLocation = PointLatLng(lat, lon)

    @property
    def Location_Y(self):  # Y Coordinate in meters from the initial location
        #
        return self.Location_y

    @Location_Y.setter
    def Location_Y(self, value):
        """value: Y coordinate in meters (relative or absolute)
        type: "rel" for relative to initial location, "abs" for absolute from the initial location
        """
        self.Location_y = value
        x = self.Location_X + self.initXY.X
        y = value + self.initXY.Y
        lat, lon = self.geo_transformer.to_geographic(x, y)
        self.GeoLocation = PointLatLng(lat, lon)

    # def XY_2_LatLng(self, Init_Location):
    #
    #    delta_lat = self.Location_Y / R * 180.0 / math.pi
    #    delta_lng = self.Location_X / R * 180.0 / math.pi
    #    self.GeoLocation = PointLatLng(Init_Location.Lat + delta_lat, Init_Location.Lng + delta_lng)
