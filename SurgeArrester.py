from typing import List, Optional
from .Node import PhaseName, Element_id
class SurgeArrester(Element_id):
    def __init__(self, filename:Optional[str]=None, N=None, Phase_connection:int=0):
        super().__init__(); self.Ni=N; self.pch_file_name=filename; self.Phases_connected=[]
        if filename and N: self._populate_phases_from_int(Phase_connection)
    def _populate_phases_from_int(self, pc:int):
        if pc==100: self.Phases_connected.append(PhaseName.A)
        if pc==10: self.Phases_connected.append(PhaseName.B)
        if pc==1: self.Phases_connected.append(PhaseName.C)
    def write_atp_file(self, file):
        if not self.pch_file_name: return
        file.write(f"INCLUDE {self.pch_file_name} FOR {self.Ni.id}\n")
