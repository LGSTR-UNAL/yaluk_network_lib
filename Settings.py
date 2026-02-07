
from enum import Enum

class Current_model(Enum):
    Heidler = "Heidler"
    Triangular = "Triangular"
    Ramp = "Ramp"

class SimulationSettings:
    """
    Direct translation of SimulationSettings from Settings.cs
    """
    def __init__(self):
        self.CurrentModel = Current_model.Heidler
        self.PeakCurrent = 30e3
        self.FrontTime = 1.2e-6
        self.TailTime = 50e-6
        self.Number_of_strokes = 1
        self.Channel_velocity = 1.3e8
        self.Channel_height = 3000.0
        self.Soil_resistivity = 100.0
        self.Relative_permittivity = 10.0
        self.Magnetic_permeability = 1.0
        self.Seed = 0
