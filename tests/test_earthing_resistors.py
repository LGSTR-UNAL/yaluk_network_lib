"""Resistencia de puesta a tierra unificada por nodo (RPAT).

Ver spec `context/specs/2026-08-11-uso-rpat-puesta-a-tierra-design.md`.
"""

import math

import pytest

import yaluk_network_lib.Network_lib as nl


def _net_dos_nodos(rpat_a=20.0, rpat_b=20.0, num_conductores=4):
    """Red minima: dos nodos unidos por una linea. Con 4 conductores la
    configuracion trae cable de guarda (fase N); con 3, no."""
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)

    config = nl.Configuration_Type()
    config.id = "CFG1"
    config.Name = "Test"
    for i in range(num_conductores):
        conductor = nl.Conductor()
        conductor.Radio = 0.005
        conductor.Resistance = 1
        conductor.Name = f"Conductor {i}"
        config.Add_conductor(conductor, 10.0, i * 1.0)
    config.gen_parameters()

    net.AddNode(0, 0, Nodeidx=1, ctype="abs", label="A", RPAT=rpat_a)
    net.AddNode(500, 0, Nodeidx=2, ctype="abs", label="B", RPAT=rpat_b)
    net.AddLine(net.Nodes[0], net.Nodes[1], config)
    return net, config


def test_nodo_con_guarda_y_rpat_definido_se_aterriza():
    net, _ = _net_dos_nodos(rpat_a=15.0, rpat_b=20.0)

    fallback = net.AddEarthingResistors(default_rpat=10.0)

    assert fallback == []
    assert len(net.Shunt_elements) == 2
    resistencias = sorted(e.Lumped_elements[0].Resistance for e in net.Shunt_elements)
    assert resistencias == pytest.approx([15.0, 20.0])


def test_nodo_con_guarda_y_rpat_vacio_no_se_aterriza():
    net, _ = _net_dos_nodos(rpat_a=float("nan"), rpat_b=float("nan"))

    fallback = net.AddEarthingResistors(default_rpat=10.0)

    assert fallback == []
    assert net.Shunt_elements == []


def test_nodo_sin_guarda_ni_equipo_no_se_aterriza():
    net, _ = _net_dos_nodos(num_conductores=3)  # A, B, C -- sin N

    fallback = net.AddEarthingResistors(default_rpat=10.0)

    assert fallback == []
    assert net.Shunt_elements == []


def _net_con_transformador(rpat=None, ground=None, con_dps=False):
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)
    net.AddNode(0, 0, Nodeidx=1, ctype="abs", label="A", RPAT=rpat)
    node = net.Nodes.GetByName("A")
    net.AddTransf(
        label="T1", CHV=340e-6, CLV=215e-6, CHL=744e-6,
        ground=ground, NHV=node, phases=111,
    )
    if con_dps:
        net.AddSurgeArrester(ni=node, pch_file="dummy.pch", Phase_connect=111)
    return net, node


def test_transformador_con_g_resistance_menor_que_rpat_usa_g_resistance():
    net, _ = _net_con_transformador(rpat=20.0, ground=15.0)

    net.AddEarthingResistors(default_rpat=10.0)

    assert len(net.Shunt_elements) == 1
    assert net.Shunt_elements[0].Lumped_elements[0].Resistance == pytest.approx(15.0)


def test_transformador_con_g_resistance_mayor_que_rpat_usa_rpat():
    net, _ = _net_con_transformador(rpat=5.0, ground=20.0)

    net.AddEarthingResistors(default_rpat=10.0)

    assert len(net.Shunt_elements) == 1
    assert net.Shunt_elements[0].Lumped_elements[0].Resistance == pytest.approx(5.0)


def test_transformador_y_descargador_en_el_mismo_nodo_una_sola_tierra():
    net, _ = _net_con_transformador(rpat=20.0, ground=float("nan"), con_dps=True)

    net.AddEarthingResistors(default_rpat=10.0)

    assert len(net.Shunt_elements) == 1  # antes: una rama por Transformer + una por SurgeArrester


def test_equipo_sin_ningun_valor_definido_usa_default_y_reporta_label():
    net, node = _net_con_transformador(rpat=float("nan"), ground=float("nan"))

    fallback = net.AddEarthingResistors(default_rpat=10.0)

    assert fallback == ["A"]
    assert len(net.Shunt_elements) == 1
    assert net.Shunt_elements[0].Lumped_elements[0].Resistance == pytest.approx(10.0)


def test_dos_transformadores_en_el_mismo_nodo_usa_el_menor_g_resistance():
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)
    net.AddNode(0, 0, Nodeidx=1, ctype="abs", label="A", RPAT=float("nan"))
    node = net.Nodes.GetByName("A")
    net.AddTransf(label="T1", CHV=340e-6, CLV=215e-6, CHL=744e-6, ground=25.0, NHV=node, phases=111)
    net.AddTransf(label="T2", CHV=340e-6, CLV=215e-6, CHL=744e-6, ground=12.0, NHV=node, phases=111)

    net.AddEarthingResistors(default_rpat=10.0)

    assert len(net.Shunt_elements) == 1
    assert net.Shunt_elements[0].Lumped_elements[0].Resistance == pytest.approx(12.0)


def test_nodo_lv_del_transformador_no_se_aterriza_aparte():
    net, _ = _net_con_transformador(rpat=20.0, ground=15.0)

    net.AddEarthingResistors(default_rpat=10.0)

    nodo_lv = net.Nodes.Find(lambda n: n.id == "B0001")
    assert nodo_lv is not None
    assert nodo_lv.Shunt_elements == []


def test_atp_no_repite_la_tierra_del_transformador_via_write_atp_file():
    net, _ = _net_con_transformador(rpat=20.0, ground=15.0)
    net.AddEarthingResistors(default_rpat=10.0)

    atp = net.MakeATPBuffer().getvalue().decode("utf-8")
    ramas, _, _ = atp.partition("/SOURCE")
    # Antes del fix, Transformer.write_atp_file escribia una segunda tarjeta
    # "  N0001N ... 20.0 ..." ademas de la que ahora escribe AddEarthingResistors.
    tarjetas_tierra_n = [
        l for l in ramas.splitlines()
        if l[:2] == "  " and l[2:8] == "N0001N"
    ]
    assert len(tarjetas_tierra_n) == 1
