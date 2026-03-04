from typing import List
from enum import Enum
from .IdentifiedObject import IdentifyObject
from .Node import Node, PhaseName


# Assumes these exist in your project
# from network_library import Node, PhaseName, Element_id
def decode_phases(mask: int):
    phases = []
    if mask % 10 == 1:
        phases.append(PhaseName.A)
    if (mask // 10) % 10 == 1:
        phases.append(PhaseName.B)
    if (mask // 100) % 10 == 1:
        phases.append(PhaseName.C)
    return phases


class Transformer(IdentifyObject):
    """
    Object transformer of two winding
    """

    def __init__(
        self,
        CHV: float = None,
        CLV: float = None,
        CHL: float = None,
        ground: float = None,
        NHV=None,
        NLV=None,
        phases=None,
    ):
        """
        This constructor covers all C# overloads by using defaults + *phases.
        """

        super().__init__()

        # Nodes
        self.NodeHV = NHV
        self.NodeLV = NLV

        # Internal (stored in Farads, exposed in microfarads)
        self._hv_cap = 0.0
        self._lv_cap = 0.0
        self._hl_cap = 0.0

        # Other properties
        self.G_Resistance: float = 0.0
        self.NumberUsers: int = 0

        # Phases
        self.Phases_connected: List[Enum] = []

        # Default constructor behavior
        if CHV is None:
            self._hv_cap = 340e-12
            self._lv_cap = 215e-12
            self._hl_cap = 744e-12
            self.G_Resistance = 10.0
            return

        # Populate common fields
        self._transformer_populate(CHV, CLV, CHL, ground, NHV, NLV)

        # Phase handling (single, double, or three phase)
        if phases is None:
            # Default to three-phase if not specified
            self.Phases_connected.extend([PhaseName.A, PhaseName.B, PhaseName.C])
        elif isinstance(phases, int):
            # If an integer mask is provided, decode it
            self.Phases_connected.extend(decode_phases(phases))
        elif isinstance(phases, list):
            # If a list of phases is provided, use it directly
            self.Phases_connected.extend(phases)

    # ------------------------------------------------------------------
    # Internal population logic (maps Transformer_populate)
    # ------------------------------------------------------------------
    def _transformer_populate(
        self, CHV: float, CLV: float, CHL: float, ground: float, NHV, NLV
    ):
        self.Phases_connected = []
        self.HV_Capacitance = CHV
        self.LV_Capacitance = CLV
        self.HL_Capacitance = CHL
        self.G_Resistance = ground
        self.NodeHV = NHV
        self.NodeLV = NLV

    # ------------------------------------------------------------------
    # Capacitance properties (µF externally, F internally)
    # ------------------------------------------------------------------
    @property
    def HV_Capacitance(self) -> float:
        return self._hv_cap * 1e6

    @HV_Capacitance.setter
    def HV_Capacitance(self, value: float):
        self._hv_cap = value

    @property
    def LV_Capacitance(self) -> float:
        return self._lv_cap * 1e6

    @LV_Capacitance.setter
    def LV_Capacitance(self, value: float):
        self._lv_cap = value

    @property
    def HL_Capacitance(self) -> float:
        return self._hl_cap * 1e6

    @HL_Capacitance.setter
    def HL_Capacitance(self, value: float):
        self._hl_cap = value

    # ------------------------------------------------------------------
    # ATP file writer (EXACT formatting preserved)
    # ------------------------------------------------------------------
    def write_atp_file(self, file):
        """
        Writes ATP shunt transformer cards.
        """

        for phase in self.Phases_connected:

            file.write(
                f"  {self.NodeHV.id}{phase.value}{self.NodeLV.id}{phase.value}"
                f"                        {self.HL_Capacitance:6.0E}                                   0\n"
            )

            file.write(
                f"  {self.NodeHV.id}{phase.value}{self.NodeHV.id}{PhaseName.N.value}"
                f"                        {self.HV_Capacitance:6.0E}                                   0\n"
            )

            file.write(
                f"  {self.NodeLV.id}{phase.value}{self.NodeHV.id}{PhaseName.N.value}"
                f"                        {self.LV_Capacitance:6.0E}                                   0\n"
            )
        if not self.NodeHV.SurgeArresters:
            file.write(
                f"  {self.NodeHV.id}{PhaseName.N.value}"
                f"                  {self.NodeHV.RPAT:6.1f}                                               0\n"
            )
