from typing import Optional, List
from .Node import PhaseName, Node, PointLatLng
from .Configuration_Type import Configuration_Type
import numpy as np
class Line:
    def __init__(self, N_i:Optional[Node]=None, N_j:Optional[Node]=None, Config:Optional[Configuration_Type]=None, is_FDTD:bool=True, isDirectStrike:bool=False):
        self.Line_Config = Config; self.Node_i = N_i; self.Node_j = N_j; self.isFDTD = is_FDTD; self.Phases_connected = []; self.isDirectStrike = isDirectStrike
        if Config: self.Configuration = Config
    @property
    def length(self) -> float:
        if self.Node_i and self.Node_j:
            dx = self.Node_j.Location_X - self.Node_i.Location_X
            dy = self.Node_j.Location_Y - self.Node_i.Location_Y
            return np.hypot(dx, dy)
        return 0.0
    @property
    def Configuration(self): return self.Line_Config
    @Configuration.setter
    def Configuration(self, value: Configuration_Type):
        self.Line_Config = value; self.Phases_connected.clear()
        for i in range(value.Num_conductors):
            ph = PhaseName.A if i==0 else (PhaseName.B if i==1 else (PhaseName.C if i==2 else PhaseName.N))
            self.Phases_connected.append(ph)
            if self.Node_i and ph not in self.Node_i.Phases_id: self.Node_i.Phases_id.append(ph)
            if self.Node_j and ph not in self.Node_j.Phases_id: self.Node_j.Phases_id.append(ph)
    def Dist2line(self, point: PointLatLng) -> float:
        # Placeholder for distance calculation from a point to the line
        XA0=self.Node_i.Location_X
        YA0=self.Node_i.Location_Y
        XB0=self.Node_j.Location_X
        YB0=self.Node_j.Location_Y
        self.Node_j.initlocation.Lng
        EARTH_RADIUS = 6_371_000.0
        X0 = (point.Lng - self.Node_j.initlocation.Lng) / 180 * np.pi * EARTH_RADIUS 
        Y0 = (point.Lat - self.Node_j.initlocation.Lat) / 180 * np.pi * EARTH_RADIUS 
        # -------------------------------
        # Vertical line
        # -------------------------------
        if XB0 == XA0:

            xc = XA0
            yc = Y0

            if (yc - YA0) * (yc - YB0) < 0:
                DISTANCIA = abs(X0 - XA0)
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
        return DISTANCIA
    def check_point_proximity(self, point: PointLatLng, threshold: float) -> bool:
        distance = self.Dist2line(point)
        if distance <= threshold:
            self.isFDTD = True
        else:            
            self.isFDTD = False
        return self.isFDTD
    
    def check_direct_strike(self, point: PointLatLng, Imax: float) -> bool:
        Rs=10*Imax**0.65
        Rg=0.9*Rs
        hmax=0
        for cond in self.Configuration.Conductors:
            if hmax< cond.Height:
                hmax=cond.Height
        if Rg >hmax:
            threshold =np.hypot(Rs, Rg- hmax)
        else:
            threshold = Rs      
        distance = self.Dist2line(point)
        if distance <= threshold:
            self.isDirectStrike = True
            self.Node_i.Directstrike = True
            self.isFDTD = False
        else:            
            self.isDirectStrike = False
            self.Node_i.Directstrike = False
            self.Nodej.Directstrike = False
        return self.isFDTD 