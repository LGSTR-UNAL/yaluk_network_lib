import math

import pytest

import yaluk_network_lib.Network_lib as nl
from yaluk_network_lib.Lightning_lib.Lightning_stat import (
    Lightning_stat,
    _dist_point_to_segment,
)


def test_dist_point_to_segment_proyeccion_interior():
    # segmento horizontal (0,0)-(10,0); punto (5,3) -> distancia 3
    assert _dist_point_to_segment(5, 3, 0, 0, 10, 0) == 3.0


def test_dist_point_to_segment_mas_alla_del_extremo():
    # punto detras del extremo A -> distancia al extremo, no a la recta
    assert _dist_point_to_segment(-5, 4, 0, 0, 10, 0) == math.hypot(5, 4)


def test_dist_point_to_segment_vertical():
    assert _dist_point_to_segment(3, 5, 0, 0, 0, 10) == 3.0


def test_dist_point_to_segment_degenerado():
    # nodos iguales -> distancia euclidiana simple al punto
    assert _dist_point_to_segment(3, 4, 0, 0, 0, 0) == 5.0
