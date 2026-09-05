"""Tests del modo Single: un rayo definido a mano (corriente + posicion),
con el resto de la doble Heidler derivado por la MEDIANA de la correlacion
tf-Ih, no por un sorteo.

La reproducibilidad es la razon de ser de este modo: LoadFromDatabase vuelve
a imputar el tiempo de frente con su propio numero aleatorio en cada
inyeccion (medido en la Etapa 4 del estudio de aceleracion, 2026-08: el mismo
evento inyectado dos veces dio dos ondas distintas). Un rayo de diagnostico
tiene que salir identico cada vez que se corre.
"""

import math

import pytest

import yaluk_network_lib.Network_lib as nl
from yaluk_network_lib.Lightning_lib.Lightning_stat import Lightning_stat


def _net_linea(x0, y0, x1, y1, origin=(0, 0)):
    """Red minima de dos nodos unidos por una linea recta (mismo helper que
    tests/test_lightning_replay.py)."""
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(*origin)

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

    net.AddNode(x0, y0, Nodeidx=1, ctype="abs")
    net.AddNode(x1, y1, Nodeidx=2, ctype="abs")
    net.AddLine(net.Nodes[0], net.Nodes[1], config)
    return net


def test_impute_front_time_con_q_es_determinista():
    """Con q fijo no se consume ningun numero aleatorio: dos llamadas
    seguidas dan exactamente lo mismo."""
    net = _net_linea(0, 0, 1000, 0)
    ls = Lightning_stat(net, 0, "Single", single_stroke=(30.0, 500.0, 10.0))

    a = ls._impute_front_time(30.0, q=0.5)
    b = ls._impute_front_time(30.0, q=0.5)
    assert a == b


def test_impute_front_time_sin_q_sigue_sorteando():
    """No se cambia el comportamiento de GenStatCurrents/LoadFromDatabase:
    sin q, el sorteo sigue siendo sorteo."""
    net = _net_linea(0, 0, 1000, 0)
    ls = Lightning_stat(net, 0, "Single", single_stroke=(30.0, 500.0, 10.0))

    vistos = {ls._impute_front_time(30.0)[0] for _ in range(20)}
    assert len(vistos) > 1


def test_modo_single_genera_exactamente_un_rayo_con_los_valores_pedidos():
    net = _net_linea(0, 0, 1000, 0)
    ls = Lightning_stat(net, 0, "Single", single_stroke=(45.0, 500.0, 10.0))

    assert len(ls.Lightnings) == 1
    L = ls.Lightnings[0]
    assert L.Ih1 == pytest.approx(45_000.0)   # kA -> A
    assert L.Ih2 == 0.0
    assert L.X_location == pytest.approx(500.0)
    assert L.Y_location == pytest.approx(10.0)
    assert L.n1 == 4
    assert L.tc1 == pytest.approx(50e-6)
    assert L.tf1 > 0


def test_modo_single_es_reproducible():
    """Dos construcciones con los mismos numeros dan la misma onda. Es la
    diferencia con el modo Database, que reimputa el frente cada vez."""
    net_a = _net_linea(0, 0, 1000, 0)
    net_b = _net_linea(0, 0, 1000, 0)
    a = Lightning_stat(net_a, 0, "Single", single_stroke=(45.0, 500.0, 10.0))
    b = Lightning_stat(net_b, 0, "Single", single_stroke=(45.0, 500.0, 10.0))

    la, lb = a.Lightnings[0], b.Lightnings[0]
    assert la.tf1 == lb.tf1
    assert la.Front_time == lb.Front_time
    assert la.Ih1 == lb.Ih1


def test_modo_single_usa_la_posicion_absoluta():
    """La posicion llega en el marco absoluto de structures.csv y se
    convierte al marco local de la red restando su origen -- mismo criterio
    que LoadFromPreviousRun, que se agrego el 2026-08-23 tras medir
    desplazamientos de hasta 14,2 km por reanclar al origen equivocado."""
    net = _net_linea(10000, 20000, 11000, 20000, origin=(10000, 20000))
    ls = Lightning_stat(net, 0, "Single", single_stroke=(45.0, 10500.0, 20050.0))

    L = ls.Lightnings[0]
    assert L.X_location == pytest.approx(500.0)
    assert L.Y_location == pytest.approx(50.0)


def test_modo_single_rechaza_un_rayo_fuera_del_corredor():
    """El corredor es el mismo de los otros modos (buffer_radius). Un rayo a
    5 km de la linea no tiene sentido fisico para este estudio, y devolver
    cero rayos en silencio dejaria una corrida vacia sin explicacion."""
    net = _net_linea(0, 0, 1000, 0)
    with pytest.raises(ValueError, match="corredor"):
        Lightning_stat(net, 0, "Single", single_stroke=(45.0, 500.0, 5000.0))


def test_modo_single_con_corriente_no_positiva_falla():
    net = _net_linea(0, 0, 1000, 0)
    with pytest.raises(ValueError):
        Lightning_stat(net, 0, "Single", single_stroke=(0.0, 500.0, 10.0))


def test_modo_single_no_estricto_omite_el_rayo_fuera_del_corredor():
    """Con varias islas, un rayo solo cae en el corredor de UNA. Las demas
    deben omitirlo en silencio, como ya hace Replay, en vez de abortar la
    corrida entera."""
    net = _net_linea(0, 0, 1000, 0)
    ls = Lightning_stat(net, 0, "Single", single_stroke=(45.0, 500.0, 5000.0),
                        single_strict=False)
    assert ls.Lightnings == []
    assert ls.single_dist_m == pytest.approx(5000.0, rel=0.01)


def test_modo_single_no_estricto_sigue_rechazando_corriente_invalida():
    """Una corriente de cero es un error de entrada del usuario, no una
    pregunta de geometria: no se omite en silencio nunca."""
    net = _net_linea(0, 0, 1000, 0)
    with pytest.raises(ValueError):
        Lightning_stat(net, 0, "Single", single_stroke=(0.0, 500.0, 10.0),
                       single_strict=False)


def test_modo_single_estricto_sigue_siendo_el_default():
    net = _net_linea(0, 0, 1000, 0)
    with pytest.raises(ValueError, match="corredor"):
        Lightning_stat(net, 0, "Single", single_stroke=(45.0, 500.0, 5000.0))
