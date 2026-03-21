from typing import List, Optional
from .Node import PhaseName, Element_id, Node


class SurgeArrester(Element_id):
    def __init__(
        self, filename: Optional[str] = None, N=None, Phase_connection: int = 0
    ):
        super().__init__()
        self.Ni: Node = N
        self.pch_file_name = filename
        self.Phases_connected = []
        if filename and N:
            self._populate_phases_from_int(Phase_connection)

    def _populate_phases_from_int(self, pc: int):
        match pc:
            case 100:
                self.Phases_connected.append(PhaseName.A)
            case 10:
                self.Phases_connected.append(PhaseName.B)
            case 1:
                self.Phases_connected.append(PhaseName.C)
            case 110:
                self.Phases_connected.append(PhaseName.A)
                self.Phases_connected.append(PhaseName.B)
            case 11:
                self.Phases_connected.append(PhaseName.B)
                self.Phases_connected.append(PhaseName.C)
            case 101:
                self.Phases_connected.append(PhaseName.A)
                self.Phases_connected.append(PhaseName.C)
            case 111:
                self.Phases_connected.append(PhaseName.A)
                self.Phases_connected.append(PhaseName.B)
                self.Phases_connected.append(PhaseName.C)
            case 000:
                # It must be implemented an error message
                pass

    def write_atp_file(self, write):
        max_len = 80
        if not self.pch_file_name:
            return
        current_line = ""
        token = f"$INCLUDE, {self.pch_file_name}"
        current_line += token
        phases = self.Phases_connected.copy()
        phases.append(PhaseName.N)
        for ph in phases:
            token = f"N{self.Ni.idx:04d}{ph.value}"
            if len(current_line) + len(token) > (max_len - 3):
                current_line += ","
                current_line = current_line.ljust(78) + "$$\n"
                write(current_line)
                current_line = "  " + token
            else:
                current_line += "," + token

        write(current_line + "\n")
        write(
            f"  N{self.Ni.idx:04d}{phases[-1].value}                  {self.Ni.RPAT:6.1f}\n"
        )
