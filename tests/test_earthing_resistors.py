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
