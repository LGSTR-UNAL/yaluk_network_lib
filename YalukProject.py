import os
import subprocess

import math
import shutil
import subprocess
import datetime
import pickle
import numpy as np

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
    def MakeYalukSettingsFile(self):

        case_folder = os.path.join(self.GenSettings.path, "CaseFiles")

        misc_file = os.path.join(case_folder, "miscelaneo.txt")

        with open(misc_file, "w") as file:
            file.write(f"{self.Channel.Velocity:0.00E} % Velocidad descarga retorno\n")
            file.write(f"{self.Channel.Atenuation_const:0.00E} % Constante de Atenuación para MTLE si es = 0 usa modelo TL(m).zlam\n")
            file.write(f"{self.Channel.Heigth:0.00E} % Altura de la Nube(m)......................................Hcan\n")
            file.write(f"{int(not self.SimSettings.Perfectsoil)} % Conductividad activa\n")
            file.write(f"{self.SimSettings.Conductivity:0.00E}\n")
            file.write(f"{self.SimSettings.Permitivity:0.00E}\n")
            file.write(f"{self.SimSettings.Dx:0.00E}\n")
            file.write(f"{int(self.SimSettings.Typewaveform)}\n")
            file.write(f"{self.SimSettings.MaxDistCamp}\n")
            file.write(f"{self.Channel.Velocity:0.00E0} % Velocidad de la Descarga de retorno(m / s)....................v\n")
            file.write(f"{self.Channel.Atenuation_const:0.00E0} % Constante de Atenuación para MTLE si es = 0 usa modelo TL(m).zlam\n")
            file.write(f"{self.Channel.Heigth:0.00E0} % Altura de la Nube(m)......................................Hcan\n")
            file.write(f"20e-6 % Tiempo de cálculo primera ventana(s)......................tmax1 (Obsolete)\n")
            file.write(f"40 % Numero de Divisiones segunda ventana.......................SIZE2 (Obsolete)\n")
            file.write(f"{int(not self.SimSettings.Perfectsoil)} % Tener en Cuenta Conductividad  1(Si) 0(No)...............Conductividad\n")
            file.write(f"{self.SimSettings.Conductivity:0.00E0} % Conductividad del terreno o(s / m)..........................o\n")
            file.write(f"{self.SimSettings.Permitivity:0.00E0} % Permitividad del terreno e [p.u]..........................o\n")
            file.write(f"{self.SimSettings.Dx:0.00E0} % Espaciamiento en distancia dx(s / m)..........................o\n")
            file.write(f"{int(self.SimSettings.Typewaveform)} % Onda triangular o(s / m)..........................o\n")
            file.write(f"{self.SimSettings.MaxDistCamp} % !Maximum distance for calculating EM Fields [m]..........................o\n")

        # yaluk.ini
        yaluk_ini = os.path.join(self.GenSettings.path, "yaluk.ini")

        with open(yaluk_ini, "w") as file:
            file.write("CaseFiles\n")
            file.write("1\n")
            file.write(f"{len(self.Current_Network.Lines)}\n")

            max_cond = max(n.Num_conductors for n in self.Current_Network.Nodes)
            file.write(f"{max_cond}\n")

        # status
        status_file = os.path.join(self.GenSettings.path, "yaluk_status.ini")

        with open(status_file, "w") as file:
            file.write(f".{self.SimSettings.Print_field}.\n")
            file.write(f".{self.SimSettings.Print_field_inf}.\n")
            file.write(f".{self.SimSettings.Read_field}.\n")
            file.write(f".{self.SimSettings.Status_profile}.\n")




class YalukProject:

    def __init__(self):
        self.SimSettings = SimulationSettings()
        self.ATPSettings = ATP_Settings()
        self.GenSettings = Project_Settings()

        self.Channel = LightningChannel()

        self.Networks = []
        self.Current_Network = None

        self.LightStat = Lightning_stat()
        self.Current_Lightning = Lightning()

        self.GenSettings.path = os.getcwd()

    # ---------------------------------------------------------
    # ATP FILE
    # ---------------------------------------------------------
    def MakeAtpFile(self):

        filename = os.path.join(
            self.GenSettings.path,
            f"{self.GenSettings.Project_name}.atp"
        )

        if os.path.exists(filename):
            os.remove(filename)

        with open(filename, "w") as file:

            file.write("BEGIN NEW DATA CASE\n")
            file.write("C --------------------------------------------------------\n")
            file.write("C Generated by YALUK DRAW 2.0\n")
            file.write("C Developed by: Ernesto Pérez G\n")
            file.write("C Universidad Nacional de Colombia\n")
            file.write(f"C File Created on: {datetime.datetime.now()}\n")
            file.write("C --------------------------------------------------------\n")
            file.write(f"C Project Name:{self.GenSettings.Project_name}\n")
            file.write(f"C   {self.GenSettings.Description}\n")

            file.write(f"{self.SimSettings.Dt:0.0000E0}{self.SimSettings.Tmax:0.0000E0}\n")

            file.write(
                f"  {self.ATPSettings.Plot_freq:06d}     100       0       0       1       0       0       "
                f"{int(self.ATPSettings.Plot_out)}       0\n"
            )

            self.Current_Network.MakeAtpFile(file)

    # ---------------------------------------------------------
    # SAVE PROJECT (XML equivalent replaced with pickle)
    # ---------------------------------------------------------
    def Save(self):

        filename = os.path.join(
            self.GenSettings.path,
            f"{self.GenSettings.Project_name}.yaluk"
        )

        with open(filename, "wb") as file:
            pickle.dump(self, file)

    # ---------------------------------------------------------
    # NETWORK MANAGEMENT
    # ---------------------------------------------------------
    def AddNetwork(self, Net, active_network=False):

        if Net not in self.Networks:
            self.Networks.append(Net)

            if active_network:
                self.Current_Network = Net

            return len(self.Networks)

        return 0

    def SetCurrentNetwork(self, Net):
        if Net in self.Networks:
            self.Current_Network = Net

    def SetCurrentNetworkByName(self, Net_name):
        for n in self.Networks:
            if n.Name == Net_name:
                self.Current_Network = n
                break

    def SetCurrentLightning(self, Li):
        if Li in self.LightStat.Lightnings:
            self.Current_Lightning = Li

    # ---------------------------------------------------------
    # YALUK EXECUTION FILES
    # ---------------------------------------------------------
    def MakeYalukExeFiles(self):

        ruta = os.path.join(self.GenSettings.path, "CaseFiles")

        if os.path.exists(ruta):
            shutil.rmtree(ruta)

        os.makedirs(ruta)

        self.Current_Network.MakeLineFiles()
        self.Current_Lightning.MakeLightningFile(1, ruta)

        self.MakeYalukSettingsFile()

    # ---------------------------------------------------------
    # SETTINGS FILES
    # ---------------------------------------------------------
    def MakeYalukSettingsFile(self):

        case_folder = os.path.join(self.GenSettings.path, "CaseFiles")

        misc_file = os.path.join(case_folder, "miscelaneo.txt")

        with open(misc_file, "w") as file:
            file.write(f"{self.Channel.Velocity:0.00E} % Velocidad descarga retorno\n")
            file.write(f"{self.Channel.Atenuation_const:0.00E} % Atenuacion\n")
            file.write(f"{self.Channel.Heigth:0.00E} % Altura nube\n")
            file.write(f"{int(not self.SimSettings.Perfectsoil)} % Conductividad activa\n")
            file.write(f"{self.SimSettings.Conductivity:0.00E}\n")
            file.write(f"{self.SimSettings.Permitivity:0.00E}\n")
            file.write(f"{self.SimSettings.Dx:0.00E}\n")
            file.write(f"{int(self.SimSettings.Typewaveform)}\n")
            file.write(f"{self.SimSettings.MaxDistCamp}\n")

        # yaluk.ini
        yaluk_ini = os.path.join(self.GenSettings.path, "yaluk.ini")

        with open(yaluk_ini, "w") as file:
            file.write("CaseFiles\n")
            file.write("1\n")
            file.write(f"{len(self.Current_Network.Lines)}\n")

            max_cond = max(n.Num_conductors for n in self.Current_Network.Nodes)
            file.write(f"{max_cond}\n")

        # status
        status_file = os.path.join(self.GenSettings.path, "yaluk_status.ini")

        with open(status_file, "w") as file:
            file.write(f".{self.SimSettings.Print_field}.\n")
            file.write(f".{self.SimSettings.Print_field_inf}.\n")
            file.write(f".{self.SimSettings.Read_field}.\n")
            file.write(f".{self.SimSettings.Status_profile}.\n")

    # ---------------------------------------------------------
    # RUN ATP + YALUK
    # ---------------------------------------------------------
    def RunActiveCase(self):

        self.MakeAtpFile()
        self.MakeYalukExeFiles()

        atp_file = os.path.join(
            self.GenSettings.path,
            f"{self.GenSettings.Project_name}.atp"
        )

        exe_path = os.path.join(self.GenSettings.path, "tp_yaluk.exe")

        subprocess.run(
            ["tp_yaluk.exe", "BOTH", atp_file, "s", "-r"],
            cwd=self.GenSettings.path
        )

        # Remove .tmp files
        for f in os.listdir(self.GenSettings.path):
            if f.endswith(".tmp"):
                os.remove(os.path.join(self.GenSettings.path, f))

    # ---------------------------------------------------------
    # DIRECT STRIKE COMPUTATION (FULL PORT)
    # ---------------------------------------------------------
    def Compute_directstrikes(self):

        for lightning in self.LightStat.Lightnings:

            Ih = lightning.Ih1
            X0 = lightning.X_location
            Y0 = lightning.Y_location

            Rs = (10 * (Ih / 1000)) ** 0.65
            Rg = 0.9 * Rs

            for L in self.Current_Network.Lines:

                XA0 = L.Node_i.Location_X
                XB0 = L.Node_j.Location_X
                YA0 = L.Node_i.Location_Y
                YB0 = L.Node_j.Location_Y

                hm = max(c.Height for c in L.Configuration.Conductors)

                if Rg > hm:
                    dist_minima = np.sqrt(Rs**2 - (Rg - hm)**2)
                else:
                    dist_minima = Rs

                # Distance to segment
                dx = XB0 - XA0
                dy = YB0 - YA0

                if dx == 0:
                    if (Y0 - YA0) * (Y0 - YB0) < 0:
                        distancia = abs(X0 - XA0)
                    else:
                        distancia = min(
                            np.hypot(XA0 - X0, YA0 - Y0),
                            np.hypot(XB0 - X0, YB0 - Y0)
                        )
                elif dy == 0:
                    if (X0 - XA0) * (X0 - XB0) < 0:
                        distancia = abs(Y0 - YA0)
                    else:
                        distancia = min(
                            np.hypot(XA0 - X0, YA0 - Y0),
                            np.hypot(XB0 - X0, YB0 - Y0)
                        )
                else:
                    M = dy / dx
                    B = YA0 - M * XA0
                    Mp = -1 / M
                    Bp = Y0 - Mp * X0
                    Xc = (Bp - B) / (M - Mp)
                    Yc = M * Xc + B

                    if (Xc - XA0) * (Xc - XB0) < 0:
                        distancia = np.hypot(Xc - X0, Yc - Y0)
                    else:
                        distancia = min(
                            np.hypot(XA0 - X0, YA0 - Y0),
                            np.hypot(XB0 - X0, YB0 - Y0)
                        )

                if distancia < dist_minima:
                    lightning.direc_strike = True
                    lightning.min_dist = distancia
                    break
                else:
                    Vrusck = 1.2958 * 30 * Ih / 1e3 * hm / distancia

                    if Vrusck > lightning.Rusck_max_voltage:
                        lightning.Rusck_max_voltage = Vrusck
                        lightning.min_dist = distancia
                        lightning.line_id_nearest = L.idx
