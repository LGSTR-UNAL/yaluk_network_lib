from typing import List, Optional
from .Node import PhaseName
import io
class IShunt_element:
    def write_atp_file(self, file: io.TextIOBase): raise NotImplementedError()
class lumped_element:
    def __init__(self): self._cap=0.0; self._ind=0.0; self.Resistance=0.0
    @property
    def Inductance(self): return self._ind*1e3
    @Inductance.setter
    def Inductance(self,v): self._ind=v
    @property
    def Capacitance(self): return self._cap*1e6
    @Capacitance.setter
    def Capacitance(self,v): self._cap=v

class Shunt_lump(IShunt_element):
    def __init__(self, E: Optional[lumped_element]=None, Ni=None, P: Optional[PhaseName]=None):
        self.Node = Ni; self.SolidGrounded=True; self.Phases_connected=[]; self.Lumped_elements=[]
        if E is not None: self.Lumped_elements.append(E)
        if P is not None: self.Phases_connected.append(P)
    def Add(self, E, P):
        if (len(self.Lumped_elements) < (self.Node.Num_conductors if self.Node else 0)) and (P in (self.Node.Phases_id if self.Node else [])):
            self.Lumped_elements.append(E); self.Phases_connected.append(P); return len(self.Lumped_elements)
        return 0
    def write_atp_file(self, write):
        for le,ph in zip(self.Lumped_elements, self.Phases_connected):
            write(f"SHUNT {self.Node.id}{ph.value} R={le.Resistance} C={le.Capacitance} L={le.Inductance}\n")
