from typing import Optional, List
from .Node import PhaseName, Node, PointLatLng
from .Configuration_Type import Configuration_Type
import numpy as np
from .IdentifiedObject import IdentifyObject

class Line(IdentifyObject):
    def __init__(
        self,
        N_i: Optional[Node] = None,
        N_j: Optional[Node] = None,
        Config: Optional[Configuration_Type] = None,
        is_FDTD: bool = True,
        isDirectStrike: bool = False,
    ):
        self.Line_Config = Config
        self.Node_i = N_i
        self.Node_j = N_j
        self.isFDTD = is_FDTD
        self.Phases_connected = []
        self.isDirectStrike = isDirectStrike
        self.node_ds = None
        if Config:
            self.Configuration = Config

    @property
    def length(self) -> float:
        if self.Node_i and self.Node_j:
            dx = self.Node_j.Location_X - self.Node_i.Location_X
            dy = self.Node_j.Location_Y - self.Node_i.Location_Y
            return np.hypot(dx, dy)
        return 0.0

    @property
    def Configuration(self):
        return self.Line_Config

    @Configuration.setter
    def Configuration(self, value: Configuration_Type):
        self.Line_Config = value
        self.Phases_connected.clear()
        for i in range(value.Num_conductors):
            match  i:
                case 0:
                    ph=PhaseName.A
                case 1:
                    ph=PhaseName.B
                case 2: 
                    ph=PhaseName.C
                case 3:
                    ph=PhaseName.N
                case 4:
                    ph=PhaseName.M

            self.Phases_connected.append(ph)
            if self.Node_i and ph.value not in self.Node_i.Phases_id:
                self.Node_i.Phases_id.append(ph.value)
            if self.Node_j and ph.value not in self.Node_j.Phases_id:
                self.Node_j.Phases_id.append(ph.value)

    def Dist2line(self, X0,Y0) -> float:
        # Placeholder for distance calculation from a point to the line
        XA0 = self.Node_i.Location_X
        YA0 = self.Node_i.Location_Y
        XB0 = self.Node_j.Location_X
        YB0 = self.Node_j.Location_Y
        self.Node_j.initlocation.Lng
        
        #EARTH_RADIUS = 6_371_000.0
        #X0 = (point.Lng - self.Node_j.initlocation.Lng) / 180 * np.pi * EARTH_RADIUS
        #Y0 = (point.Lat - self.Node_j.initlocation.Lat) / 180 * np.pi * EARTH_RADIUS

        # -------------------------------
        # Vertical line
        # -------------------------------
        if XB0 == XA0:

            xc = XA0
            yc = Y0

            if (yc - YA0) * (yc - YB0) < 0:
                DISTANCIA = abs(X0 - XA0)
                closest_node = self.Node_i if abs(Y0 - YA0) < abs(Y0 - YB0) else self.Node_j #check which node is closer in the vertical direction
            else:
                d1 = np.hypot(XA0 - X0, YA0 - Y0)
                d2 = np.hypot(XB0 - X0, YB0 - Y0)
                DISTANCIA = min(d1, d2)
                if DISTANCIA == d1:
                    closest_node = self.Node_i
                else:
                    closest_node = self.Node_j

        # -------------------------------
        # Horizontal line
        # -------------------------------
        elif YB0 == YA0:

            xc = X0
            yc = YA0

            if (xc - XA0) * (xc - XB0) < 0:
                DISTANCIA = abs(Y0 - YA0)
                closest_node = self.Node_i if abs(X0 - XA0) < abs(X0 - XB0) else self.Node_j #check which node is closer in the horizontal direction
            else:
                d1 = np.hypot(XA0 - X0, YA0 - Y0)
                d2 = np.hypot(XB0 - X0, YB0 - Y0)
                DISTANCIA = min(d1, d2)
                if DISTANCIA == d1:
                    closest_node = self.Node_i
                else:
                    closest_node = self.Node_j

        # -------------------------------
        # General case (inclined line)
        # -------------------------------
        else:
            M = (YB0 - YA0) / (XB0 - XA0)
            B = YA0 - M * XA0

            Mp = -1.0 / M
            Bp = Y0 - Mp * X0

            xc = (Bp - B) / (M - Mp)
            yc = M * xc + B

            if (xc - XA0) * (xc - XB0) < 0:
                DISTANCIA = np.hypot(xc - X0, yc - Y0)
                closest_node = self.Node_i if abs(X0 - XA0) < abs(X0 - XB0) else self.Node_j   # The closest point is on the line segment, so no specific node is closer
            else:
                d1 = np.hypot(XA0 - X0, YA0 - Y0)
                d2 = np.hypot(XB0 - X0, YB0 - Y0)
                DISTANCIA = min(d1, d2)
                if DISTANCIA == d1:
                    closest_node = self.Node_i
                else:
                    closest_node = self.Node_j

        # -------------------------------
        # Distance threshold logic
        # -------------------------------
        return DISTANCIA, closest_node

    def check_point_proximity(self, X,Y, threshold: float) -> bool:
        
        distance = self.Dist2line(X,Y)
        if distance <= threshold and distance > 0:
            self.isFDTD = True
        else:
            self.isFDTD = False
        return self.isFDTD

    def check_direct_strike(self, X:float, Y:float, I: float) -> bool:
        Imax = I/1e3  # Convert to kA
        Rs = 10 * Imax**0.65
        Rg = 0.9 * Rs
        hmax = self.Configuration.get_max_height() if self.Configuration else 0.0
        
        if Rg > hmax:
            threshold = np.sqrt(Rs **2 -(Rg - hmax)**2)
        else:
            threshold = Rs
        distance, self.node_ds = self.Dist2line(X,Y)
        if distance <= threshold:
            self.isDirectStrike = True
            self.node_ds.Directstrike = True
            self.isFDTD = False
        else:
            self.isDirectStrike = False
            self.Node_i.Directstrike = False
            self.Node_j.Directstrike = False
        return self.isDirectStrike, distance
