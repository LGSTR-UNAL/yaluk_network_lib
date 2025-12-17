from typing import List, Optional
from .Node import PhaseName, Node, Element_id
class Transformer(Element_id):
    def __init__(self, CHV=None, CLV=None, CHL=None, ground=None, NHV:Node=None, NLV:Node=None, *phases):
        super().__init__()
        self.NodeHV = NHV; self.NodeLV = NLV; self._hv=CHV or 0.0; self._lv=CLV or 0.0; self._hl=CHL or 0.0
        self.Phases_connected = [p for p in phases if isinstance(p, PhaseName)]
        self.G_Resistance = ground or 0.0
    @property
    def HV_Capacitance(self): return (self._hv or 0.0)*1e6
    def write_atp_file(self, file):
        for ph in self.Phases_connected:
            file.write(f"TRF {self.NodeHV.id}{ph.value}->{self.NodeLV.id}{ph.value} HVcap={self.HV_Capacitance}\n")
