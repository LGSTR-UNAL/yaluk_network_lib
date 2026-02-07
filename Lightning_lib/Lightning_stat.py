import math
import random
from enum import Enum
from typing import List

from scipy.stats import lognorm

from .Lightning import Lightning
from .Lightning import Current_Waveform


class StatI_ModelType(Enum):
    Database = 0
    ProbDistribution = 1


class Lightning_stat:
    def __init__(self, M: StatI_ModelType = StatI_ModelType.ProbDistribution):

        self.Model: StatI_ModelType = M

        # Spatial boundaries
        self.Xmin: float = -1000
        self.Xmax: float = 2000
        self.Ymin: float = -1000
        self.Ymax: float = 1000

        # Statistics
        self.Num_events: int = 1

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

        if M == StatI_ModelType.Database:
            self.Lightnings = []
        else:
            self.Lightnings = []

    # ---------------------------------------------------------
    # Statistical lightning generation
    # ---------------------------------------------------------
    def GenStatCurrents(self) -> int:

        rng = random.Random()

        Ix1 = lognorm(
            s=self.std_dev_I1,
            scale=math.exp(math.log(self.Mean_Ip_1))
        )

        Ix2 = lognorm(
            s=self.std_dev_I2,
            scale=math.exp(math.log(self.Mean_Ip_2))
        )

        for _ in range(self.Num_events):

            Li = Lightning()

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

            Xtf = (
                math.log(self.Mean_tf)
                + self.tf_correlation
                * self.std_dev_tf
                / Std_I
                * (math.log(Ix) - math.log(Mean_I))
            )

            Std_tf = self.std_dev_tf * math.sqrt(
                1 - self.tf_correlation ** 2
            )

            Tf_dist = lognorm(s=Std_tf, scale=math.exp(Xtf))
            Li.Front_time = Tf_dist.ppf(rng.random()) * 1e-6

            Li.tf1 = (
                (Li.Front_time ** (self.n1 + 1) / (self.n1 * self.tc))
                ** (1 / self.n1)
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
                "X0;Y0;direc_strike;min_dist;Line_id;Rusck_maxV\n"
            )

            sim_all = Vr <= 0
            i = 1

            for L in self.Lightnings:

                if (
                    L.Rusck_max_voltage > Vr
                    and (not L.direc_strike or sim_all)
                ):
                    file.write(
                        f"{i};{L.Ih1:0.00E};{L.Ih2:0.00E};"
                        f"{L.tf1:0.00E};{L.tc1:0.00E};"
                        f"{L.tf2:0.00E};{L.tc2:0.00E};"
                        f"{L.n1};{L.n2};"
                        f"{L.X_location};{L.Y_location};"
                        f"{int(L.direc_strike)};"
                        f"{L.min_dist};{L.line_id_nearest};"
                        f"{L.Rusck_max_voltage}\n"
                    )

                i += 1
