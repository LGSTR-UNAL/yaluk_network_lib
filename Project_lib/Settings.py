
from enum import Enum
from yaluk_network_lib.Lightning_lib.LightningChannel import LightningChannel
from yaluk_network_lib.Lightning_lib.Soil import Soil
from yaluk_network_lib.Network_lib import Network as nl


class Current_model(Enum):
    Heidler = "Heidler"
    Triangular = "Triangular"
    Ramp = "Ramp"

class SimulationSettings:
    """
    Direct translation of SimulationSettings from Settings.cs
    """
    def __init__(self):
        self.Tmax = 20e-6
        self.Size2 = 40
        self.Dt=.2e-8
        self.Dx=30.0
        self.Conductivity=100.0
        self.Permitivity=10.0
        self.Typewaveform=1 #1: Heidler, 2: Triangular, 3: Ramp
        self.MaxDistCamp=10000.0
        self.Perfectsoil = False
        self.Print_field_info = False
        self.Print_field=False
        self.Read_field=False
        self.Status_profile = False

class StrokeSettings:
    """Direct translation of StrokeSettings from Settings.cs
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
class ATPSettings:
    """
    Direct translation of GeneralSettings from Settings.cs
    """
    def __init__(self):
        self.Plot_freq=99999999
        self.Plot_out=False

class ProjectSettings():
    
    def __init__(self):
        self.Sim_settings=SimulationSettings()
        self.Channel_settings=LightningChannel()
        self.Soil_settings=Soil()
        self.Atp_settings=nl.AtpSettings()
        
      
