from enum import Enum
import os


class Current_Waveform(Enum):
    Heidler = 0
    Triangular = 1


class Lightning:
    def __init__(self):
        # Location
        self.X_location: float = 0.0
        self.Y_location: float = 0.0

        # Current parameters
        self.Magnitude: float = 0.0
        self.Front_time: float = 0.0
        self.Decay_time: float = 0.0

        # Heidler parameters
        self.Ih1: float = 30.0
        self.Ih2: float = 0.0
        self.tf1: float = 1.2e-6
        self.tf2: float = 0.0
        self.tc1: float = 50e-6
        self.tc2: float = 0.0
        self.n1: float = 4.
        self.n2: float = 0.0

        # Waveform
        self.WaveformType: int = int(Current_Waveform.Heidler.value)

        # Network interaction results
        self.min_dist: float = float("inf")
        self.line_id_nearest: int = 0
        self.direc_strike: bool = False
        self.Rusck_max_voltage: float = 0.0

    # -------------------------------------------------
    # Lightning file generation (ATP / Yaluk)
    # -------------------------------------------------
    def MakeLightningFile(self, i: int, path: str) -> int:

        filename = os.path.join(
            path,
            f"corr_{i:05d}.txt"
        )

        if os.path.exists(filename):
            os.remove(filename)

        with open(filename, "w") as file:
            file.write(f"{self.Ih1:0.00E}   % Magnitud Corriente 1era funcion Heidler.....Ih1\n")
            file.write(f"{self.Ih2:0.00E}   % Magnitud Corriente 2da funcion Heidler.....Ih2\n")
            file.write(f"{self.tf1:0.00E}   % tiempo de Frente 1era Funcion Heidler.......tao11\n")
            file.write(f"{self.tc1:0.00E}   % Tiempo de Cola 1era Funcion Heidler.........tao21\n")
            file.write(f"{self.tf2:0.00E}   % Tiempo de Frente 2da Funcion Heidler........tao12\n")
            file.write(f"{self.tc2:0.00E}   % Tiempo de Cola 2da Funcion Heidler..........tao22\n")
            file.write(f"{self.n1:0.00E}   % Constante 1era funcion Heidler..............n1\n")
            file.write(f"{self.n2}   % Constante 2da funcion Heidler..............n2\n")
            file.write(f"{self.X_location}   % Posición en X del Rayo..........X0\n")
            file.write(f"{self.Y_location}   % Posición en Y del Rayo..........Y0\n")

        return 0
