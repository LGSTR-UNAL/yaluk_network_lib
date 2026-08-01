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


def test_init_sin_lineas_lanza_valueerror_si_no_es_bbox():
    net = nl.Network()
    net.AddNode(0, 0, Nodeidx=1, ctype="abs")  # fija xmin/xmax; net.Lines sigue vacio
    with pytest.raises(ValueError, match="no hay lineas"):
        Lightning_stat(net, num_events=10, sampling="buffer_reject")


def test_init_bbox_no_requiere_lineas():
    net = nl.Network()
    net.AddNode(0, 0, Nodeidx=1, ctype="abs")
    ls = Lightning_stat(net, num_events=0, M="Database", sampling="bbox")
    assert ls.Area == pytest.approx((ls.Xmax - ls.Xmin) * (ls.Ymax - ls.Ymin))


def _net_dos_nodos():
    """Red minima: dos nodos unidos por una linea de 1000 m sobre el eje X,
    (0,0)-(1000,0)."""
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)

    conductor = nl.Conductor()
    conductor.Radio = 0.005
    conductor.Resistance = 1
    conductor.Name = "Conductor test"
    conductor.Description = "Conductor de prueba"

    config = nl.Configuration_Type()
    config.id = "CFG1"
    config.Name = "Mono"
    config.Description = "Linea de un solo conductor"
    config.Add_conductor(conductor, 10, 0)
    config.gen_parameters()

    net.AddNode(0, 0, Nodeidx=1, ctype="abs")
    net.AddNode(1000, 0, Nodeidx=2, ctype="abs")
    net.AddLine(net.Nodes[0], net.Nodes[1], config)
    return net


def test_cobertura_buffer_reject_todos_los_puntos_dentro_del_corredor():
    net = _net_dos_nodos()   # linea (0,0)-(1000,0)
    ls = Lightning_stat(net, num_events=200, sampling="buffer_reject", buffer_radius=1000.0)
    for L in ls.Lightnings:
        assert ls._min_dist_to_lines(L.X_location, L.Y_location) <= 1000.0 + 1e-6


def test_cobertura_buffer_capsule_todos_los_puntos_dentro_del_corredor():
    net = _net_dos_nodos()
    ls = Lightning_stat(net, num_events=200, sampling="buffer_capsule", buffer_radius=1000.0)
    for L in ls.Lightnings:
        assert ls._min_dist_to_lines(L.X_location, L.Y_location) <= 1000.0 + 1e-6


def test_sampling_bbox_reproduce_rectangulo_legacy():
    net = _net_dos_nodos()
    ls = Lightning_stat(net, num_events=200, sampling="bbox")
    for L in ls.Lightnings:
        assert ls.Xmin <= L.X_location <= ls.Xmax
        assert ls.Ymin <= L.Y_location <= ls.Ymax
    assert ls.Area == pytest.approx((ls.Xmax - ls.Xmin) * (ls.Ymax - ls.Ymin))
