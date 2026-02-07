import os
import subprocess

from Network_lib import Network
from Lightning_lib import (
    Lightning,
    Lightning_stat,
    LightningChannel,
    Soil,
)

from .Settings import SimulationSettings


class YalukProject:
    """
    Direct refactor of YalukProject.cs

    Acts as the main orchestration class:
    - Holds Network
    - Holds Lightning model
    - Holds SimulationSettings
    - Handles save/load and ATP execution
    """

    def __init__(self):
        # Settings
        self.SimSettings = SimulationSettings()

        # Core models
        self.Network = Network()
        self.Lightning = None

        # Project info
        self.ProjectName = "Yaluk_Project"
        self.ProjectPath = ""

    # ------------------------------------------------------------------
    # Lightning construction
    # ------------------------------------------------------------------
    def BuildLightning(self):
        """
        Builds the Lightning object from simulation settings.
        Equivalent to Lightning setup logic in C#.
        """

        stats = Lightning_stat(
            Ng=1.0,
            Ik_mean=self.SimSettings.PeakCurrent,
            Ik_std=0.0,
        )

        channel = LightningChannel(
            Height=self.SimSettings.Channel_height,
            Velocity=self.SimSettings.Channel_velocity,
        )

        soil = Soil(
            rho=self.SimSettings.Soil_resistivity,
            eps_r=self.SimSettings.Relative_permittivity,
            mu_r=self.SimSettings.Magnetic_permeability,
        )

        self.Lightning = Lightning(
            Statistics=stats,
            Channel=channel,
            Soil=soil,
        )

    # ------------------------------------------------------------------
    # Project persistence
    # ------------------------------------------------------------------
    def SaveProject(self, path: str):
        """
        Saves the project:
        - Stores path
        - Saves network (.stcx)
        """
        self.ProjectPath = path
        os.makedirs(path, exist_ok=True)
        self.Network.Save(path)

    def LoadProject(self, file: str):
        """
        Loads a project from file.
        """
        self.ProjectPath = os.path.dirname(file)
        self.Network.Load(file)

    # ------------------------------------------------------------------
    # ATP execution
    # ------------------------------------------------------------------
    def ExportATP(self):
        """
        Generates the ATP file from the Network.
        """
        if not self.ProjectPath:
            raise RuntimeError("ProjectPath not set")

        self.Network.MakeAtpFile(self.ProjectPath + os.sep)

    def RunATP(self, atp_executable: str):
        """
        Executes ATP using the generated .atp file.
        """
        atp_file = os.path.join(
            self.ProjectPath,
            f"{self.ProjectName}.atp",
        )

        if not os.path.exists(atp_file):
            raise FileNotFoundError(atp_file)

        subprocess.run(
            [atp_executable, atp_file],
            check=False,
        )

