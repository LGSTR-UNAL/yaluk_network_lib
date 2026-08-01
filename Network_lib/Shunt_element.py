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
        """Tarjeta /BRANCH de elemento concentrado RLC en formato de columnas
        fijas de ATP:

            cols 1-2   tipo (en blanco para RLC concentrado)
            cols 3-8   nodo 1
            cols 9-14  nodo 2 (en blanco = tierra)
            cols 15-26 referencias (en blanco)
            cols 27-32 R [ohm], 33-38 L [mH], 39-44 C [uF]
            col  80    solicitud de salida (0 = ninguna)

        Antes escribia `SHUNT <nodo> R=.. C=.. L=..`, que no es una tarjeta
        valida de ATP; nunca se habia detectado porque ningun caso agregaba
        elementos shunt hasta la terminacion con Zc de la segmentacion.
        Shunt_lump no guarda el segundo nodo, asi que el caso no aterrizado
        (SolidGrounded=False) se escribe igual contra tierra.
        """
        for le, ph in zip(self.Lumped_elements, self.Phases_connected):
            n1 = f"{self.Node.id}{ph.value}"
            card = (
                f"  {n1:<6}{'':6}{'':12}"
                f"{le.Resistance:06.1f}{le.Inductance:06.1f}{le.Capacitance:06.1f}"
            )
            write(card.ljust(79) + "0\n")
