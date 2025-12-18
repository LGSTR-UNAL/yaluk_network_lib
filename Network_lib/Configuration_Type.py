from .Conductor import ConductorPosition, Conductor
from .collections import ConductorCollection
from .basic_func import lineparam
class Configuration_Type:
    def __init__(self):
        self.Type=''; self.Zc=None; self.Lm=None; self.Cm=None
        self.Conductors = ConductorCollection()
    @property
    def Num_conductors(self): return len(self.Conductors._list) if hasattr(self.Conductors,'_list') else 0
    def gen_parameters(self):
        cond = self.Num_conductors
        Xi=[0.0]*cond; hm=[0.0]*cond; rc=[0.0]*cond
        for j, conductor in enumerate(self.Conductors._list):
            hm[j]=conductor.Height; Xi[j]=conductor.Relative_X_location; rc[j]=conductor.Conduct.Radio
        return lineparam(cond, Xi, hm, rc)
    def Add_conductor(self, C: Conductor, Height: float, X_pos: float = 0.0):
        cp = ConductorPosition(); cp.Conduct=C; cp.Height=Height; cp.Relative_X_location=X_pos
        cp.id = len(self.Conductors._list)+1
        self.Conductors.Add(cp)
