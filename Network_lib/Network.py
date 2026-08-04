from __future__ import annotations

import os
from sys import prefix
import token
from typing import TYPE_CHECKING, List, Optional
import math, io
from pathlib import Path
import io
import zipfile

# from click import Path
from .Node import Node, PhaseName
from .collections import NodeCollection, LineCollection, TrfCollection
from .Configuration_Type import Configuration_Type
from .Conductor import Conductor, ConductorPosition
from .Shunt_element import Shunt_lump, lumped_element, IShunt_element
from .Transformer import Transformer
from .SurgeArrester import SurgeArrester
from .Line import Line
from .IdentifiedObject import IdentifyObject
from .LCC_cards import branch_card_lcc, conductor_card_lcc, arg_card_lcc
from .GeoTransform import CoordTransf, PointLatLng, PointXY
from dataclasses import dataclass, field
from datetime import date
from .atp_solver import cleanup_solver_files, check_required_output, run_atp_solver
from .ATP_cards_w import (
    write_branches,
    write_footer,
    write_header,
    write_models,
    write_output,
    write_sources,
)

if TYPE_CHECKING:
    from Lightning_lib.Lightning import Lightning


_SPEED_OF_LIGHT = 3e8  # [m/s]
_DEFAULT_CHANNEL_VELOCITY = 2.0 / 3.0 * 3e8  # [m/s] == LightningChannel().Velocity por default
_DEFAULT_BETA = _DEFAULT_CHANNEL_VELOCITY / _SPEED_OF_LIGHT
# Formula de Rusck (ESTIMACION de tension inducida maxima por impacto
# indirecto -- no decide impacto directo, eso es Line.check_direct_strike):
# el termino beta/sqrt(1-beta**2) es la dependencia estandar con la
# velocidad de retorno. _RUSCK_K se calibra para que, a la velocidad default
# (2/3 c), el resultado sea IDENTICO al valor hardcodeado historico
# (1.2958 * 30) -- no rompe corridas existentes.
# ADVERTENCIA: _RUSCK_K en si no esta validado contra una referencia
# bibliografica de Rusck, solo reproduce el numero que ya se usaba. Confirmar
# con quien tenga la derivacion original antes de confiar en el resultado
# para velocidades muy distintas al default.
_RUSCK_K = (1.2958 * 30) / (_DEFAULT_BETA / math.sqrt(1 - _DEFAULT_BETA**2))


@dataclass
class Network(IdentifyObject):
    xmax: float | None = 0.0
    ymax: float | None = 0.0
    xmin: float | None = 0.0
    ymin: float | None = 0.0

    class output:
        def __init__(self, error: bool = False, id_str: str = "", index: int = 0):
            self.error = error
            self.id = id_str
            self.index = index

    def __init__(self, uid: str = "", name: str = ""):
        super().__init__()
        print("Initializing network...")
        self.uid = uid if uid else ""
        self.name = name if name else ""
        self.InitLatLong = PointLatLng(6.1924, -75.3979)
        geo_transform = CoordTransf()
        x, y = geo_transform.to_projected(self.InitLatLong.Lat, self.InitLatLong.Lng)
        self.InitXY = PointXY(x, y)
        self.Lines = LineCollection()
        self.Nodes = NodeCollection()
        self.Transformers = TrfCollection()
        self.Shunt_elements = []
        self.SurgeArresters = []
        self.Tmax = 60e-6
        self.Dt = 2e-8
        self.Dx = 10.0
        self.Dmax_induction = 0.0
        self.xmax = None
        self.ymax = None
        self.xmin = None
        self.ymin = None
        self.num_lines_FDTD = 0
        self.direct_strike = (
            False  # Flag to indicate if the network is affected by a direct strike
        )
        self.line_ds = None  # ID of the line with direct strike, if any
        self.Vrusck_max = 0.0  # [m] Maximum Rusck voltage calculated for the network based on the distance to the lines and the maximum current
        self.min_distance = 1e15  # [m] Minimum distance from the strike point to the lines in the network
        self.Channel_settings = None  # LightningChannel opcional; default si no se setea (ver check_direct_strike)

    def update_limits(self, x: float, y: float):
        if self.xmax is None or x > self.xmax:
            self.xmax = x
        if self.xmin is None or x < self.xmin:
            self.xmin = x
        if self.ymax is None or y > self.ymax:
            self.ymax = y
        if self.ymin is None or y < self.ymin:
            self.ymin = y

    def AddNode(
        self,
        X,
        Y,
        Nodeidx=None,
        ctype="rel",
        label=None,
        RPAT=20,
        configuration: str = "Default",
        monitor: bool = True,
    ):
        """Add a node to the network at coordinates (X,Y) in meters from the initial location.
        If Nodeidx is provided, it will be used as the index for the new node (max 4 characters).
        Otherwise, the index will be automatically assigned based on the number of existing nodes.
        ctype: "rel" for relative to initial location, "abs" for absolute from the initial location
        label: optional label for the node
        monitor: si es False no se pide la medicion de tension del nodo en el
                 ATP (ver Node.monitor / ATP_cards_w.write_output)
        """
        tol_nodes = 1e-1  # Tolerance of 10 cm for node matching
        salida = Network.output()
        h = self.Nodes.Find(
            lambda n: math.isclose(n.Location_X, X, abs_tol=tol_nodes)
            and math.isclose(n.Location_Y, Y, abs_tol=tol_nodes)
        )

        if h is None:
            i = len(self.Nodes)
            if i > 0:
                try:
                    salida.index = int(self.Nodes[i - 1].id.lstrip("N"))
                except Exception:
                    salida.index = 0
            else:
                salida.index = 0
            newNode = Node(self.InitLatLong, RPAT, configuration)
            newNode.monitor = monitor
            if ctype == "abs":
                newNode.Location_X = X - self.InitXY.X
                newNode.Location_Y = Y - self.InitXY.Y
            else:
                newNode.Location_X = X
                newNode.Location_Y = Y
            self.update_limits(
                newNode.Location_X, newNode.Location_Y
            )  # Update network limits based on new node coordinates
            # if newNode.GeoLocation is None:
            #    newNode.XY_2_LatLng(self.InitLatLong)
            if Nodeidx is None:
                newNode.id = f"N{salida.index+1:04d}"
                newNode.idx = salida.index + 1
            else:
                if isinstance(Nodeidx, int):
                    newNode.id = f"N{Nodeidx:04d}"
                    newNode.idx = Nodeidx
                    salida.index = Nodeidx
                elif isinstance(Nodeidx, str):
                    if len(Nodeidx) > 4:
                        raise ValueError(
                            "Nodeidx string must be at most 4 characters long"
                        )
                    newNode.id = Nodeidx
                    try:
                        newNode.idx = int(Nodeidx.lstrip("N"))
                        salida.index = newNode.idx
                    except Exception:
                        newNode.idx = len(self.Nodes._list) + 1
                        salida.index = newNode.idx
            newNode.name = label if label is not None else newNode.id
            self.Nodes.Add(newNode)
            salida.error = False
            salida.id = newNode.id
        else:
            salida.id = h.id
            salida.error = True
            salida.index = 0
        return salida

    def AddBTNode(self, Node_connection: Node):
        id_name = f"B{Node_connection.id.lstrip('N')}"
        Ni = self.Nodes.Find(lambda n: n.id == id_name)
        if Ni is None:
            newNode = Node(self.InitLatLong)
            newNode.Location_X = Node_connection.Location_X
            newNode.Location_Y = Node_connection.Location_Y
            newNode.Description = " Low Voltage Node for using with transformer"
            newNode.idx = len(self.Nodes) + 1
            newNode.name = (
                Node_connection.name + "_BT" if Node_connection.name else newNode.id
            )
            # newNode.XY_2_LatLng(self.InitLatLong)
            newNode.id = id_name
            self.Nodes.Add(newNode)
            return newNode
        else:
            return Ni

    def AddLine(self, Node_i: Node, Node_j: Node, C_type: Configuration_Type) -> int:
        Linea = Line()
        Linea.Node_i = Node_i
        Linea.Node_j = Node_j
        Linea.Configuration = C_type
        # NOTA: Phases_connected ya lo asigna el setter de Configuration en Line.py
        # (A,B,C,N,M según Num_conductors). No sobreescribir aquí: el bucle antiguo
        # forzaba a N todos los conductores desde el índice 3, colapsando la fase M
        # del 5.º conductor a N y duplicando el neutro.
        h = self.Lines.Find(
            lambda L: (
                (L.Node_i == Linea.Node_i and L.Node_j == Linea.Node_j)
                or (L.Node_i == Linea.Node_j and L.Node_j == Linea.Node_i)
            )
        )
        if h is None:
            if len(self.Lines) > 0:
                index = self.Lines._list[-1].idx
            else:
                index = 0
            Linea.id = f"Line {index+1:03d}"
            Linea.idx = index + 1
            self.Lines.Add(Linea)
            if Linea.isFDTD:
                self.num_lines_FDTD += 1
            i = self.Nodes.GetByName(Linea.Node_i.name)
            if i is not None:
                i.Lines.append(Linea)
            i = self.Nodes.GetByName(Linea.Node_j.name)
            if i is not None:
                i.Lines.append(Linea)
            return i
        else:
            return -1

    def AddRLC_1p(self, RLC: lumped_element, Ni: Node, P: PhaseName, Grounded: bool):
        E = Shunt_lump(RLC, Ni, P)
        E.SolidGrounded = Grounded
        self.Shunt_elements.append(E)
        # NodeCollection no tiene GetByIdx (solo LineCollection lo tiene), asi
        # que el `self.Nodes.GetByIdx(Ni)` original lanzaba AttributeError: la
        # rama nunca se habia ejecutado porque nada llamaba a AddRLC_* hasta
        # la terminacion con Zc de la segmentacion. Ni ya ES el nodo.
        if Ni is not None:
            Ni.Shunt_elements.append(E)
        return 1

    def AddZcTermination(self, Ni: Node):
        """Termina la red en `Ni` con una resistencia a tierra por fase igual
        a la impedancia caracteristica propia del conductor correspondiente
        (`Configuration.Zc[i,i]`) de la linea incidente.

        Se usa en los nodos donde un sub-caso de la segmentacion corta la red:
        sin esta terminacion, el extremo abierto refleja la onda viajera y el
        sub-caso reporta sobretensiones que no existen en la red completa.
        Devuelve el numero de fases terminadas (0 si el nodo no tiene linea).
        """
        if not Ni.Lines:
            return 0
        linea = Ni.Lines[0]
        config = linea.Configuration
        if config is None or config.Zc is None:
            return 0
        for i, ph in enumerate(linea.Phases_connected):
            R = lumped_element()
            R.Resistance = float(config.Zc[i, i])
            self.AddRLC_1p(R, Ni, ph, True)
        return len(linea.Phases_connected)

    def AddRLC_1p_pair(self, RLC: lumped_element, Ni: Node, Nj: Node, P: PhaseName):
        E = Shunt_lump(RLC, Ni, P)
        E.SolidGrounded = False
        self.Shunt_elements.append(E)
        i = self.Nodes.GetByIdx(Ni)
        if i is not None:
            i.Shunt_elements.append(E)
        return 1

    def AddRLC_3p(self, RLC: lumped_element, Ni: Node, Grounded: bool):
        if Ni.Num_conductors > 2:
            E = Shunt_lump(RLC, Ni, PhaseName.A)
            if not Grounded:
                j = self.Nodes.GetByIdx(Ni)
                if j >= 0 and PhaseName.N not in self.Nodes[j].Phases_id:
                    self.Nodes[j].Phases_id.append(PhaseName.N)
                E.SolidGrounded = False
            else:
                E.SolidGrounded = True
            E.Add(RLC, PhaseName.B)
            E.Add(RLC, PhaseName.C)
            self.Shunt_elements.append(E)
            i = self.Nodes.GetByIdx(Ni)
            if i is not None:
                i.Shunt_elements.append(E)
            return 1
        else:
            return 0

    def AddTransf(self, label, CHV, CLV, CHL, ground, NHV, phases):
        if isinstance(NHV, int):
            NHV = self.Nodes.GetByName(NHV)
            if NHV is None:
                raise ValueError(f"Node with id {NHV} not found in the network")
        elif isinstance(NHV, str):
            NHV = self.Nodes.GetByName(NHV)
        elif isinstance(NHV, Node):
            pass
        else:
            raise ValueError("Invalid type for NHV")

        NLV = self.AddBTNode(NHV)
        Trf = Transformer(CHV, CLV, CHL, ground, NHV, NLV, phases)
        Trf.idx = 1 + len(self.Transformers._list)
        Trf.id = f"T{Trf.idx:04d}"
        Trf.Name = label
        self.Transformers.Add(Trf)
        NHV.Transformers.append(Trf)
        NLV.Transformers.append(Trf)
        return 0

    def AddSurgeArrester(self, ni: Node, pch_file: str, Phase_connect: int):
        SA = SurgeArrester(pch_file, ni, Phase_connect)
        ni.SurgeArresters.append(SA)
        self.SurgeArresters.append(SA)
        return 0

    def MakeLineFiles(self, ruta: str = "CaseFiles/", return_buffer: bool = True):

        # os.makedirs(f"{self.name}/{ruta}", exist_ok=True) #revisar la creación del archivo
        # lines_buffer = io.BytesIO()
        # for i, line in enumerate(self.Lines):
        #     filename = f"{self.name}/{ruta}linea_{i+1:03d}.txt"
        #     with open(filename, "w", encoding="utf-8") as file:
        #         file.write(
        #             f"{line.Configuration.Conductors._list[0].Conduct.Radio}              Radio del conductor\n"
        #         )
        #         file.write(
        #             f"{line.Node_i.Location_X}   {line.Node_i.Location_Y}            % Posición del extremo A en XA0   YA0\n"
        #         )
        #         file.write(
        #             f"{line.Node_j.Location_X}   {line.Node_j.Location_Y}            % Posición del extremo B en XA0   YA0\n"
        #         )
        #         for j in range(line.Configuration.Num_conductors):
        #             cp = line.Configuration.Conductors._list[j]
        #             file.write(
        #                 f"{cp.Height}   {cp.Conduct.Resistance}            % Height [m] and Resistance [Ohm/km]\n"
        #             )
        #             file.write(
        #                 f"{cp.Relative_X_location}             % Relative position\n"
        #             )

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(
            zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zf:

            for i, line in enumerate(self.Lines):
                filename = f"{ruta}linea_{i+1:03d}.txt"

                # Create in-memory text buffer
                file_buffer = io.StringIO()

                file_buffer.write(
                    f"{line.Configuration.Conductors._list[0].Conduct.Radio}              Radio del conductor\n"
                )
                file_buffer.write(
                    f"{line.Node_i.Location_X}   {line.Node_i.Location_Y}            % Posición del extremo A en XA0   YA0\n"
                )
                file_buffer.write(
                    f"{line.Node_j.Location_X}   {line.Node_j.Location_Y}            % Posición del extremo B en XA0   YA0\n"
                )

                for j in range(line.Configuration.Num_conductors):
                    cp = line.Configuration.Conductors._list[j]
                    file_buffer.write(
                        f"{cp.Height}   {cp.Conduct.Resistance}            % Height [m] and Resistance [Ohm/km]\n"
                    )
                    file_buffer.write(
                        f"{cp.Relative_X_location}             % Relative position\n"
                    )

                # Add to ZIP (convert to bytes)
                zf.writestr(filename, file_buffer.getvalue())
        zip_buffer.seek(0)
        if return_buffer:
            return zip_buffer

        extract_dir = Path(self.name)
        extract_dir.parent.mkdir(parents=True, exist_ok=True)
        zip_buffer.seek(0)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            zf.extractall(extract_dir)

        return extract_dir

    def MakeLccFile(
        self,
        ruta: str = "lcc",
        soil_resistivity: float = 100.0,
        Freq_mat: float = 1e3,
        Freq_ss: float = 1e6,
        freq_init: float = 100.0,
        decades: int = 6,
        points_decade: int = 10,
        run_solver: bool = True,
        solver_path: str | os.PathLike | None = None,
        solver_cwd: str | os.PathLike | None = None,
        return_buffer: bool = False,
    ):
        """
        Docstring for MakeLccFile

        :param self: Description
        :param ruta: path to save the LCC files
        :type ruta: str
        :param soil_resistivity: Soil resistivity in Ohm-m for LCC line characterization
        :type soil_resistivity: float
        :param Freq_mat: Frequency for matrix calculation
        :type Freq_mat: float
        :param Freq_ss: Frequency for steady state calculation
        :type Freq_ss: float
        :param freq_init: Initial frequency for LCC line characterization
        :type freq_init: float
        :param decades: #number of decades for JMarti Model
        :type decades: int
        :param points_decade: Points per decade for JMarti Model
        :type points_decade: int
        :param run_solver: If True, run the ATP/Yaluk solver for each generated
            .dat and .dbm file.
        :type run_solver: bool
        :param solver_path: Optional path to the solver executable. If omitted,
            Windows uses C:\\EMTP\\Solver\\tp_yaluk.exe and other platforms use
            tpyaluk from PATH.
        :type solver_path: str | os.PathLike | None
        :param solver_cwd: Optional working directory for the solver process.
            Defaults to each generated LCC file directory so ATP/Yaluk receives
            only the input file name, avoiding path parsing issues.
        :type solver_cwd: str | os.PathLike | None
        """
        solver_results = []
        solver_workdirs = set()
        today = date.today()
        casenname = f"C - LCC line for: {self.name}"
        for i, line in enumerate(self.Lines):

            fname = f"lcc_{i+1:03d}.dat"

            filename = Path(self.name) / Path(ruta) / fname
            filename.parent.mkdir(parents=True, exist_ok=True)
            with open(filename, "w", encoding="utf-8") as file:
                file.write("BEGIN NEW DATA CASE\n")
                file.write(
                    "C --------------------------------------------------------\n"
                )
                file.write("C -LCC data File-\n")
                file.write(f"C Date: {today}\n")
                file.write(casenname + "\n")
                file.write("C Generated by YALUK DRAW 2.0\n")
                file.write(
                    f"C --------------------------------------------------------\n"
                )
                file.write("JMARTI SETUP\n")
                file.write("$ERASE\n")
                file.write(
                    branch_card_lcc(
                        line.Configuration.Num_conductors, max_len=80
                    ).__str__()
                )
                file.write("LINE CONSTANTS\n")
                file.write("METRIC\n")
                for k in range(line.Configuration.Num_conductors):
                    cp = line.Configuration.Conductors._list[k]
                    file.write(conductor_card_lcc(k + 1, cp) + "\n")

                file.write("BLANK CARD ENDING CONDUCTOR CARDS\n")
                length_km = line.length / 1000.0
                file.write(
                    f"{soil_resistivity:8.2f}{Freq_mat:10.2e}{" ":<26}{length_km:8.4}{1:>6d}           1-9\n"
                )
                file.write(
                    f"{soil_resistivity:8.2f}{Freq_ss:10.2e}{" ":<26}{length_km:8.4}{1:>6d}           1-9\n"
                )
                file.write(
                    f"{soil_resistivity:8.2f}{freq_init:10.2e}{" ":<26}{length_km:8.4}{1:>6d}{decades:>4d}{points_decade:>3d}    1-9\n"
                )
                file.write("BLANK CARD ENDING FREQUENCY CARDS\n")
                file.write("BLANK CARD ENDING LINE CONSTANT\n")
                file.write("DEFAULT\n")
                file.write("$PUNCH\n")
                file.write("BLANK CARD ENDING JMARTI SETUP\n")
                file.write("BEGIN NEW DATA CASE\n")
                file.write("BLANK CARD\n")

            if run_solver:
                solver_workdirs.add(filename.resolve().parent)
                solver_results.append(
                    run_atp_solver(
                        filename,
                        solver_path=solver_path,
                        solver_cwd=solver_cwd,
                    )
                )
                check_required_output(filename.with_suffix(".pch"), "LCC punch")

            filename_dbm = filename.with_suffix(".dbm")
            filename_pch = filename.with_suffix(".pch")
            filename_lib = filename.with_suffix(".lib")
            print(f"Short path: {filename_lib}")
            with open(filename_dbm, "w", encoding="utf-8") as file:
                file.write("BEGIN NEW DATA CASE --NOSORT--\n")
                file.write(
                    "C --------------------------------------------------------\n"
                )
                file.write(
                    f"C -LCC punch File for line: {line.id} in network: {self.name}\n"
                )
                file.write(f"C Date: {today}\n")
                file.write("C Generated by YALUK DRAW 2.0\n")
                file.write(
                    f"C --------------------------------------------------------\n"
                )
                file.write("DATA BASE MODULE\n")
                file.write("$ERASE\n")
                file.write(
                    arg_card_lcc(
                        line.Configuration.Num_conductors, max_len=80
                    ).__str__()
                )
                file.write(f"$INCLUDE, {filename_pch.name}\n")
                file.write("BEGIN NEW DATA CASE\n")
                file.write(f"$PUNCH, {filename_lib.name}\n")
                file.write("BEGIN NEW DATA CASE\n")
                file.write("BLANK\n")
                file.write("BLANK\n")

            if run_solver:
                check_required_output(filename_pch, "LCC punch")
                check_required_output(filename_dbm, "LCC database module")
                solver_workdirs.add(filename_dbm.resolve().parent)
                solver_results.append(
                    run_atp_solver(
                        filename_dbm,
                        solver_path=solver_path,
                        solver_cwd=solver_cwd,
                    )
                )
                check_required_output(filename_lib, "LCC library")

        if run_solver:
            for directory in solver_workdirs:
                cleanup_solver_files(directory)
        if return_buffer:
            lccbuffer = self.get_lcc_lib_zipbuffer(filename.parent)
            return lccbuffer, solver_results
        return solver_results

    def get_lcc_lib_zipbuffer(self, base_path, current_buffer=None):

        base_path = Path(base_path)
        lcc_dir = base_path / "lcc"

        if not lcc_dir.exists():
            raise FileNotFoundError(f"{lcc_dir} not found")

        current_buffer = current_buffer if current_buffer is not None else io.BytesIO()

        with zipfile.ZipFile(
            current_buffer, "a", compression=zipfile.ZIP_DEFLATED
        ) as zf:

            for file_path in lcc_dir.glob("*.lib"):
                content = file_path.read_text(encoding="utf-8")

                # store inside zip under /lcc/
                zf.writestr(f"lcc/{file_path.name}", content)

        current_buffer.seek(0)
        return current_buffer

    from dataclasses import dataclass

    @dataclass
    class AtpSettings:
        """
        :param printfreq: Print frequency for ATP lis file output. Default is 999999 (no printing). Set to a positive integer to print every N steps.
        :type printfreq: int
        :param plotfreq: Plot frequency for ATP output. Default is 1 (every step). Set to a positive integer to plot every N steps.
        :type plotfreq: int
        :param pl4out: Plot4 output option for ATP file generation. If 1, a .pl4 file will be generated with the results. If 0, only a .lis file will be generated.
        :type pl4out: int
        :param NetwrkOut: Network output option for ATP lis file generation. If 1, network output will be printed in the .lis file. If 0, no network output will be printed.
        :type NetwrkOut: int
        :param SSPhasor: Print phasor option for ATP file generation. If 1, phasor information will be printed in the .lis file. If 0, no phasor information will be printed.
        :type SSPhasor: int
        :param MaxMinOut: Max/Min output option for ATP file generation. If 1, maximum and minimum values will be printed in the .lis file. If 0, no maximum or minimum values will be printed.
        :type MaxMinOut: int
        :param MemSave: Memory save option for ATP file generation. If 1, memory saving techniques will be applied in the ATP simulation. If 0, no memory saving techniques will be applied.
        :type MemSave: int
        :param ExtrPinOut: Extra print output option for ATP file generation. To be implemented in future versions. If 1, extra print output will be included in the .lis file. If 0, no extra print output will be included.
        :type ExtrPinOut: int
        :param Tmax: Simulation end time for the ATP run, in seconds. Default is 60e-6.
        :type Tmax: float
        :param Dt: Simulation time step for the ATP run, in seconds. Default is 2e-8.
        :type Dt: float
        """

        printfreq: int = 999999
        plotfreq: int = 1
        pl4out: int = 1
        NetwrkOut: int = 1
        SSPhasor: int = 1
        MaxMinOut: int = 1
        MemSave: int = 0
        ExtrPinOut: int = 0
        Tmax: float = 60e-6
        Dt: float = 2e-8

    def MakeATPBuffer(
        self,
        settings: AtpSettings = None,
        stroke: Lightning = None,
        distance_threshold: float = -1,
    ):
        if stroke is None:
            # Sin rayo no puede haber fuente de impacto directo: si se dejara el
            # direct_strike del rayo ANTERIOR (esta instancia se reutiliza entre
            # rayos), write_sources entra a la rama de impacto directo y
            # desreferencia stroke.Ih1 sobre None -> AttributeError. Solo se
            # llega aca al generar un ATP de diagnostico, sin rayo asociado.
            self.direct_strike = False
        else:
            self.check_direct_strike(
                stroke.X_location, stroke.Y_location, stroke.Ih1, distance_threshold
            )

            if not self.direct_strike:
                stroke = None
                print("* Impacto indirecto.")
                print(
                    f"  Distancia mínima al punto de impacto: {self.min_distance:.2f} m"
                )
                print(f"  Tensión de Rusck máximo calculado: {self.Vrusck_max:.2f} kV")
                print(
                    f"  Línea más cercana al punto de impacto: {self.line_ds.name if not self.line_ds==None else 'N/A'}"
                )
                lcc_counter = 0
                for line in self.Lines:
                    if line.isFDTD == True:
                        lcc_counter += 1
                print(
                    f"Número de líneas FDTD en la red: {lcc_counter}: {len(self.Lines)}"
                )

            else:
                print("** Impacto Directo incluido en ATP")
                print(
                    f"   Distancia mínima al punto de impacto: {self.min_distance:.2f} m"
                )
                print(
                    f"   Línea más cercana al punto de impacto: {self.line_ds.name if self.line_ds else 'N/A'}"
                )
                print(f"   Impacto directo: {self.direct_strike}")

        buffer = io.BytesIO()
        if settings is None:
            settings = self.AtpSettings()

        def write(text):
            buffer.write(text.encode("utf-8"))

        write_header(write, self, settings)
        write_models(write, self, settings)
        write_branches(write, self)
        write_sources(write, self, stroke)
        write_output(write, self)
        write_footer(write, self)
        buffer.seek(0)
        return buffer

    def MakeAtpFile(
        self,
        settings: AtpSettings = None,
        stroke: Lightning = None,
        distance_threshold: float = 0,
    ):

        if settings is None:
            settings = self.AtpSettings()
        buffer = self.MakeATPBuffer(settings, stroke, distance_threshold)
        file_name = Path(self.name) / f"{self.name}.atp"
        # crear carpeta si no existe
        file_name.parent.mkdir(parents=True, exist_ok=True)
        with open(file_name, "wb") as f:
            buffer.seek(0)
            f.write(buffer.read())

    def MakeAtpFile2(self, settings: AtpSettings):
        """
        Docstring for MakeAtpFile

        :param self: Description
        :param ruta: Description
        :type ruta: str
        :param printfreq: Print frequency for ATP lis file output. Default is 999999 (no printing). Set to a positive integer to print every N steps.
        :type printfreq: int
        :param plotfreq: Plot frequency for ATP output. Default is 1 (every step). Set to a positive integer to plot every N steps.
        :type plotfreq: int
        :param pl4out: Plot4 output option for ATP file generation. If 1, a .pl4 file will be generated with the results. If 0, only a .lis file will be generated.
        :type pl4out: int
        :param NetwrkOut: Network output option for ATP lis file generation. If 1, network output will be printed in the .lis file. If 0, no network output will be printed.
        :type NetwrkOut: int
        :param SSPhasor: Print phasor option for ATP file generation. If 1, phasor information will be printed in the .lis file. If 0, no phasor information will be printed.
        :type SSPhasor: int
        :param MaxMinOut: Max/Min output option for ATP file generation. If 1, maximum and minimum values will be printed in the .lis file. If 0, no maximum or minimum values will be printed.
        :type MaxMinOut: int
        :param MemSave: Memory save option for ATP file generation. If 1, memory saving techniques will be applied in the ATP simulation. If 0, no memory saving techniques will be applied.
        :type MemSave: int
        :param ExtrPinOut: Extra print output option for ATP file generation. To be implemented in future versions. If 1, extra print output will be included in the .lis file. If 0, no extra print output will be included.
        :type ExtrPinOut: int
        """
        max_len = 80
        today = date.today()
        os.makedirs(f"{self.name}", exist_ok=True)
        filename = f"{self.name}/{self.name}.atp"
        with open(filename, "w", encoding="utf-8") as file:
            if self.direct_strike == True:
                self.num_lines_FDTD = 0
            else:
                self.num_lines_FDTD = 0
                for line in self.Lines:
                    if line.isFDTD:
                        self.num_lines_FDTD += 1
                # file.write(f"**TEST lines: {self.num_lines_FDTD}\n")
            # with open(filename, "w", encoding="utf-8") as file:
            file.write("BEGIN NEW DATA CASE\n")
            file.write("C --------------------------------------------------------\n")
            file.write(f"C Date: {today}\n")
            file.write("C Generated by YALUK DRAW 2.0 python\n")
            file.write("C Developed by: Ernesto Pérez G\n")
            file.write("C eperezg@unal.edu.co\n")
            file.write("C Universidad Nacional de Colombia\n")
            file.write("C --------------------------------------------------------\n")
            file.write("C  dT  >< Tmax >< Xopt >< Copt >\n")
            file.write(f"{self.Dt:>8.2E}{self.Tmax:>8.2E}\n")
            # file.write(f"{plotfreq:08d} 1       1       1       1       0       0       0       0\n")
            # Options output files
            file.write(
                f"{settings.printfreq:8d}{settings.plotfreq:8d}{settings.NetwrkOut:8d}{settings.SSPhasor:8d}{settings.MaxMinOut:8d}{settings.ExtrPinOut:8d}{settings.MemSave:8d}{settings.pl4out:8d}       0\n"
            )
            if self.direct_strike == False:
                file.write("C ATP File for Induced Voltages Model\n")
                # Models definition for lines with FDTD
                file.write("/MODELS\n")
                file.write("MODELS\n")
                file.write("INPUT\n")
                # Inputs
                for i in range(len(self.Nodes)):
                    node = self.Nodes[i]
                    for j in range(node.Num_conductors):
                        ph = node.Phases_id[j]
                        file.write(f"M{node.idx:04d}{ph}  {{v(N{node.idx:04d}{ph})}}\n")
                # Outputs for FDTD
                if self.num_lines_FDTD > 0:
                    file.write("OUTPUT\n")
                    for linea in self.Lines:
                        if linea.isFDTD:
                            for j in range(len(linea.Phases_connected)):
                                file.write(
                                    f"   L{linea.idx:04d}{linea.Phases_connected[j].value}\n"
                                )
                                file.write(
                                    f"   R{linea.idx:04d}{linea.Phases_connected[j].value}\n"
                                )
                # Models definition per number of conductors

                try:
                    max_conductor = max([n.Num_conductors for n in self.Nodes])
                except ValueError:
                    max_conductor = 0

                file.write("MODEL Yaluk1\n")
                file.write(
                    " -- This model is link with ATP by means of a iluminated line characteristic method\n"
                )
                file.write(
                    " -- It must have four inputs for one single line (Va,Ia,Vb,Ib)\n"
                )
                file.write("CONST\n")
                file.write("cond {VAL:1} --num. phases\n")
                file.write("INPUT\n")
                file.write("  Va[1..cond]\n")
                file.write("  Vb[1..cond]\n")
                file.write("VAR Vfa[1..cond],Vfb[1..cond]\n")
                file.write("OUTPUT\n")
                file.write("   Vfa,Vfb\n")
                file.write("DATA\n")
                file.write("	No_Lin\n")
                file.write(
                    "MODEL yaluk_f FOREIGN YALUK_DLL_MODEL {ixdata:4, ixin:3, ixout:2, ixvar:200}\n"
                )
                file.write("EXEC -- using the DLL subroutine\n")
                file.write("  USE yaluk_f AS yaluk_f\n")
                file.write("    DATA xdata[1..4]:=[timestep,stoptime,cond,No_Lin]\n")
                file.write("    INPUT xin[1..2*cond+1]:=[t,Va[1..cond],Vb[1..cond]]\n")
                file.write("    OUTPUT 	Vfa[1..cond]:=xout[1..cond]\n")
                file.write("		Vfb[1..cond]:=xout[cond+1..2*cond]\n")
                file.write("  ENDUSE\n")
                file.write("  ENDEXEC\n")
                file.write("ENDMODEL\n")
                file.write("MODEL Yaluk2\n")
                file.write(
                    " -- This model is link with ATP by means of a iluminated line characteristic method\n"
                )
                file.write(
                    " -- It must have four inputs for one single line (Va,Ia,Vb,Ib)\n"
                )
                file.write("CONST\n")
                file.write("cond {VAL:2} --num. phases\n")
                file.write("INPUT\n")
                file.write("  Va[1..cond]\n")
                file.write("  Vb[1..cond]\n")
                file.write("VAR Vfa[1..cond],Vfb[1..cond]\n")
                file.write("OUTPUT\n")
                file.write("   Vfa,Vfb\n")
                file.write("DATA\n")
                file.write("	No_Lin\n")
                file.write(
                    "MODEL yaluk_f FOREIGN YALUK_DLL_MODEL {ixdata:4, ixin:5, ixout:4, ixvar:200}\n"
                )
                file.write("EXEC -- using the DLL subroutine\n")
                file.write("  USE yaluk_f AS yaluk_f\n")
                file.write("    DATA xdata[1..4]:=[timestep,stoptime,cond,No_Lin]\n")
                file.write("    INPUT xin[1..2*cond+1]:=[t,Va[1..cond],Vb[1..cond]]\n")
                file.write("  --    HISTORY histdef(xvar[1]):=0\n")
                file.write("    OUTPUT 	Vfa[1..cond]:=xout[1..cond]\n")
                file.write("		Vfb[1..cond]:=xout[cond+1..2*cond]\n")
                file.write("  ENDUSE\n")
                file.write("  ENDEXEC\n")
                file.write("ENDMODEL\n")
                file.write("MODEL Yaluk3\n")
                file.write(
                    " -- This model is link with ATP by means of a iluminated line characteristic method\n"
                )
                file.write(
                    " -- It must have four inputs for one single line (Va,Ia,Vb,Ib)\n"
                )
                file.write("CONST\n")
                file.write("cond {VAL:3} --num. phases\n")
                file.write("INPUT\n")
                file.write("  Va[1..cond]\n")
                file.write("  Vb[1..cond]\n")
                file.write("VAR Vfa[1..cond],Vfb[1..cond]\n")
                file.write("OUTPUT\n")
                file.write("   Vfa,Vfb\n")
                file.write("DATA\n")
                file.write("	No_Lin\n")
                file.write(
                    "MODEL yaluk_f FOREIGN YALUK_DLL_MODEL {ixdata:4, ixin:7, ixout:6, ixvar:200}\n"
                )
                file.write("EXEC -- using the DLL subroutine\n")
                file.write("  USE yaluk_f AS yaluk_f\n")
                file.write("    DATA xdata[1..4]:=[timestep,stoptime,cond,No_Lin]\n")
                file.write("    INPUT xin[1..2*cond+1]:=[t,Va[1..cond],Vb[1..cond]]\n")
                file.write("  --    HISTORY histdef(xvar[1]):=0\n")
                file.write("    OUTPUT 	Vfa[1..cond]:=xout[1..cond]\n")
                file.write("		Vfb[1..cond]:=xout[cond+1..2*cond]\n")
                file.write("  ENDUSE\n")
                file.write("  ENDEXEC\n")
                file.write("ENDMODEL\n")
                file.write("MODEL Yaluk4\n")
                file.write(
                    " -- This model is link with ATP by means of a iluminated line characteristic method\n"
                )
                file.write(
                    " -- It must have four inputs for one single line (Va,Ia,Vb,Ib)\n"
                )
                file.write("CONST\n")
                file.write("cond {VAL:4} --num. phases\n")
                file.write("INPUT\n")
                file.write("  Va[1..cond]\n")
                file.write("  Vb[1..cond]\n")
                file.write("VAR Vfa[1..cond],Vfb[1..cond]\n")
                file.write("OUTPUT\n")
                file.write("   Vfa,Vfb\n")
                file.write("DATA\n")
                file.write("	No_Lin\n")
                file.write(
                    "MODEL yaluk_f FOREIGN YALUK_DLL_MODEL {ixdata:4, ixin:9, ixout:8, ixvar:200}\n"
                )
                file.write("EXEC -- using the DLL subroutine\n")
                file.write("  USE yaluk_f AS yaluk_f\n")
                file.write("    DATA xdata[1..4]:=[timestep,stoptime,cond,No_Lin]\n")
                file.write("    INPUT xin[1..2*cond+1]:=[t,Va[1..cond],Vb[1..cond]]\n")
                file.write("  --    HISTORY histdef(xvar[1]):=0\n")
                file.write("    OUTPUT 	Vfa[1..cond]:=xout[1..cond]\n")
                file.write("		Vfb[1..cond]:=xout[cond+1..2*cond]\n")
                file.write("  ENDUSE\n")
                file.write("  ENDEXEC\n")
                file.write("ENDMODEL\n")
                # Use models for lines
                if self.num_lines_FDTD > 0:
                    for Linea in self.Lines:

                        if linea.isFDTD:
                            file.write(
                                f"USE Yaluk{Linea.Configuration.Num_conductors} AS Yaluk{Linea.Configuration.Num_conductors:04d}\n"
                            )
                            file.write("INPUT\n")
                            for i in range(Linea.Configuration.Num_conductors):
                                file.write(
                                    f"  Va[{i+1}]:=M{Linea.Node_i.idx:04d}{Linea.Phases_connected[i].value}\n"
                                )
                            for i in range(Linea.Configuration.Num_conductors):
                                file.write(
                                    f"  Vb[{i+1}]:=M{Linea.Node_j.idx:04d}{Linea.Phases_connected[i].value}\n"
                                )
                            file.write("DATA\n")
                            file.write(f"  No_Lin:={Linea.idx}\n")
                            file.write("OUTPUT\n")
                            for i in range(Linea.Configuration.Num_conductors):
                                file.write(
                                    f"  L{Linea.idx:04d}{Linea.Phases_connected[i].value}:=Vfa[{i+1}]\n"
                                )
                            for i in range(Linea.Configuration.Num_conductors):
                                file.write(
                                    f"  R{Linea.idx:04d}{Linea.Phases_connected[i].value}:=Vfb[{i+1}]\n"
                                )
                            file.write("ENDUSE\n")
                file.write("ENDMODELS\n")
            else:
                file.write("C ATP File for Direct Strike Model\n")

            # Branches (simplified)
            file.write("/BRANCH\n")
            file.write("C < n1 >< n2 ><ref1><ref2>< R  >< A  >< B  >\n")
            for Linea in self.Lines:
                if Linea.isFDTD:
                    for i in range(Linea.Configuration.Num_conductors):
                        DevNum = f"5{(i+1)}"
                        # file.write(f"{DevNum:2d}N{Linea.Node_i.idx:04d}{Linea.Phases_connected[i].value}L{Linea.idx:04d}{Linea.Phases_connected[i].value}            {Linea.Configuration.Zc[0,0]:6.1f}
                        #                                                         0\n")
                        file.write(
                            f"{DevNum}"
                            f"N{Linea.Node_i.idx:04d}"
                            f"{Linea.Phases_connected[i].value}"
                            f"L{Linea.idx:04d}"
                            f"{Linea.Phases_connected[i].value}"
                            f"{'':12}"
                            f"{Linea.Configuration.Zc[i, 0]:06.1f}"
                        )

                        for j in range(1, i + 1):
                            test_line = (j + 1) % 3

                            if test_line == 1:
                                # Create a new line
                                file.write(
                                    f"\n{'':26}" f"{Linea.Configuration.Zc[i, j]:06.1f}"
                                )
                            else:
                                file.write(
                                    f"{'':12}" f"{Linea.Configuration.Zc[i, j]:06.1f}"
                                )

                        file.write("\n")

                    for i in range(Linea.Configuration.Num_conductors):
                        # file.write(f"  N{Linea.Node_j.idx:04d}{Linea.Phases_connected[i].value}R{Linea.idx:04d}{Linea.Phases_connected[i].value}            {440.2:6.1f}                                               0\n")
                        DevNum = f"5{(i+1)}"
                        # file.write(f"{DevNum:2d}N{Linea.Node_i.idx:04d}{Linea.Phases_connected[i].value}L{Linea.idx:04d}{Linea.Phases_connected[i].value}            {Linea.Configuration.Zc[0,0]:6.1f}
                        #                                                         0\n")
                        file.write(
                            f"{DevNum}"
                            f"N{Linea.Node_j.idx:04d}"
                            f"{Linea.Phases_connected[i].value}"
                            f"R{Linea.idx:04d}"
                            f"{Linea.Phases_connected[i].value}"
                            f"{'':12}"
                            f"{Linea.Configuration.Zc[i, 0]:06.1f}"
                        )

                        for j in range(1, i + 1):
                            test_line = (j + 1) % 3

                            if test_line == 1:
                                # Create a new line
                                file.write(
                                    f"\n{'':26}" f"{Linea.Configuration.Zc[i, j]:06.1f}"
                                )
                            else:
                                file.write(
                                    f"{'':12}" f"{Linea.Configuration.Zc[i, j]:06.1f}"
                                )

                        file.write("\n")
            # writing lumped elements

            for E in self.Shunt_elements:
                E.write_atp_file(file)
            # writing transformers
            for T in self.Transformers:
                T.write_atp_file(file)
            # writing surge arresters
            for SA in self.SurgeArresters:
                SA.write_atp_file(file)
            # writing LCC lines
            for Linea in self.Lines:

                if not Linea.isFDTD:
                    lcc_filename = f"lcc/lcc_{Linea.idx:03d}.lib"
                    lcc_line = ""
                    token = f"$INCLUDE, {lcc_filename}"
                    lcc_line += token
                    for ph in Linea.Phases_connected:
                        token = f"N{Linea.Node_i.idx:04d}{ph.value}"
                        if len(lcc_line) + len(token) > (max_len - 3):
                            lcc_line += ","
                            lcc_line = lcc_line.ljust(78) + "$$\n"
                            file.write(lcc_line)
                            lcc_line = "  " + token
                        else:
                            lcc_line += "," + token
                    file.write(lcc_line + "\n")
            # SOURCES
            file.write("/SOURCE\n")
            file.write(
                "C < n 1><>< Ampl.  >< Freq.  ><Phase/T0><   A1   ><   T1   >< TSTART >< TSTOP  >\n"
            )
            for Linea in self.Lines:
                if Linea.isFDTD:
                    CARD_BODY = "                                                             0      1.E3\n"
                    for phase in Linea.Phases_connected:
                        file.write(f"60L{Linea.idx:04d}{phase.value}{CARD_BODY}")
                        file.write(f"60R{Linea.idx:04d}{phase.value}{CARD_BODY}")
            # OUTPUT
            file.write("/OUTPUT\n")
            c_line = "  "
            for Node in self.Nodes:
                for i in range(Node.Num_conductors):
                    ph = Node.Phases_id[i]
                    token = f"N{Node.idx:04d}{ph}"
                    if len(c_line) + len(token) > max_len:
                        file.write(f"{c_line}\n")
                        c_line = "  " + token
                    else:
                        c_line += token
            file.write(f"{c_line}\n")
            file.write("C ENDING DIRECTIVES\n")
            file.write("BLANK MODELS\n")
            file.write("BLANK BRANCH\n")
            file.write("BLANK SWITCH\n")
            file.write("BLANK SOURCE\n")
            file.write("BLANK OUTPUT\n")
            file.write("BLANK PLOT\n")
            file.write("BEGIN NEW DATA CASE\n")
            file.write("BLANK\n")

    def Save(self, path: str):
        self.create_Dataframes()
        self.df_nodes.to_csv(f"{path}{self.name}_nodes.csv", index=False)
        self.df_lines.to_csv(f"{path}{self.name}_lines.csv", index=False)
        filename = f"{path}{self.name}.stcx"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Network: {self.name}\n")
            f.write(f"Description: {self.Description}\n")
            f.write(f"Tmax: {self.Tmax}\n")
            f.write(f"Dt: {self.Dt}\n")
            f.write(f"Dx: {self.Dx}\n")
            f.write(f"NumNodes: {len(self.Nodes)}\n")
            f.write(f"NumLines: {len(self.Lines)}\n")

    def Load(self, file: str):
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
        for line in content.splitlines():
            if line.startswith("Network: "):
                self.nme = line.split("Network: ", 1)[1]
            if line.startswith("Description: "):
                self.Description = line.split("Description: ", 1)[1]

    def check_direct_strike(self, X, Y, Imax, threshold_distance=0):
        """Check if the lightning strike is a direct strike to any line in the network. If it is a direct strike, return True and the line that is directly struck. If it is not a direct strike, return False and the line that is closest to the strike point, along with the maximum Rusck voltage calculated for that line and the minimum distance to that line.
        :param X: X coordinate of the lightning strike point
        :param Y: Y coordinate of the lightning strike point
        :param Imax: Maximum current of the lightning strike
        :param threshold_distance: Distancia de corte para decidir el modelo de linea:
            <= threshold_distance -> FDTD (onda viajera); mayor -> LCC (parametros
            concentrados). NO participa en la decision de impacto directo/indirecto
            (esa la decide Line.check_direct_strike via los radios Rs/Rg) ni en el
            calculo de Vrusck (ver mas abajo).
        :return: direct_strike (bool), Vrusck_max (float), min_distance (float), line_name (str)
        """
        self.direct_strike = False
        self.line_ds = None
        line_name = None
        self.Vrusck_max = 0
        self.min_distance = 9999999

        if threshold_distance <= 100:
            threshold_distance = 9999999  # [m] if the threshold distance is not specified or is too small, we consider all lines for FDTD

        for line in self.Lines:
            ds, distance = line.check_direct_strike(X, Y, Imax)
            if ds:
                self.direct_strike = True
                self.line_ds = line
                line_name = line.id
                self.Vrusck_max = 0
                self.min_distance = distance
                # Update all lines to not be FDTD since we are modeling a direct strike
                for line_i in self.Lines:
                    line_i.isFDTD = False
                return self.direct_strike, self.Vrusck_max, self.min_distance, line_name
            else:
                hm = line.Configuration.get_max_height()
                velocity = (
                    self.Channel_settings.Velocity
                    if self.Channel_settings is not None
                    else _DEFAULT_CHANNEL_VELOCITY
                )
                beta = velocity / _SPEED_OF_LIGHT
                beta_factor = beta / math.sqrt(1 - beta**2)
                Vrusck = _RUSCK_K * beta_factor * Imax / 1e3 * hm / distance
                self.Vrusck_max = max(self.Vrusck_max, Vrusck)
                if distance < self.min_distance:
                    self.line_ds = line
                    line_name = line.id
                self.min_distance = min(self.min_distance, distance)
                # Checking if the line is within the threshold distance
                if distance <= threshold_distance:
                    line.isFDTD = True
                else:
                    line.isFDTD = False

        return self.direct_strike, self.Vrusck_max, self.min_distance, line_name

    def create_dataframes(self):
        import pandas as pd

        self.df_nodes = pd.DataFrame(
            {
                "Node_id": [node.id for node in self.Nodes],
                "Node_idx": [node.idx for node in self.Nodes],
                "Name": [node.name for node in self.Nodes],
                "X": [node.Location_X for node in self.Nodes],
                "Y": [node.Location_Y for node in self.Nodes],
                "Phases": [node.Phases_id for node in self.Nodes],
                "transformers": [node.Transformers for node in self.Nodes],
                "surge_arresters": [node.SurgeArresters for node in self.Nodes],
                "lat": [node.GeoLocation.Lat for node in self.Nodes],
                "long": [node.GeoLocation.Lng for node in self.Nodes],
            }
        )
        self.df_lines = pd.DataFrame(
            {
                "Line_id": [line.id for line in self.Lines],
                "Line_idx": [line.idx for line in self.Lines],
                "name": [line.name for line in self.Lines],
                "Node_i": [line.Node_i.name for line in self.Lines],
                "Node_j": [line.Node_j.name for line in self.Lines],
                "Xi": [line.Node_i.Location_X for line in self.Lines],
                "Yi": [line.Node_i.Location_Y for line in self.Lines],
                "Xj": [line.Node_j.Location_X for line in self.Lines],
                "Yj": [line.Node_j.Location_Y for line in self.Lines],
                "lat_i": [line.Node_i.GeoLocation.Lat for line in self.Lines],
                "long_i": [line.Node_i.GeoLocation.Lng for line in self.Lines],
                "lat_j": [line.Node_j.GeoLocation.Lat for line in self.Lines],
                "long_j": [line.Node_j.GeoLocation.Lng for line in self.Lines],
                "hmax": [line.Configuration.get_max_height() for line in self.Lines],
                "FTD": [line.isFDTD for line in self.Lines],
                "direct_strike": [line.isDirectStrike for line in self.Lines],
                "Num_conductors": [
                    line.Configuration.Num_conductors for line in self.Lines
                ],
                "Length": [line.length for line in self.Lines],
            }
        )
