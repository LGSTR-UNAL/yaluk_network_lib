import os
from sys import prefix
import token
from typing import List, Optional
import math, io
from pathlib import Path

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
from .LCC_cards import branch_card_lcc, conductor_card_lcc
from .GeoTransform import CoordTransf, PointLatLng, PointXY
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Network(IdentifyObject):
    InitLatLong: PointLatLng = field(
        default_factory=lambda: PointLatLng(6.1924, -75.3979)
    )
    InitXY: PointXY = field(default_factory=lambda: PointXY(0.0, 0.0))
    Tmax: float = 30e-6
    Dt: float = 2e-8
    Dx: float = 10.0
    Dmax_induction: float = 0.0
    num_lines_FDTD: int = 0
    Lines: LineCollection = field(default_factory=LineCollection)
    Nodes: NodeCollection = field(default_factory=NodeCollection)
    Transformers: TrfCollection = field(default_factory=TrfCollection)
    Shunt_elements: List[IShunt_element] = field(default_factory=list)
    SurgeArresters: List[SurgeArrester] = field(default_factory=list)

    class output:
        def __init__(self, error=False, id_str="", index=0):
            self.error = error
            self.id = id_str
            self.index = index

    def Init(self):
        geo_transform = CoordTransf()
        x, y = geo_transform.to_projected(self.InitLatLong.Lat, self.InitLatLong.Lng)
        self.InitXY = PointXY(x, y)
        self.Lines = LineCollection()
        self.Nodes = NodeCollection()
        self.Transformers = TrfCollection()
        self.Shunt_elements = []
        self.SurgeArresters = []
        self.Tmax = 30e-6
        self.Dt = 2e-8
        self.Dx = 10.0

    def AddNode(self, X, Y, Nodeidx=None, ctype="rel", label=None):
        """Add a node to the network at coordinates (X,Y) in meters from the initial location.
        If Nodeidx is provided, it will be used as the index for the new node (max 4 characters).
        Otherwise, the index will be automatically assigned based on the number of existing nodes.
        ctype: "rel" for relative to initial location, "abs" for absolute from the initial location
        label: optional label for the node
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
            newNode = Node(self.InitLatLong)
            if ctype == "abs":
                newNode.Location_X = X - self.InitXY.X
                newNode.Location_Y = Y - self.InitXY.Y
            else:
                newNode.Location_X = X
                newNode.Location_Y = Y
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
        if len(Linea.Phases_connected) > 3:
            for ii in range(3, len(Linea.Phases_connected)):
                Linea.Phases_connected[ii] = PhaseName.N
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
        i = self.Nodes.GetByIdx(Ni)
        if i is not None:
            i.Shunt_elements.append(E)
        return 1

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
            NHV = self.Nodes.GetByIdx(NHV)
        elif isinstance(NHV, str):
            NHV = self.Nodes.Find(lambda n: n.id == NHV)
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

    def MakeLineFiles(self, ruta: str = "CaseFiles/"):
        os.makedirs(ruta, exist_ok=True)
        for i, line in enumerate(self.Lines):
            filename = f"{ruta}linea_{i+1:03d}.txt"
            with open(filename, "w", encoding="utf-8") as file:
                file.write(
                    f"{line.Configuration.Conductors._list[0].Conduct.Radio}              Radio del conductor\n"
                )
                file.write(
                    f"{line.Node_i.Location_X}   {line.Node_i.Location_Y}            % Posición del extremo A en XA0   YA0\n"
                )
                file.write(
                    f"{line.Node_j.Location_X}   {line.Node_j.Location_Y}            % Posición del extremo B en XA0   YA0\n"
                )
                for j in range(line.Configuration.Num_conductors):
                    cp = line.Configuration.Conductors._list[j]
                    file.write(
                        f"{cp.Height}   {cp.Conduct.Resistance}            % Height [m] and Resistance [Ohm/km]\n"
                    )
                    file.write(
                        f"{cp.Relative_X_location}             % Relative position\n"
                    )

    def MakeLccFile(
        self,
        ruta: str = "lcc",
        soil_resistivity: float = 100.0,
        Freq_mat: float = 1e3,
        Freq_ss: float = 1e6,
        freq_init: float = 100.0,
        decades: int = 6,
        points_decade: int = 10,
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
        """
        today = date.today()
        casenname = f"C - LCC line for: {self.name}"
        for i, line in enumerate(self.Lines):

            fname = f"lcc_{i+1:03d}.dat"
            filename = Path(ruta) / fname
            filename.parent.mkdir(parents=True, exist_ok=True)
            with open(filename, "w", encoding="utf-8") as file:
                file.write(f"Line {i+1}\n")

                with open(filename, "w", encoding="utf-8") as file:
                    file.write("BEGIN NEW DATA CASE\n")
                    file.write(
                        "C --------------------------------------------------------\n"
                    )
                    file.write("C -LCC data File-\n")
                    file.write(f"C Date: {today}\n")
                    file.write(casenname)
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
                    file.write("METRIC\n")
                    for k in range(line.Configuration.Num_conductors):
                        cp = line.Configuration.Conductors._list[k]
                        file.write(conductor_card_lcc(k + 1, cp) + "\n")

                    file.write("BLANK CARD ENDING CONDUCTOR CARDS\n")
                    file.write(
                        f"{soil_resistivity:8.2f}{Freq_mat:10.2e}{" ":<26}{line.length:8.4}{1:>6d}           1-9\n"
                    )
                    file.write(
                        f"{soil_resistivity:8.2f}{Freq_ss:10.2e}{" ":<26}{line.length:8.4}{1:>6d}           1-9\n"
                    )
                    file.write(
                        f"{soil_resistivity:8.2f}{freq_init:10.2e}{" ":<26}{line.length:8.4}{1:>6d}{decades:>4d}{points_decade:>3d}    1-9\n"
                    )
                    file.write("BLANK CARD ENDING FREQUENCY CARDS\n")
                    file.write("BLANK CARD ENDING LINE CONSTANT\n")
                    file.write("DEFAULT\n")
                    file.write("$PUNCH\n")
                    file.write("BLANK CARD ENDING JMARTI SETUP\n")
                    file.write("BEGIN NEW DATA CASE\n")
                    file.write("BLANK CARD\n")

    def MakeAtpFile(
        self,
        ruta: str = "",
        direct_strike: bool = False,
        printfreq: int = 999999,
        plotfreq: int = 1,
        pl4out: int = 1,
        NetwrkOut: int = 1,
        SSPhasor: int = 1,
        MaxMinOut: int = 1,
        MemSave: int = 0,
        ExtrPinOut: int = 0,
    ):
        """
        Docstring for MakeAtpFile

        :param self: Description
        :param ruta: Description
        :type ruta: str
        :param direct_strike: Direct strike option for ATP file generation. If True, no lines will be considered for FDTD modeling.
        :type direct_strike: bool
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
        filename = f"{ruta}{self.name}.atp"
        with open(filename, "w", encoding="utf-8") as file:
            if direct_strike == True:
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
                f"{printfreq:8d}{plotfreq:8d}{NetwrkOut:8d}{SSPhasor:8d}{MaxMinOut:8d}{ExtrPinOut:8d}{MemSave:8d}{pl4out:8d}       0\n"
            )
            if direct_strike == False:
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
                        file.write(
                            f"M{node.idx:04d}{ph.value}  {{v(N{node.idx:04d}{ph.value})}}\n"
                        )
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
                for j in range(1, max_conductor + 1):
                    file.write(f"MODEL Yaluk{j}\n")
                    file.write(
                        " -- This model is link with ATP by means of a iluminated line characteristic method\n"
                    )
                    file.write(
                        " -- It must have four inputs for one single line (Va,Ia,Vb,Ib)\n"
                    )
                    file.write("CONST\n")
                    file.write(f"cond {{VAL:{j}}} --num. phases\n")
                    file.write("INPUT\n")
                    file.write("  Va[1..cond]\n")
                    file.write("  Vb[1..cond]\n")
                    file.write("VAR Vfa[1..cond],Vfb[1..cond]\n")
                    file.write("OUTPUT\n")
                    file.write("   Vfa,Vfb\n")
                    file.write("DATA\n")
                    file.write("    No_Lin\n")
                    file.write(
                        "MODEL yaluk_f FOREIGN YALUK_DLL_MODEL {ixdata:4, ixin:3, ixout:2, ixvar:200}\n"
                    )
                    file.write("EXEC -- using the DLL subroutine\n")
                    file.write("  USE yaluk_f AS yaluk_f\n")
                    file.write(
                        "    DATA xdata[1..4]:=[timestep,stoptime,cond,No_Lin]\n"
                    )
                    file.write(
                        "    INPUT xin[1..2*cond+1]:=[t,Va[1..cond],Vb[1..cond]]\n"
                    )
                    file.write("    OUTPUT Vfa[1..cond]:=xout[1..cond]\n")
                    file.write("        Vfb[1..cond]:=xout[cond+1..2*cond]\n")
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
            c_line = ""
            for Node in self.Nodes:
                for i in range(Node.Num_conductors):
                    ph = Node.Phases_id[i]
                    token = f"N{Node.idx:04d}{ph.value}"
                    if len(c_line) + len(token) > max_len:
                        file.write(f"{c_line}\n")
                        c_line = token
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
