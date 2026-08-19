import pandas as pd

import yaluk_network_lib.Network_lib as nl
from yaluk_network_lib.Network_lib.ATP_cards_w import write_models
from yaluk_network_lib.Network_lib.net_setting import build_conductors_db, build_configurations_db


def _r580_config():
    cables = pd.DataFrame([
        {"id": "COND_4_0", "label": "Conductor 4/0",
         "description": "Conductor 4/0 AWG - catalogo CENTELSA",
         "radio": 0.0143, "resistance": 0.2667},
    ])
    config_types = pd.DataFrame([
        {"id": "R-580", "name": "R-580", "description": "Linea un solo conductor",
         "Geometry": "[('COND_4_0', 12, 2), ('COND_4_0', 12, 0), ('COND_4_0', 12, -2)]"},
    ])
    conductors_db = build_conductors_db(cables)
    configurations_db = build_configurations_db(config_types, conductors_db)
    return configurations_db["R-580"]


def _network_two_lines(fdtd_flags):
    """3 nodos, 2 lineas (N1-N2, N2-N3). fdtd_flags[i] se asigna a mano al
    isFDTD de self.Lines[i] -- simula lo que check_direct_strike dejaria
    para un rayo indirecto puntual, sin depender de la geometria real."""
    net = nl.Network("uid_test", "TestNet")
    net.AddNode(0.0, 0.0, Nodeidx=1, ctype="rel", label="N1")
    net.AddNode(0.0, 100.0, Nodeidx=2, ctype="rel", label="N2")
    net.AddNode(0.0, 200.0, Nodeidx=3, ctype="rel", label="N3")
    n1 = net.Nodes.GetByName("N1")
    n2 = net.Nodes.GetByName("N2")
    n3 = net.Nodes.GetByName("N3")
    net.AddLine(n1, n2, _r580_config())
    net.AddLine(n2, n3, _r580_config())
    net.direct_strike = False
    for line, flag in zip(net.Lines, fdtd_flags):
        line.isFDTD = flag
    return net


def test_write_models_instantiates_the_fdtd_line_even_when_the_last_line_is_not_fdtd():
    # bug real encontrado 2026-08-19: el 2do bucle de write_models revisaba
    # la variable "linea" (minuscula) que quedaba STALE del primer bucle --
    # siempre la ULTIMA linea de self.Lines -- en vez de "Linea" (la propia
    # de cada iteracion). Con la ultima linea NO FDTD (el caso tipico en un
    # red con FDTDDistThreshold chico), ninguna linea se instanciaba nunca,
    # sin importar cuantas SI fueran FDTD -- yaluk_init nunca se llamaba.
    net = _network_two_lines(fdtd_flags=[True, False])

    chunks = []
    write_models(chunks.append, net, settings=None)
    text = "".join(chunks)

    fdtd_line = net.Lines[0]
    assert f"AS Yaluk{fdtd_line.idx:04d}\n" in text


def test_write_models_gives_each_fdtd_line_a_unique_alias_by_its_own_idx():
    # bug real #2: el alias usaba Linea.Configuration.Num_conductors (igual
    # para cualquier linea con la misma cantidad de conductores) en vez de
    # Linea.idx -- dos lineas FDTD con el mismo Num_conductors colisionaban
    # con el mismo alias "Yaluk000N".
    net = _network_two_lines(fdtd_flags=[True, True])

    chunks = []
    write_models(chunks.append, net, settings=None)
    text = "".join(chunks)

    line_a, line_b = net.Lines[0], net.Lines[1]
    assert line_a.idx != line_b.idx
    assert f"AS Yaluk{line_a.idx:04d}\n" in text
    assert f"AS Yaluk{line_b.idx:04d}\n" in text


def test_write_models_never_instantiates_a_non_fdtd_line():
    net = _network_two_lines(fdtd_flags=[True, False])

    chunks = []
    write_models(chunks.append, net, settings=None)
    text = "".join(chunks)

    non_fdtd_line = net.Lines[1]
    assert f"AS Yaluk{non_fdtd_line.idx:04d}\n" not in text
