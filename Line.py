from typing import Optional, List
from .Node import PhaseName, Node
from .Configuration_Type import Configuration_Type
class Line:
    def __init__(self, N_i:Optional[Node]=None, N_j:Optional[Node]=None, Config:Optional[Configuration_Type]=None, is_FDTD:bool=True):
        self.Line_Config = Config; self.Node_i = N_i; self.Node_j = N_j; self.isFDTD = is_FDTD; self.Phases_connected = []
        if Config: self.Configuration = Config
    @property
    def Configuration(self): return self.Line_Config
    @Configuration.setter
    def Configuration(self, value: Configuration_Type):
        self.Line_Config = value; self.Phases_connected.clear()
        for i in range(value.Num_conductors):
            ph = PhaseName.A if i==0 else (PhaseName.B if i==1 else (PhaseName.C if i==2 else PhaseName.N))
            self.Phases_connected.append(ph)
            if self.Node_i and ph not in self.Node_i.Phases_id: self.Node_i.Phases_id.append(ph)
            if self.Node_j and ph not in self.Node_j.Phases_id: self.Node_j.Phases_id.append(ph)
