from __future__ import annotations

import io
import math
import random
from enum import Enum
from typing import TYPE_CHECKING, List

import numpy as np
from scipy.stats import lognorm

from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf, PointLatLng, PointXY

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
        database_buffer=None,
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
            self.check_direct_strike(net)
        elif M == "Database":
            self.LoadFromDatabase(database_buffer)
            self.check_direct_strike(net)

        # sampling="bbox" es el modo legacy: el area sigue siendo la del
        # rectangulo, no la del corredor (los puntos SI cubren todo el bbox).
        # M distinto de ProbDistribution/Database (stub futuro) tampoco corre
        # sobre el corredor, asi que tambien usa el area del rectangulo.
        bbox_area = (self.Xmax - self.Xmin) * (self.Ymax - self.Ymin)
        uses_corridor = M in ("ProbDistribution", "Database") and self.sampling != "bbox"
        self.Area: float = self._compute_buffer_area() if uses_corridor else bbox_area

    # ---------------------------------------------------------
    # Statistical lightning generation
    # ---------------------------------------------------------

    def GenStatCurrents(self) -> int:

        rng = self._rng

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

            Li.Ih1 = Ix
            Li.tc1 = self.tc
            Li.n1 = self.n1
            Li.Decay_time = self.tc

            Li.Front_time, Li.tf1 = self._impute_front_time(Ix)

            Li.Ih1 *= 1000
            Li.Magnitude = Li.Ih1

            Li.WaveformType = int(Current_Waveform.Heidler.value)

            # Random spatial location (dentro del corredor/buffer, ver _sample_location)
            x, y = self._sample_location()
            Li.X_location = x
            Li.Y_location = y

            self.Lightnings.append(Li)

        return 0

    def _impute_front_time(self, Ix_kA: float):
        """Imputa Front_time y tf1 por correlacion lognormal con la magnitud
        (misma formula que usaba GenStatCurrents inline). `Ix_kA` es la
        corriente en kA (magnitud, antes de escalar a A). Reutilizado por
        GenStatCurrents (corriente muestreada) y por LoadFromDatabase
        (corriente real de un LLS)."""
        if Ix_kA > 20:
            Std_I = self.std_dev_I2
            Mean_I = lognorm(
                s=self.std_dev_I2, scale=math.exp(math.log(self.Mean_Ip_2))
            ).median()
        else:
            Std_I = self.std_dev_I1
            Mean_I = lognorm(
                s=self.std_dev_I1, scale=math.exp(math.log(self.Mean_Ip_1))
            ).median()

        Xtf = math.log(
            self.Mean_tf
        ) + self.tf_correlation * self.std_dev_tf / Std_I * (
            math.log(Ix_kA) - math.log(Mean_I)
        )
        Std_tf = self.std_dev_tf * math.sqrt(1 - self.tf_correlation**2)
        Tf_dist = lognorm(s=Std_tf, scale=math.exp(Xtf))
        Front_time = Tf_dist.ppf(self._rng.random()) * 1e-6
        tf1 = (Front_time ** (self.n1 + 1) / (self.n1 * self.tc)) ** (1 / self.n1)
        return Front_time, tf1

    # ---------------------------------------------------------
    # Real lightning ingestion (LLS)
    # ---------------------------------------------------------
    def LoadFromDatabase(self, buffer) -> int:
        """Carga rayos reales desde un CSV de un sistema de localizacion de
        rayos (LLS): columnas lat, lon, current_kA, timestamp. Filtra
        espacialmente por el mismo corredor que usa el modo estadistico
        (`_min_dist_to_lines(x,y) <= self.buffer_radius`) e imputa
        Front_time/tf1 con la misma correlacion que GenStatCurrents, usando
        la corriente real de cada evento."""
        import pandas as pd

        df = pd.read_csv(buffer)
        df.columns = df.columns.str.strip()

        transf = CoordTransf()
        accepted = []
        dropped = 0
        for _, row in df.iterrows():
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
                ik = abs(float(row["current_kA"]))
                if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(ik)):
                    raise ValueError("lat/lon/current_kA no finito (NaN o infinito)")
                if ik == 0:
                    raise ValueError("corriente 0")
            except (KeyError, TypeError, ValueError):
                dropped += 1
                continue
            xp, yp = transf.to_projected(lat, lon)
            X0, Y0 = xp - self.x_init, yp - self.y_init
            if self._min_dist_to_lines(X0, Y0) > self.buffer_radius:
                continue  # fuera del corredor de exposicion de la red
            accepted.append((X0, Y0, ik))

        if dropped:
            print(f"* LLS: {dropped} fila(s) descartada(s) por datos invalidos")
        if not accepted:
            raise ValueError(
                "LLS: cero rayos reales dentro del corredor de la red"
            )

        for i, (X0, Y0, ik) in enumerate(accepted):
            Li = Lightning(case=i)
            Li.initXY = self.initXY
            Li.initlocation = self.initlocation
            Li.tc1 = self.tc
            Li.n1 = self.n1
            Li.Decay_time = self.tc
            Li.Front_time, Li.tf1 = self._impute_front_time(ik)
            Li.Ih1 = ik * 1000                          # kA -> A
            Li.Magnitude = Li.Ih1
            Li.WaveformType = int(Current_Waveform.Heidler.value)
            Li.X_location = X0
            Li.Y_location = Y0
            self.Lightnings.append(Li)

        return 0

    # ---------------------------------------------------------
    # Spatial sampling
    # ---------------------------------------------------------
    def _min_dist_to_lines(self, x: float, y: float) -> float:
        return min(_dist_point_to_segment(x, y, *s) for s in self.segments)

    def _sample_location(self):
        if self.sampling == "buffer_reject":
            return self._sample_reject()
        if self.sampling == "buffer_capsule":
            return self._sample_capsule()
        return self._sample_bbox()

    def _sample_bbox(self):
        rng = self._rng
        x = self.Xmin + rng.random() * (self.Xmax - self.Xmin)
        y = self.Ymin + rng.random() * (self.Ymax - self.Ymin)
        return x, y

    def _sample_reject(self):
        rng = self._rng
        x = y = 0.0
        for _ in range(self.max_tries):
            x = self.Xmin + rng.random() * (self.Xmax - self.Xmin)
            y = self.Ymin + rng.random() * (self.Ymax - self.Ymin)
            if self._min_dist_to_lines(x, y) <= self.buffer_radius:
                return x, y
        print(
            f"* Aviso: no se encontro punto en el buffer en {self.max_tries} "
            "intentos (corredor chico frente al bbox); se usa el ultimo sorteo."
        )
        return x, y

    def _sample_capsule(self):
        rng = self._rng
        r = self.buffer_radius
        for _ in range(self.max_tries):
            seg = rng.choices(self.segments, weights=self.seg_weights, k=1)[0]
            x, y = self._sample_in_capsule(seg, r)
            k = sum(
                1 for s in self.segments
                if _dist_point_to_segment(x, y, *s) <= r
            )
            if k > 0 and rng.random() < 1.0 / k:
                return x, y
        print(
            f"* Aviso: correccion de solapamiento no acepto en {self.max_tries} "
            "intentos; se usa el ultimo sorteo."
        )
        return x, y

    def _sample_in_capsule(self, seg, r):
        rng = self._rng
        ax, ay, bx, by = seg
        L = math.hypot(bx - ax, by - ay)
        rect, caps = 2 * r * L, math.pi * r * r
        if L > 0 and rng.random() < rect / (rect + caps):
            ux, uy = (bx - ax) / L, (by - ay) / L     # unitario a lo largo
            s = rng.random() * L
            n = (2 * rng.random() - 1) * r
            return ax + ux * s - uy * n, ay + uy * s + ux * n   # normal (-uy,ux)
        cx, cy = (ax, ay) if rng.random() < 0.5 else (bx, by)   # tapa en extremo
        rr = r * math.sqrt(rng.random())
        th = rng.random() * 2 * math.pi
        return cx + rr * math.cos(th), cy + rr * math.sin(th)

    def _compute_buffer_area(self, n: int = 200000, batch: int = 10000) -> float:
        """Estimador Monte Carlo del area del corredor, vectorizado con NumPy.
        La version en Python puro (bucle de n*len(segments) llamadas a
        _dist_point_to_segment) tardaba ~57s con ~289 segmentos (caso real);
        esta version tarda ~4s para el mismo caso, procesando en lotes para
        no materializar un array (n x num_segmentos) completo en memoria."""
        bbox_area = (self.Xmax - self.Xmin) * (self.Ymax - self.Ymin)
        seg = np.array(self.segments)          # (m,4): ax,ay,bx,by
        ax, ay, bx, by = seg[:, 0], seg[:, 1], seg[:, 2], seg[:, 3]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        seg2_safe = np.where(seg2 == 0.0, 1.0, seg2)   # evita division por 0

        rng = self._rng
        inside = 0
        remaining = n
        while remaining > 0:
            m = min(batch, remaining)
            remaining -= m
            px = self.Xmin + np.array([rng.random() for _ in range(m)]) * (self.Xmax - self.Xmin)
            py = self.Ymin + np.array([rng.random() for _ in range(m)]) * (self.Ymax - self.Ymin)
            px_b, py_b = px[:, None], py[:, None]      # (m,1) vs (1,num_seg)
            t = ((px_b - ax) * dx + (py_b - ay) * dy) / seg2_safe
            t = np.clip(t, 0.0, 1.0)
            t = np.where(seg2 == 0.0, 0.0, t)           # degenerado -> t=0
            cx, cy = ax + t * dx, ay + t * dy
            dist = np.hypot(px_b - cx, py_b - cy)        # (m, num_seg)
            min_dist = dist.min(axis=1)
            inside += int(np.count_nonzero(min_dist <= self.buffer_radius))
        return bbox_area * inside / n

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
