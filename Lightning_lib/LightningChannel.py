from enum import Enum


class Return_stroke_model(Enum):
    MTL = 0
    TL = 1


class LightningChannel:
    def __init__(self):
        self.Model: Return_stroke_model = Return_stroke_model.TL
        self.Velocity: float = 2.0 / 3.0 * 3e8  # [m/s]
        self.Heigth: float = 8000.0            # [m]
        self.Atenuation_const: float = 2000.0  # [m]

    def __str__(self):
        return self.Model.name
