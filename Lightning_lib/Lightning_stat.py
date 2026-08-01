from __future__ import annotations

import io
import math
import random
from enum import Enum
from typing import TYPE_CHECKING, List

from scipy.stats import lognorm

from yaluk_network_lib.Network_lib.GeoTransform import PointLatLng, PointXY

from .Lightning import Lightning
from .Lightning import Current_Waveform

if TYPE_CHECKING:
    from Network_lib.Network import Network


def _dist_point_to_segment(px, py, ax, ay, bx, by) -> float:
    """Distancia minima del punto (px,py) al segmento (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0.0:                       # segmento degenerado (nodos iguales)
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class StatI_ModelType(Enum):
    Database = 0
    ProbDistribution = 1


class Lightning_stat:
    def __init__(
        self,
        net: Network,
        num_events=100,
        M: str = "ProbDistribution",
        dist=1000,
        sampling: str = "buffer_reject",
        buffer_radius: float = 1000.0,
        max_tries: int = 50000,
    ):

        self.Model: StatI_ModelType = M

        # Spatial boundaries
        self.Xmin: float = net.xmin - dist
        self.Xmax: float = net.xmax + dist
        self.Ymin: float = net.ymin - dist
        self.Ymax: float = net.ymax + dist
        self.initlocation = PointLatLng(net.InitLatLong.Lat, net.InitLatLong.Lng)
        self.x_init, self.y_init = net.InitXY.X, net.InitXY.Y
        self.initXY = PointXY(self.x_init, self.y_init)

        # Buffer sampling config
        self.sampling: str = sampling
        self.buffer_radius: float = buffer_radius
        self.max_tries: int = max_tries
        self._rng = random.Random()      # siempre aleatorio, sin semilla
        self.segments = [
            (
                L.Node_i.Location_X, L.Node_i.Location_Y,
                L.Node_j.Location_X, L.Node_j.Location_Y,
            )
            for L in net.Lines
        ]
        if sampling != "bbox" and not self.segments:
            raise ValueError(
                "Lightning_stat: no hay lineas para construir el buffer "
                "(net.Lines vacio); use sampling='bbox' o cargue la red primero."
            )
        # peso proporcional al area de la capsula (rect 2rL + circulo pi r^2)
        self.seg_weights = [
            2 * buffer_radius * math.hypot(bx - ax, by - ay)
            + math.pi * buffer_radius ** 2
            for (ax, ay, bx, by) in self.segments
        ]

        # Statistics
        self.Num_events: int = num_events

        self.Mean_Ip_1: float = 61
        self.Mean_Ip_2: float = 33.3

        self.std_dev_I1: float = 1.33
        self.std_dev_I2: float = 0.605

        self.Mean_tf: float = 3.83
        self.std_dev_tf: float = 0.553

        self.tf_correlation: float = 0.47

        # Heidler defaults
        self.n1: float = 4
        self.tc: float = 50e-6

        # Lightning database
        self.Lightnings: List[Lightning] = []
        if M == "ProbDistribution":
            self.GenStatCurrents()
            self.Area: float = self._compute_buffer_area()
            self.check_direct_strike(net)
        else:
            self.Lightnings = []
            self.Area: float = (self.Xmax - self.Xmin) * (self.Ymax - self.Ymin)

    # ---------------------------------------------------------
    # Statistical lightning generation
    # ---------------------------------------------------------

    def GenStatCurrents(self) -> int:

        rng = random.Random()

        Ix1 = lognorm(s=self.std_dev_I1, scale=math.exp(math.log(self.Mean_Ip_1)))

        Ix2 = lognorm(s=self.std_dev_I2, scale=math.exp(math.log(self.Mean_Ip_2)))

        for i in range(self.Num_events):

            Li = Lightning(case=i)
            Li.initXY = self.initXY
            Li.initlocation = self.initlocation
            Xrnd = rng.random()
            Ix = Ix1.ppf(Xrnd)

            if Ix > 20:
                Ix = Ix2.ppf(Xrnd)
                Std_I = self.std_dev_I2
                Mean_I = Ix2.median()
            else:
                Std_I = self.std_dev_I1
                Mean_I = Ix1.median()

            Li.Ih1 = Ix
            Li.tc1 = self.tc
            Li.n1 = self.n1
            Li.Decay_time = self.tc

            Xtf = math.log(
                self.Mean_tf
            ) + self.tf_correlation * self.std_dev_tf / Std_I * (
                math.log(Ix) - math.log(Mean_I)
            )

            Std_tf = self.std_dev_tf * math.sqrt(1 - self.tf_correlation**2)

            Tf_dist = lognorm(s=Std_tf, scale=math.exp(Xtf))
            Li.Front_time = Tf_dist.ppf(rng.random()) * 1e-6

            Li.tf1 = (Li.Front_time ** (self.n1 + 1) / (self.n1 * self.tc)) ** (
                1 / self.n1
            )

            Li.Ih1 *= 1000
            Li.Magnitude = Li.Ih1

            Li.WaveformType = int(Current_Waveform.Heidler.value)

            # Random spatial location
            Li.X_location = self.Xmin + rng.random() * (self.Xmax - self.Xmin)
            Li.Y_location = self.Ymin + rng.random() * (self.Ymax - self.Ymin)

            self.Lightnings.append(Li)

        return 0

    # ---------------------------------------------------------
    # File creation
    # ---------------------------------------------------------
    def CreateFiles(self, path: str) -> int:
        i = 1
        for L in self.Lightnings:
            L.MakeLightningFile(i, path)
            i += 1
        return 0

    # ---------------------------------------------------------
    # CSV database creation
    # ---------------------------------------------------------
    def Create_csvDB(self, filename: str, Vr: float = 0):

        import os

        if os.path.exists(filename):
            os.remove(filename)

        with open(filename, "w") as file:
            file.write(
                "Case;Ih1;Ih2;tao11;tao21;tao12;tao22;n1;n2;"
                "X0;Y0;direct_strike;min_dist;Line_id;Rusck_maxV\n"
            )

            sim_all = Vr <= 0
            i = 1

            for L in self.Lightnings:

                file.write(
                    f"{i};{L.Ih1:.2f};{L.Ih2:.2f};"
                    f"{L.tf1:.3E};{L.tc1:.3E};"
                    f"{L.tf2:.3E};{L.tc2:.3E};"
                    f"{int(L.n1)};{int(L.n2)};"
                    f"{L.X_location:.2f};{L.Y_location:.2f};"
                    f"{int(L.direc_strike)};"
                    f"{L.min_dist:.2f};{L.line_id_nearest};"
                    f"{L.Rusck_max_voltage:.2f}\n"
                )

                i += 1

    def Create_csvBuffer(self, Vr: float = 0):

        buffer = io.StringIO()
        buffer.write(
            "Case;Ih1;Ih2;tao11;tao21;tao12;tao22;n1;n2;"
            "X0;Y0;direct_strike;min_dist;Line_id;Rusck_maxV\n"
        )

        sim_all = Vr <= 0
        i = 1

        for L in self.Lightnings:

            buffer.write(
                f"{L.case+1};{L.Ih1:.2f};{L.Ih2:.2f};"
                f"{L.tf1:.3E};{L.tc1:.3E};"
                f"{L.tf2:.3E};{L.tc2:.3E};"
                f"{int(L.n1)};{int(L.n2)};"
                f"{L.X_location:.2f};{L.Y_location:.2f};"
                f"{int(L.direc_strike)};"
                f"{L.min_dist:.2f};{L.line_id_nearest};"
                f"{L.Rusck_max_voltage:.2f}\n"
            )

        return buffer

    def check_direct_strike(self, net: Network):
        for L in self.Lightnings:
            L.direc_strike, L.Rusck_max_voltage, L.min_dist, L.line_id_nearest = (
                net.check_direct_strike(L.X_location, L.Y_location, L.Ih1)
            )

    def create_dataframe(self):
        import pandas as pd

        data = []
        for L in self.Lightnings:
            data.append(
                {
                    "Ih1": L.Ih1,
                    "Ih2": L.Ih2,
                    "tao11": L.tf1,
                    "tao21": L.tc1,
                    "tao12": L.tf2,
                    "tao22": L.tc2,
                    "n1": int(L.n1),
                    "n2": int(L.n2),
                    "X0": L.X_location,
                    "Y0": L.Y_location,
                    "direct_strike": int(L.direc_strike),
                    "min_dist": L.min_dist,
                    "line_id_nearest": L.line_id_nearest,
                    "Rusck_max_voltage": L.Rusck_max_voltage,
                    "Lat": L.GeoLocation.Lat,
                    "Lng": L.GeoLocation.Lng,
                }
            )
            self.lightnings_df = pd.DataFrame(data)
        return self.lightnings_df
