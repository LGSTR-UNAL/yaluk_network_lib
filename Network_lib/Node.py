from dataclasses import dataclass
from typing import List, Optional
import math
from enum import Enum
@dataclass
class PointLatLng:
    Lat: float = 0.0
    Lng: float = 0.0
    def __str__(self): return f"({self.Lat},{self.Lng})"
    def equals(self, other): return isinstance(other, PointLatLng) and math.isclose(self.Lat, other.Lat) and math.isclose(self.Lng, other.Lng)
class PhaseName(Enum):
    A='A'; B='B'; C='C'; N='N'; M='M'
class Element_id:
    def __init__(self):
        self.id=''; self.idx=0; self.Name=''
class Node(Element_id):
    def __init__(self, location: Optional[PointLatLng]=None):
        super().__init__()
        self.initlocation = location if location is not None else PointLatLng(6.1924, -75.3979)
        self.GeoLocation = PointLatLng(self.initlocation.Lat, self.initlocation.Lng)
        self.Phases_id: List = []
        self.Lines = []
        self.Transformers = None
        self.SurgeArresters = []
        self.Shunt_elements = []
        self.CFO=0.0; self.RatedVoltage=0.0
    @property
    def Num_conductors(self): return len(self.Phases_id)
    @property
    def Location_X(self):
        R=6373100.0
        return round((self.GeoLocation.Lng - self.initlocation.Lng)/180.0*math.pi*R,1)
    @Location_X.setter
    def Location_X(self, value):
        R=6373100.0
        self.GeoLocation = PointLatLng(self.GeoLocation.Lat, round(self.initlocation.Lng + value / R * 180.0 / math.pi, 6))
    @property
    def Location_Y(self):
        R=6373100.0
        return round((self.GeoLocation.Lat - self.initlocation.Lat)/180.0*math.pi*R,1)
    @Location_Y.setter
    def Location_Y(self, value):
        R=6373100.0
        self.GeoLocation = PointLatLng(round(self.initlocation.Lat + value / R * 180.0 / math.pi,6), self.GeoLocation.Lng)
    def XY_2_LatLng(self, Init_Location):
        R=6373100.0
        delta_lat = self.Location_Y / R * 180.0 / math.pi
        delta_lng = self.Location_X / R * 180.0 / math.pi
        self.GeoLocation = PointLatLng(Init_Location.Lat + delta_lat, Init_Location.Lng + delta_lng)
