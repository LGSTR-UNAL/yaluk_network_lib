"""Nodos no monitoreados y terminacion con Zc (segmentacion de redes grandes).

Ver plan `context/plans/2026-07-31-segmentacion-redes-grandes.md` §5 y §6.
"""

import pytest

import yaluk_network_lib.Network_lib as nl


def _net_tres_nodos(num_conductores: int = 3):
    """Red minima: tres nodos en linea sobre el eje X, (0,0)-(500,0)-(1000,0)."""
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

    net.AddNode(0, 0, Nodeidx=1, ctype="abs", label="A")
    net.AddNode(500, 0, Nodeidx=2, ctype="abs", label="B")
    net.AddNode(1000, 0, Nodeidx=3, ctype="abs", label="C", monitor=False)
    net.AddLine(net.Nodes[0], net.Nodes[1], config)
    net.AddLine(net.Nodes[1], net.Nodes[2], config)
    return net, config


def _atp_text(net):
    return net.MakeATPBuffer().getvalue().decode("utf-8")


def _output_section(atp: str) -> str:
    _, _, resto = atp.partition("/OUTPUT\n")
    salida, _, _ = resto.partition("C ENDING DIRECTIVES")
    return salida


# ------------------------------------------------------------------ monitor


def test_nodo_es_monitoreado_por_default():
    net, _ = _net_tres_nodos()
    assert net.Nodes.GetByName("A").monitor is True


def test_write_output_omite_los_nodos_no_monitoreados():
    net, _ = _net_tres_nodos()
    salida = _output_section(_atp_text(net))

    # A (idx 1) y B (idx 2) si; C (idx 3, monitor=False) no.
    assert "N0001A" in salida
    assert "N0002A" in salida
    assert "N0003" not in salida


def test_todos_monitoreados_pide_todos_los_nodos():
    net, _ = _net_tres_nodos()
    net.Nodes.GetByName("C").monitor = True
    salida = _output_section(_atp_text(net))

    assert "N0003A" in salida


# -------------------------------------------------------- terminacion con Zc


def test_add_zc_termination_agrega_una_resistencia_por_fase():
    net, config = _net_tres_nodos(num_conductores=3)
    nodo = net.Nodes.GetByName("C")

    fases = net.AddZcTermination(nodo)

    assert fases == 3
    assert len(net.Shunt_elements) == 3
    assert len(nodo.Shunt_elements) == 3
    resistencias = sorted(
        e.Lumped_elements[0].Resistance for e in net.Shunt_elements
    )
    esperadas = sorted(float(config.Zc[i, i]) for i in range(3))
    assert resistencias == pytest.approx(esperadas)


def test_add_zc_termination_sin_lineas_no_hace_nada():
    net, _ = _net_tres_nodos()
    net.AddNode(5000, 5000, Nodeidx=9, ctype="abs", label="SUELTO")

    assert net.AddZcTermination(net.Nodes.GetByName("SUELTO")) == 0
    assert net.Shunt_elements == []


def test_terminacion_zc_se_escribe_como_tarjeta_de_branch_valida():
    net, config = _net_tres_nodos(num_conductores=3)
    nodo = net.Nodes.GetByName("C")
    net.AddZcTermination(nodo)

    atp = _atp_text(net)
    ramas, _, _ = atp.partition("/SOURCE")
    # cols 1-2 en blanco = RLC concentrado (las tarjetas "51N0003A..." son
    # las lineas FDTD del mismo nodo, con tipo en las dos primeras columnas)
    cards = [l for l in ramas.splitlines() if l[:2] == "  " and l[2:8] == "N0003A"]

    assert cards, "no se escribio la tarjeta de terminacion del nodo N0003A"
    card = cards[0]
    assert len(card) == 80
    assert card[:2] == "  "            # tipo en blanco = RLC concentrado
    assert card[8:14].strip() == ""    # nodo 2 en blanco = tierra
    assert float(card[26:32]) == pytest.approx(float(config.Zc[0, 0]), abs=0.05)
    assert card[79] == "0"             # sin solicitud de salida extra
    assert "SHUNT" not in atp          # el placeholder viejo ya no se escribe
