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
        buffer_area_rel_error: float = 0.01,
        buffer_area_max_samples: int = 200000,
    ):

        self.Model: StatI_ModelType = M

        # Config del estimador dinamico de _compute_buffer_area: valores
        # invalidos (<=0, o None si viene de un sim_settings mal armado)
        # caen al default de siempre, en vez de propagar el error.
        self.buffer_area_rel_error: float = (
            buffer_area_rel_error if buffer_area_rel_error and buffer_area_rel_error > 0 else 0.01
        )
        self.buffer_area_max_samples: int = (
            buffer_area_max_samples if buffer_area_max_samples and buffer_area_max_samples > 0 else 200000
        )

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
        self.Area: float = (
            self._compute_buffer_area(self.buffer_area_rel_error, self.buffer_area_max_samples)
            if uses_corridor else bbox_area
        )

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

    def _compute_buffer_area(
        self, rel_error: float = 0.01, max_samples: int = 200000, batch: int = 10000,
    ) -> float:
        """Estimador Monte Carlo del area del corredor, vectorizado con NumPy,
        DINAMICO: corre por lotes y para en cuanto el error estandar de la
        estimacion acumulada cae debajo de `rel_error` (relativo al area
        estimada), con un minimo de 2 lotes antes de evaluar el corte (evita
        parar temprano con una desviacion estandar artificialmente chica por
        pocas muestras) y un tope duro en `max_samples` para corredores muy
        chicos frente al bounding box (ahi el evento "cae dentro" es raro y
        el error converge lento). Antes corria siempre a un `n` fijo de
        200000; la version en Python puro (bucle de n*len(segments) llamadas
        a _dist_point_to_segment) tardaba ~57s con ~289 segmentos (caso
        real), esta version vectorizada tardaba ~4s para el mismo caso
        siempre a n fijo -- ahora puede terminar antes si el corredor es
        geometricamente simple.
        self._buffer_area_n_used queda con el numero de muestras usadas,
        para diagnostico/tests."""
        bbox_area = (self.Xmax - self.Xmin) * (self.Ymax - self.Ymin)
        seg = np.array(self.segments)          # (m,4): ax,ay,bx,by
        ax, ay, bx, by = seg[:, 0], seg[:, 1], seg[:, 2], seg[:, 3]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        seg2_safe = np.where(seg2 == 0.0, 1.0, seg2)   # evita division por 0

        rng = self._rng
        inside = 0
        n_done = 0
        n_batches = 0
        min_batches = 2
        while n_done < max_samples:
            m = min(batch, max_samples - n_done)
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
            n_done += m
            n_batches += 1

            p_hat = inside / n_done
            if n_batches >= min_batches and p_hat > 0:
                area_hat = bbox_area * p_hat
                se_area = bbox_area * math.sqrt(p_hat * (1 - p_hat) / n_done)
                if se_area / area_hat < rel_error:
                    break

        self._buffer_area_n_used = n_done
        return bbox_area * inside / n_done

    def nearest_segment_index(self, x: float, y: float) -> int:
        """Indice (en self.segments/self.seg_weights) del segmento mas
        cercano al punto (x,y). Usado por compute_density_check para asignar
        cada rayo ya generado a su tramo."""
        dists = [_dist_point_to_segment(x, y, *s) for s in self.segments]
        return min(range(len(dists)), key=lambda i: dists[i])

    def compute_density_check(self, Ng_real: float, segment_length_km: float) -> dict:
        """Chequeo de homogeneidad de la campana de rayos ya generada
        (self.Lightnings): parte self.segments en tramos consecutivos (mismo
        orden que net.Lines) de longitud objetivo `segment_length_km`, cuenta
        cuantos rayos cayeron mas cerca de cada tramo (Ng_i = m_i/A_i) y
        deriva T_sim = m_t / (Ng_real * A_buffer).

        A_i es el area de una franja rectangular (2*r*L_tramo), NO la suma de
        seg_weights de los segmentos reales del tramo: seg_weights existe
        para PONDERAR EL MUESTREO (cada segmento carga su propio circulo
        pi*r^2 completo, a proposito, para que segmentos cortos no queden
        sub-representados al elegir donde cae un rayo) y sumarlos duplica
        ese circulo una vez por cada segmento real dentro del tramo -- con
        postes cada ~130-150 m y r=1000 m eso significa contar 6-7 circulos
        de ~3.14 km^2 en vez de uno solo (bug real reportado por el usuario
        contra el caso 216-13_a01: ~11-12 km^2 por tramo de 1 km en vez de
        los ~2 km^2 esperados). La franja rectangular ignora los 2 casquetes
        circulares de los extremos de la linea COMPLETA (no de cada tramo) y
        el solape en curvas/quiebres cerrados -- por eso sum(A_i) de todos
        los tramos queda un poco por debajo de A_buffer, no muy por encima.
        A_buffer (para T_sim) sigue siendo el estimador Monte Carlo exacto
        de self.Area, no se toca.
        """
        n_segments = len(self.segments)
        seg_lengths_m = [
            math.hypot(bx - ax, by - ay) for (ax, ay, bx, by) in self.segments
        ]
        total_length_km = sum(seg_lengths_m) / 1000.0

        if segment_length_km and segment_length_km > 0 and total_length_km > 0:
            n = max(1, min(n_segments, round(total_length_km / segment_length_km)))
        else:
            n = 1

        total_length_m = sum(seg_lengths_m)
        target = total_length_m / n
        bucket_indices = []
        current, current_len = [], 0.0
        for i, seg_len in enumerate(seg_lengths_m):
            current.append(i)
            current_len += seg_len
            if current_len >= target and len(bucket_indices) < n - 1:
                bucket_indices.append(current)
                current, current_len = [], 0.0
        bucket_indices.append(current)

        seg_to_bucket = {}
        for bi, idxs in enumerate(bucket_indices):
            for i in idxs:
                seg_to_bucket[i] = bi

        counts = [0] * len(bucket_indices)
        for L in self.Lightnings:
            si = self.nearest_segment_index(L.X_location, L.Y_location)
            counts[seg_to_bucket[si]] += 1

        tramos = []
        for bi, idxs in enumerate(bucket_indices):
            length_m = sum(seg_lengths_m[i] for i in idxs)
            area_km2 = (2 * self.buffer_radius * length_m) / 1e6
            m_i = counts[bi]
            tramos.append({
                "tramo": bi,
                "m_i": m_i,
                "A_i_km2": area_km2,
                "Ng_i": (m_i / area_km2) if area_km2 else None,
            })

        A_buffer_km2 = self.Area / 1e6
        m_t = len(self.Lightnings)
        T_sim_years = (
            m_t / (Ng_real * A_buffer_km2) if Ng_real and Ng_real > 0 and A_buffer_km2 else None
        )

        return {
            "Ng_real": Ng_real,
            "NgSegmentLength_km": segment_length_km,
            "m_t": m_t,
            "A_buffer_km2": A_buffer_km2,
            "T_sim_years": T_sim_years,
            "n_tramos": len(bucket_indices),
            "tramos": tramos,
        }

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
