class Conductor:
    def __init__(self):
        self.id=''; self.idx=0; self.Name=''; self._radius=0.0; self._resis=0.0
    @property
    def Radio(self): return self._radius
    @Radio.setter
    def Radio(self,v): self._radius = abs(v) if abs(v)<=0.1 else 0.1
    @property
    def Resistance(self): return self._resis
    @Resistance.setter
    def Resistance(self,v): self._resis = abs(v) if abs(v)<=100 else 100.0
class ConductorPosition:
    def __init__(self):
        self.id=0; self.Conduct=Conductor(); self.Height=0.0; self.Relative_X_location=0.0
