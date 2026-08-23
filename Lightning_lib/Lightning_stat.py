from __future__ import annotations

import io
import math
import random
from enum import Enum
from typing import TYPE_CHECKING, List

import numpy as np
from scipy.stats import lognorm
from scipy.special import ndtri

from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf, PointLatLng, PointXY

from .Lightning import Lightning
from .Lightning import Current_Waveform

if TYPE_CHECKING:
    from Network_lib.Network import Network

# _sample_reject_pool: cada lote nuevo pide este multiplicador veces la
# cantidad de puntos que todavia faltan (no la cantidad total pedida) --
# 5x balancea encontrar suficientes aceptados en el primer lote sin
# sobre-generar de mas cuando el corredor cubre una fraccion razonable
# del bounding box (medido con un corredor ~17.6% del bbox: converge en
# 1 lote para la enorme mayoria de los rayos).
_REJECT_POOL_BATCH_MULTIPLIER = 5


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
        replay_df=None,
        buffer_area_rel_error: float = 0.01,
        buffer_area_max_samples: int = 200000,
        planar_epsg: int = 3116,
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
        # EPSG plano real del caso (structures.csv/GeoJSON) -- usado por
        # LoadFromDatabase para alinear la ingesta LLS con net.InitXY, que
        # esta en este mismo sistema (ver spec
        # 2026-08-16-epsg-configurable-ingesta-lls-design.md).
        self.planar_epsg: int = planar_epsg

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
        # cache de los arrays NumPy de self.segments para _sample_reject
        # (vectorizado) -- se arma perezosamente la primera vez que hace
        # falta, self.segments no cambia despues de esto.
        self._seg_matrix_cache = None
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
        elif M == "Replay":
            self.LoadFromPreviousRun(replay_df)
            self.check_direct_strike(net)

        # sampling="bbox" es el modo legacy: el area sigue siendo la del
        # rectangulo, no la del corredor (los puntos SI cubren todo el bbox).
        # M distinto de ProbDistribution/Database/Replay (stub futuro) tampoco corre
        # sobre el corredor, asi que tambien usa el area del rectangulo.
        bbox_area = (self.Xmax - self.Xmin) * (self.Ymax - self.Ymin)
        uses_corridor = M in ("ProbDistribution", "Database", "Replay") and self.sampling != "bbox"
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

        # sampling="buffer_reject" (el default, y el unico modo reportado
        # como lento en produccion): ubicaciones de TODOS los rayos de una
        # sola vez, en lotes vectorizados compartidos -- ver
        # _sample_reject_pool. bbox/capsule siguen igual que antes, un
        # punto a la vez via _sample_location (no son el cuello de botella
        # reportado).
        locations = (
            self._sample_reject_pool(self.Num_events)
            if self.sampling == "buffer_reject"
            else None
        )

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

            # Random spatial location (dentro del corredor/buffer)
            x, y = locations[i] if locations is not None else self._sample_location()
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
        # antes: lognorm(s=Std_I, scale=exp(log(Mean_Ip_X))).median() -- el
        # median de una lognormal con ese scale es EXACTAMENTE el scale
        # (propiedad estandar de la distribucion), asi que construir el
        # objeto entero solo para llamar .median() era pura sobrecarga sin
        # ningun computo real detras (~2.5s para 1500 llamadas, ver test de
        # regresion).
        if Ix_kA > 20:
            Std_I = self.std_dev_I2
            Mean_I = math.exp(math.log(self.Mean_Ip_2))
        else:
            Std_I = self.std_dev_I1
            Mean_I = math.exp(math.log(self.Mean_Ip_1))

        Xtf = math.log(
            self.Mean_tf
        ) + self.tf_correlation * self.std_dev_tf / Std_I * (
            math.log(Ix_kA) - math.log(Mean_I)
        )
        Std_tf = self.std_dev_tf * math.sqrt(1 - self.tf_correlation**2)
        # antes: lognorm(s=Std_tf, scale=exp(Xtf)).ppf(q) -- reconstruia un
        # lognorm() nuevo en cada llamada solo para invertir la CDF una vez.
        # lognorm(s,scale=exp(mu)).ppf(q) == exp(mu + s*Phi^-1(q)) (Phi^-1 =
        # inversa normal estandar), verificado numericamente a ~1e-15 de
        # diferencia contra la formula original -- scipy.special.ndtri es
        # esa inversa normal, sin construir ningun objeto de distribucion.
        Front_time = math.exp(Xtf + Std_tf * ndtri(self._rng.random())) * 1e-6
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

        transf = CoordTransf(dst_epsg=self.planar_epsg)
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
    # Replay de una corrida anterior (reproducibilidad)
    # ---------------------------------------------------------
    def LoadFromPreviousRun(self, df) -> int:
        """Reconstruye rayos EXACTOS a partir de los parametros ya
        calculados de una corrida anterior (Ih1/Ih2/tao11-22/n1/n2 y la
        posicion en X0_abs/Y0_abs), sin pasar por ningun sorteo -- a
        diferencia de LoadFromDatabase, que si vuelve a llamar
        _impute_front_time (con su propio numero aleatorio) para el tiempo
        de frente. Filtra espacialmente igual que LoadFromDatabase: un rayo
        puede quedar fuera del corredor de ESTE sub-caso y pertenecer al de
        un sub-caso vecino -- no hay deduplicacion entre sub-casos (spec de
        reutilizacion de rayos, 2026-08-12). A diferencia de
        LoadFromDatabase, NO lanza excepcion si el resultado queda vacio: un
        sub-caso sin rayos reutilizables es un resultado valido (se acepta
        el hueco), no un error.

        X0_abs/Y0_abs son la posicion ABSOLUTA del rayo (el mismo sistema
        plano de structures.csv), no el X0/Y0 crudo de la corrida anterior:
        ese es relativo a net.InitXY, que es el nodo 1 de la red que lo
        genero, y cada sub-caso de area tiene el suyo. Reutilizar el valor
        crudo desplaza el rayo por la diferencia entre origenes -- medido en
        produccion el 2026-08-23: hasta 14,2 km, con rayos que terminaban
        junto a un nodo donde en realidad nunca cayo ninguno. Aca se
        convierte al marco local de ESTA red (restando su propio origen)
        antes de filtrar por corredor y antes de ubicar el rayo."""
        accepted = []
        for _, row in df.iterrows():
            X0 = float(row["X0_abs"]) - self.x_init
            Y0 = float(row["Y0_abs"]) - self.y_init
            if self._min_dist_to_lines(X0, Y0) > self.buffer_radius:
                continue
            accepted.append((row, X0, Y0))

        for i, (row, X0, Y0) in enumerate(accepted):
            Li = Lightning(case=i)
            Li.initXY = self.initXY
            Li.initlocation = self.initlocation
            Li.Ih1 = float(row["Ih1"])
            Li.Ih2 = float(row["Ih2"])
            Li.tf1 = float(row["tao11"])
            Li.tc1 = float(row["tao21"])
            Li.tf2 = float(row["tao12"])
            Li.tc2 = float(row["tao22"])
            Li.n1 = float(row["n1"])
            Li.n2 = float(row["n2"])
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

    def _segment_matrix(self):
        """Arrays NumPy cacheados de self.segments (ax,ay,bx,by,dx,dy,seg2)
        para vectorizar distancia punto-a-todos-los-segmentos -- mismo
        patron que ya usa _compute_buffer_area (ver su docstring: bucle
        Python puro O(muestras*segmentos), ~57s con ~289 segmentos, vs
        ~4s vectorizado). Se arma una sola vez por instancia."""
        if self._seg_matrix_cache is None:
            seg = np.array(self.segments)  # (m,4): ax,ay,bx,by
            ax, ay, bx, by = seg[:, 0], seg[:, 1], seg[:, 2], seg[:, 3]
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            seg2_safe = np.where(seg2 == 0.0, 1.0, seg2)  # evita division por 0
            self._seg_matrix_cache = (ax, ay, bx, by, dx, dy, seg2, seg2_safe)
        return self._seg_matrix_cache

    def _min_dist_to_lines_batch(self, px: np.ndarray, py: np.ndarray) -> np.ndarray:
        """Version vectorizada de _min_dist_to_lines: distancia minima de
        CADA punto en (px,py) (arrays 1D) a todos los segmentos, de una
        sola vez -- usada por _sample_reject en vez de min() por punto."""
        ax, ay, bx, by, dx, dy, seg2, seg2_safe = self._segment_matrix()
        px_b, py_b = px[:, None], py[:, None]      # (m,1) vs (1,num_seg)
        t = ((px_b - ax) * dx + (py_b - ay) * dy) / seg2_safe
        t = np.clip(t, 0.0, 1.0)
        t = np.where(seg2 == 0.0, 0.0, t)           # degenerado -> t=0
        cx, cy = ax + t * dx, ay + t * dy
        dist = np.hypot(px_b - cx, py_b - cy)        # (m, num_seg)
        return dist.min(axis=1)

    def _sample_reject(self):
        """Un solo punto por llamada, bucle Python puro -- se mantiene tal
        cual para _sample_location/otros usos puntuales. GenStatCurrents ya
        NO llama esto para sampling="buffer_reject": vectorizar UN punto a
        la vez (evaluado y descartado: ver historia en el commit que agrego
        _sample_reject_pool) resulto igual o peor que este bucle simple --
        el overhead de NumPy por llamada no se amortiza con lotes chicos.
        La version que si vale la pena es _sample_reject_pool, que comparte
        un lote grande entre TODOS los rayos que hacen falta de una vez."""
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

    def _sample_reject_pool(self, n: int) -> list:
        """Genera las `n` ubicaciones de TODOS los rayos que hacen falta de
        una sola vez, compartiendo lotes vectorizados entre ellas -- a
        diferencia de _sample_reject (una llamada independiente por rayo),
        que paga el overhead de NumPy N veces para lotes chicos sin
        amortizarlo (medido: igual o peor que el bucle Python original, ver
        _sample_reject). Cada lote nuevo pide
        `_REJECT_POOL_BATCH_MULTIPLIER` veces la cantidad de puntos que
        TODAVIA faltan (no la cantidad original `n`), para no sobre-generar
        una vez que ya se acepto la mayoria -- si de 1000 rayos ya se
        aceptaron 950, el siguiente lote pide candidatos para los 50 que
        faltan, no para 1000 de nuevo."""
        if n <= 0:
            return []
        rng = self._rng
        accepted: list = []
        tries_budget = self.max_tries * n
        tries_used = 0
        last_px, last_py = 0.0, 0.0
        while len(accepted) < n and tries_used < tries_budget:
            remaining = n - len(accepted)
            batch = min(remaining * _REJECT_POOL_BATCH_MULTIPLIER, tries_budget - tries_used)
            batch = max(batch, 1)
            px = self.Xmin + np.array([rng.random() for _ in range(batch)]) * (self.Xmax - self.Xmin)
            py = self.Ymin + np.array([rng.random() for _ in range(batch)]) * (self.Ymax - self.Ymin)
            min_dist = self._min_dist_to_lines_batch(px, py)
            idx = np.flatnonzero(min_dist <= self.buffer_radius)
            for i in idx[:remaining]:
                accepted.append((float(px[i]), float(py[i])))
            last_px, last_py = float(px[-1]), float(py[-1])
            tries_used += batch

        if len(accepted) < n:
            print(
                f"* Aviso: no se encontraron suficientes puntos en el buffer "
                f"({len(accepted)}/{n}) en {tries_used} intentos (corredor "
                "chico frente al bbox); se rellena con el ultimo sorteo."
            )
            accepted.extend([(last_px, last_py)] * (n - len(accepted)))
        return accepted

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

    def _montecarlo_area_by_tramo(self, seg_to_tramo: dict, n_samples: int = 300000) -> dict:
        """Area de cada tramo (m_i/A_i de compute_density_check), estimada
        por Monte Carlo: muestrea puntos en el corredor (mismo muestreo por
        rechazo que _compute_buffer_area) y clasifica cada punto aceptado
        por `nearest_segment_index` -> tramo -- la MISMA regla que ya usa
        compute_density_check para asignar cada rayo real a su tramo.

        Por que Monte Carlo y no geometria analitica (historia completa en
        el docstring de compute_density_check, punto 4): una union
        geometrica de los segmentos de un tramo, por mas exacta que sea,
        solo sabe de SUS PROPIOS segmentos -- si otro tramo (lejos en el
        indice de `self.segments`, pero cerca en el espacio real, por un
        recodo o un paralelismo de la red) le "roba" parte de esa zona via
        nearest_segment_index, la geometria aislada no tiene forma de
        detectarlo. El Monte Carlo evita el problema de raiz porque usa la
        MISMA regla de asignacion en todo momento -- captura automaticamente
        curvas, bifurcaciones, y esta competencia entre tramos cercanos en
        el espacio, sin necesitar ningun caso especial."""
        ax, ay, bx, by, dx, dy, seg2, seg2_safe = self._segment_matrix()
        rng = self._rng
        tally: dict = {}
        accepted_total = 0
        # Cota dura de tamano de lote (no remaining*multiplicador como
        # _sample_reject_pool) -- si la tasa de aceptacion del corredor es
        # baja frente al bbox de una red real grande, "remaining" no baja y
        # el lote quedaria fijo en un tamano enorme por cientos de
        # iteraciones, cada una asignando varias matrices (lote x
        # segmentos) -- causo un OOM real contra una red de 178 km2 de
        # buffer antes de acotarlo asi.
        BATCH_CAP = 20000
        MAX_ITERS = 60
        for _ in range(MAX_ITERS):
            if accepted_total >= n_samples:
                break
            this_batch = min(BATCH_CAP, (n_samples - accepted_total) * 2)
            this_batch = max(this_batch, 1)
            px = self.Xmin + np.array([rng.random() for _ in range(this_batch)]) * (self.Xmax - self.Xmin)
            py = self.Ymin + np.array([rng.random() for _ in range(this_batch)]) * (self.Ymax - self.Ymin)
            px_b, py_b = px[:, None], py[:, None]
            t = ((px_b - ax) * dx + (py_b - ay) * dy) / seg2_safe
            t = np.clip(t, 0.0, 1.0)
            t = np.where(seg2 == 0.0, 0.0, t)
            cx, cy = ax + t * dx, ay + t * dy
            dist = np.hypot(px_b - cx, py_b - cy)
            min_dist = dist.min(axis=1)
            nearest = dist.argmin(axis=1)
            keep = np.flatnonzero(min_dist <= self.buffer_radius)
            for i in keep:
                key = seg_to_tramo[int(nearest[i])]
                tally[key] = tally.get(key, 0) + 1
            accepted_total += len(keep)

        A_buffer_km2 = self.Area / 1e6
        return {
            key: (count / accepted_total) * A_buffer_km2 if accepted_total else None
            for key, count in tally.items()
        }

    def compute_density_check(self, Ng_real: float, segment_length_km: float) -> dict:
        """Chequeo de homogeneidad de la campana de rayos ya generada
        (self.Lightnings): parte self.segments en tramos consecutivos (mismo
        orden que net.Lines) de longitud objetivo `segment_length_km`, cuenta
        cuantos rayos cayeron mas cerca de cada tramo (Ng_i = m_i/A_i) y
        deriva T_sim = m_t / (Ng_real * A_buffer).

        A_i se estima por Monte Carlo (`_montecarlo_area_by_tramo`):
        muestrea puntos en el corredor y los clasifica por
        `nearest_segment_index`, la MISMA regla que ya usan los rayos
        reales -- no una franja rectangular (2*r*L) ni una union geometrica
        de los segmentos propios del tramo, y tampoco la suma de
        seg_weights (que existe para PONDERAR EL MUESTREO de donde cae un
        rayo, no para medir area).

        Historia (4 correcciones reales sobre la MISMA funcion de area,
        cada una encontrada verificando contra una corrida real):
        1. (Fase 1, 2026-08-11) sumar seg_weights por tramo duplicaba el
           circulo de cada segmento corto -- ~11-12 km^2 por tramo de 1 km
           en vez de los ~2 km^2 esperados. Reemplazado por la franja
           rectangular (2*r*L) + casquete solo en terminales reales.
        2. (2026-08-18) la franja rectangular es correcta SOLO si el tramo
           es perfectamente recto -- una curva real (la red sigue el trazado
           de una via/terreno) hace que el buffer real se solape consigo
           mismo, y la franja lo sobreestima. Reemplazada por una union
           geometrica real (`shapely`, linemerge + join redondo) para TODOS
           los tramos, no solo los clusters de bifurcacion. Encontrado en
           una corrida real de 20000 rayos con Ng_i hasta -47% por debajo
           de Ng_real en tramos sin ninguna bifurcacion cerca.
        3. (2026-08-18, misma investigacion) esa union geometrica tambien
           subestimaba en el HUB de una bifurcacion real -- corregido
           agregando un circulo ahi tambien.
        4. (2026-08-18, misma investigacion) INCLUSO con esas 2
           correcciones, 3 tramos de esa misma corrida seguian con Ng_i
           hasta -49% por debajo de Ng_real, sin tener ninguna curva
           pronunciada: estaban geometricamente CERCA de otro tramo NO
           adyacente (la red hace un recodo/paralelismo que acerca dos
           tramos sin que sean consecutivos en `self.segments`) -- una
           union geometrica por tramo aislado no puede detectar que otro
           tramo, lejos en el indice pero cerca en el espacio, le "roba"
           esa zona via nearest_segment_index. Reemplazado por completo con
           el enfoque Monte Carlo (punto 4 arriba), que usa la MISMA regla
           de asignacion que los rayos reales y por lo tanto no puede
           tener este problema estructuralmente. Verificado contra el caso
           real: los 3 tramos con -28% a -49% de error bajaron a -2% a
           +4%, y el resto de los 22 tramos de esa corrida tambien mejoro.

        Los segmentos cerca de una bifurcacion real (nodo de grado >=3) se
        agrupan en su PROPIO tramo (uno por cluster de bifurcacion) -- el
        reparto de rayos entre sus ramas es exacto (cada rayo va al
        segmento mas cercano). A_buffer (para T_sim) sigue siendo el
        estimador Monte Carlo exacto de self.Area, no se toca.
        """
        seg_lengths_m = [
            math.hypot(bx - ax, by - ay) for (ax, ay, bx, by) in self.segments
        ]

        # Grado de cada punto (extremo de segmento): 1 = terminal real,
        # >=3 = bifurcacion. Las coordenadas de nodos compartidos son el
        # mismo float reusado (mismo objeto Node de varias Lines), asi que
        # el redondeo es solo una salvaguarda, no hace falta tolerancia.
        endpoint_degree: dict = {}
        for (ax, ay, bx, by) in self.segments:
            for pt in ((round(ax, 3), round(ay, 3)), (round(bx, 3), round(by, 3))):
                endpoint_degree[pt] = endpoint_degree.get(pt, 0) + 1

        cluster_groups = self._branch_clusters(endpoint_degree, seg_lengths_m)
        segments_in_cluster = {i for group in cluster_groups for i in group}

        # El resto de los segmentos (fuera de cualquier cluster de
        # bifurcacion) se reparte en tramos consecutivos por longitud
        # acumulada, igual que antes -- pero solo entre ellos, n se recalcula
        # sobre la longitud que les queda.
        remaining = [i for i in range(len(self.segments)) if i not in segments_in_cluster]
        remaining_length_km = sum(seg_lengths_m[i] for i in remaining) / 1000.0

        if segment_length_km and segment_length_km > 0 and remaining_length_km > 0:
            n = max(1, min(len(remaining), round(remaining_length_km / segment_length_km)))
        else:
            n = 1 if remaining else 0

        bucket_indices = []
        if remaining:
            target = sum(seg_lengths_m[i] for i in remaining) / n
            current, current_len = [], 0.0
            for i in remaining:
                current.append(i)
                current_len += seg_lengths_m[i]
                if current_len >= target and len(bucket_indices) < n - 1:
                    bucket_indices.append(current)
                    current, current_len = [], 0.0
            # bug real (encontrado revisando el calculo de areas del caso
            # real): si el ultimo flush de arriba consume justo el ultimo
            # segmento de `remaining`, `current` queda vacio -- agregarlo
            # igual crea un tramo fantasma (m_i=0, A_i_km2=0.0) que no
            # representa ningun segmento real, solo infla n_tramos.
            if current:
                bucket_indices.append(current)

        seg_to_tramo: dict = {}
        for bi, idxs in enumerate(bucket_indices):
            for i in idxs:
                seg_to_tramo[i] = ("normal", bi)
        for ci, group in enumerate(cluster_groups):
            for i in group:
                seg_to_tramo[i] = ("cluster", ci)

        counts: dict = {}
        for L in self.Lightnings:
            si = self.nearest_segment_index(L.X_location, L.Y_location)
            key = seg_to_tramo[si]
            counts[key] = counts.get(key, 0) + 1

        A_buffer_km2 = self.Area / 1e6
        m_t = len(self.Lightnings)
        T_sim_years = (
            m_t / (Ng_real * A_buffer_km2) if Ng_real and Ng_real > 0 and A_buffer_km2 else None
        )

        def _ng_i(m_i: int, area_km2: float):
            # Ng_i tiene que quedar en las mismas unidades que Ng_real
            # (rayos/km2/año): m_i/area_km2 es la densidad CRUDA acumulada
            # durante los T_sim años ya simulados, no una tasa anual -- sin
            # dividir por T_sim_years, Ng_i queda T_sim veces mayor que
            # Ng_real para cualquier T_sim != 1 (bug real reportado por el
            # usuario, la UI compara Ng_i contra Ng_real asumiendo la misma
            # escala).
            if not area_km2 or not T_sim_years:
                return None
            return (m_i / area_km2) / T_sim_years

        # Area por Monte Carlo (asignacion de vecino mas cercano, la MISMA
        # regla que usan los rayos reales) -- reemplaza la union geometrica
        # de los propios segmentos del tramo (linemerge + join redondo +
        # circulo en terminales/hubs internos). Historia (2026-08-18,
        # misma investigacion, corrida real de 20000 rayos):
        # 1. La franja rectangular sobreestimaba tramos curvos (hasta -47%
        #    de Ng_i) -- corregido con la union geometrica real.
        # 2. La union geometrica segui sobreestimando 3 tramos especificos
        #    (7, 17, 18 en esa corrida, hasta -49%) que NO tienen curvas
        #    pronunciadas: estan geometricamente CERCA de otro tramo no
        #    adyacente (la red real hace un recodo/paralelismo que acerca
        #    dos tramos sin que sean consecutivos en self.segments) -- el
        #    area geometrica de un tramo aislado no sabe que parte de su
        #    "propio" corredor en realidad esta mas cerca de un VECINO, que
        #    se queda con esos rayos via nearest_segment_index. La union
        #    geometrica por tramo simplemente no puede detectar esto (no
        #    tiene forma de saber que otro tramo, lejos en el indice pero
        #    cerca en el espacio, "compite" por la misma zona).
        # El Monte Carlo evita el problema de raiz: muestrea puntos en el
        # corredor completo y los clasifica por el MISMO nearest_segment_index
        # que ya usan los rayos reales, así que automaticamente reparte el
        # area segun a quien realmente le tocaria cada zona -- capta curvas,
        # bifurcaciones, Y esta competencia entre tramos cercanos en el
        # espacio, todo en un solo mecanismo. Verificado contra el caso real
        # 216-13: los 3 tramos con -28% a -49% de error bajaron a -2% a +4%,
        # y el resto de los 22 tramos tambien mejoro (dev tipica <10%, ya
        # dentro del ruido de muestreo esperable para su m_i).
        mc_by_key = self._montecarlo_area_by_tramo(seg_to_tramo)

        tramos = []
        for bi in range(len(bucket_indices)):
            key = ("normal", bi)
            area_km2 = mc_by_key.get(key)
            m_i = counts.get(key, 0)
            tramos.append({
                "tramo": len(tramos),
                "m_i": m_i,
                "A_i_km2": area_km2,
                "Ng_i": _ng_i(m_i, area_km2),
            })
        for ci in range(len(cluster_groups)):
            key = ("cluster", ci)
            area_km2 = mc_by_key.get(key)
            m_i = counts.get(key, 0)
            tramos.append({
                "tramo": len(tramos),
                "m_i": m_i,
                "A_i_km2": area_km2,
                "Ng_i": _ng_i(m_i, area_km2),
            })

        return {
            "Ng_real": Ng_real,
            "NgSegmentLength_km": segment_length_km,
            "m_t": m_t,
            "A_buffer_km2": A_buffer_km2,
            "T_sim_years": T_sim_years,
            "n_tramos": len(tramos),
            "tramos": tramos,
            "L_lin_km": sum(seg_lengths_m) / 1000.0,
        }

    def _branch_clusters(self, endpoint_degree: dict, seg_lengths_m: list) -> list:
        """Agrupa en clusters los segmentos cercanos a una bifurcacion real
        (nodo de grado >=3): desde cada nodo asi, camina por la red hasta
        `self.buffer_radius` metros acumulados por cada rama, juntando los
        segmentos recorridos. Clusters que comparten un segmento (dos
        bifurcaciones cercanas entre si) se fusionan en uno solo. Devuelve
        una lista de sets de indices de self.segments -- vacia si no hay
        ninguna bifurcacion."""
        branch_points = {pt for pt, deg in endpoint_degree.items() if deg >= 3}
        if not branch_points:
            return []

        adjacency: dict = {}
        for i, (ax, ay, bx, by) in enumerate(self.segments):
            pa = (round(ax, 3), round(ay, 3))
            pb = (round(bx, 3), round(by, 3))
            adjacency.setdefault(pa, []).append((i, pb))
            adjacency.setdefault(pb, []).append((i, pa))

        cluster_radius = self.buffer_radius
        segments_near_branch: set = set()
        for bp in branch_points:
            visited = {bp: 0.0}
            stack = [bp]
            while stack:
                pt = stack.pop()
                dist_here = visited[pt]
                if dist_here >= cluster_radius:
                    continue
                for seg_idx, other_pt in adjacency.get(pt, []):
                    segments_near_branch.add(seg_idx)
                    new_dist = dist_here + seg_lengths_m[seg_idx]
                    if other_pt not in visited or new_dist < visited[other_pt]:
                        visited[other_pt] = new_dist
                        stack.append(other_pt)

        # Componentes conexas de segments_near_branch (segmentos que
        # comparten un extremo quedan en el mismo grupo/tramo).
        point_to_segs: dict = {}
        for i in segments_near_branch:
            ax, ay, bx, by = self.segments[i]
            for pt in ((round(ax, 3), round(ay, 3)), (round(bx, 3), round(by, 3))):
                point_to_segs.setdefault(pt, []).append(i)

        groups = []
        remaining = set(segments_near_branch)
        while remaining:
            start = next(iter(remaining))
            group: set = set()
            stack = [start]
            while stack:
                seg_i = stack.pop()
                if seg_i in group:
                    continue
                group.add(seg_i)
                remaining.discard(seg_i)
                ax, ay, bx, by = self.segments[seg_i]
                for pt in ((round(ax, 3), round(ay, 3)), (round(bx, 3), round(by, 3))):
                    for other in point_to_segs.get(pt, ()):
                        if other not in group:
                            stack.append(other)
            groups.append(group)
        return groups

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
        """Version vectorizada: antes recorria cada rayo (self.Lightnings) y
        por cada uno llamaba Network.check_direct_strike, que a su vez
        recorria TODAS las lineas de la red -- O(rayos*lineas) en Python
        puro (~4s medido con 1500 rayos x 300 lineas), ademas recalculando
        get_max_height() (constante POR LINEA, no por rayo) y
        velocity/beta/beta_factor (constante para TODA la red) en cada una
        de esas 1500*300 iteraciones. Aca se arma una matriz
        (rayos x lineas) con NumPy de una sola vez, y las constantes se
        computan una sola vez.

        Los efectos secundarios de Network.check_direct_strike /
        Line.check_direct_strike sobre isFDTD/isDirectStrike/
        node.Directstrike NO se replican aca a proposito: en el bucle
        original quedaban sobreescritos en cada iteracion (solo
        sobrevivia el ultimo rayo procesado -- un estado sin uso real
        despues de este chequeo estadistico) y se recalculan
        correctamente mas adelante, rayo por rayo, al armar el .atp real
        de cada uno (Network.MakeATPBuffer llama check_direct_strike de
        nuevo con el threshold_distance real de esa corrida, justo antes
        de escribir ese .atp)."""
        if not self.Lightnings:
            return

        from yaluk_network_lib.Network_lib.Network import (
            _RUSCK_K,
            _SPEED_OF_LIGHT,
            _DEFAULT_CHANNEL_VELOCITY,
        )

        ax, ay, bx, by, dx, dy, seg2, seg2_safe = self._segment_matrix()
        lines = list(net.Lines)
        hmax = np.array(
            [line.Configuration.get_max_height() if line.Configuration else 0.0 for line in lines]
        )
        velocity = (
            net.Channel_settings.Velocity
            if net.Channel_settings is not None
            else _DEFAULT_CHANNEL_VELOCITY
        )
        beta = velocity / _SPEED_OF_LIGHT
        beta_factor = beta / math.sqrt(1 - beta**2)

        px = np.array([L.X_location for L in self.Lightnings])
        py = np.array([L.Y_location for L in self.Lightnings])
        Imax = np.array([L.Ih1 for L in self.Lightnings])  # Amperios (GenStatCurrents ya hizo *1000)

        px_b, py_b = px[:, None], py[:, None]
        t = ((px_b - ax) * dx + (py_b - ay) * dy) / seg2_safe
        t = np.clip(t, 0.0, 1.0)
        t = np.where(seg2 == 0.0, 0.0, t)
        cx, cy = ax + t * dx, ay + t * dy
        distance = np.hypot(px_b - cx, py_b - cy)  # (n_strokes, n_lines)

        Imax_kA = (Imax / 1e3)[:, None]  # (n_strokes,1)
        Rs = 10 * Imax_kA**0.65
        Rg = 0.9 * Rs
        hmax_row = hmax[None, :]  # (1,n_lines)
        # Rg>hmax_row implica hmax_row<Rg=0.9*Rs, asi que (Rg-hmax_row) esta
        # en [0, 0.9*Rs) y el discriminante nunca es negativo (mismo
        # supuesto implicito que el codigo original, que tampoco lo valida).
        threshold = np.where(Rg > hmax_row, np.sqrt(Rs**2 - (Rg - hmax_row) ** 2), Rs)

        is_direct_line = distance <= threshold  # (n_strokes, n_lines)
        # distance==0 solo ocurre en una linea directamente impactada, que
        # threshold>0 siempre clasifica is_direct_line=True para esa misma
        # celda -- esa fila entera toma la rama de impacto directo mas abajo
        # y jamas lee Vrusck[k], asi que el inf/nan resultante es inocuo
        # (mismo comportamiento del original: Line.check_direct_strike ya
        # retorna ds=True antes de que Network.check_direct_strike llegue a
        # calcular Vrusck para esa linea).
        with np.errstate(divide="ignore", invalid="ignore"):
            Vrusck = _RUSCK_K * beta_factor * Imax_kA * hmax_row / distance  # (n_strokes, n_lines)

        line_ids = [line.id for line in lines]

        for k, L in enumerate(self.Lightnings):
            direct_row = is_direct_line[k]
            if direct_row.any():
                # primer indice True, mismo orden que net.Lines -- igual al
                # bucle original, que retornaba en el primer match.
                j = int(np.argmax(direct_row))
                L.direc_strike = True
                L.Rusck_max_voltage = 0.0
                L.min_dist = float(distance[k, j])
                L.line_id_nearest = line_ids[j]
            else:
                j = int(np.argmin(distance[k]))
                L.direc_strike = False
                L.Rusck_max_voltage = float(Vrusck[k].max())
                L.min_dist = float(distance[k, j])
                L.line_id_nearest = line_ids[j]

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
