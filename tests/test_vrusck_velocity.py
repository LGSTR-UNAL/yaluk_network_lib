import math

import pandas as pd
import pytest

import yaluk_network_lib.Network_lib as nl
from yaluk_network_lib.Network_lib.net_setting import build_conductors_db, build_configurations_db
from yaluk_network_lib.Lightning_lib.LightningChannel import LightningChannel


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


def _vertical_line_network():
    net = nl.Network("uid_test", "TestNet")
    net.AddNode(0.0, 0.0, Nodeidx=1, ctype="rel", label="N1")
    net.AddNode(0.0, 100.0, Nodeidx=2, ctype="rel", label="N2")
    node_i = net.Nodes.GetByName("N1")
    node_j = net.Nodes.GetByName("N2")
    net.AddLine(node_i, node_j, _r580_config())
    return net


# Punto (200, 50): distancia perpendicular a la linea vertical = 200 m.
# Con Imax=30000 A y hm=12 m, el criterio Rs/Rg de impacto directo da un
# umbral (~58 m) menor a 200 -> impacto indirecto, se calcula Vrusck.
X0, Y0, IMAX, HM, DIST = 200.0, 50.0, 30000.0, 12.0, 200.0


def test_check_direct_strike_vrusck_matches_historical_default_velocity():
    """Regresion: sin Channel_settings (o con la velocidad default de
    LightningChannel, 2/3 c), Vrusck_max debe reproducir exactamente la
    formula hardcodeada original -- no rompe corridas existentes."""
    net = _vertical_line_network()

    net.check_direct_strike(X0, Y0, IMAX, threshold_distance=9999999)

    historical = 1.2958 * 30 * IMAX / 1e3 * HM / DIST
    assert net.direct_strike is False
    assert net.Vrusck_max == pytest.approx(historical, rel=1e-9)


def test_check_direct_strike_vrusck_reacts_to_channel_velocity():
    """Antes era imposible: "1.2958 * 30" estaba hardcodeado y desconectado
    de Channel_settings.Velocity. Con una velocidad de canal distinta a la
    default, Vrusck_max debe cambiar en proporcion."""
    net_default = _vertical_line_network()
    net_default.check_direct_strike(X0, Y0, IMAX, threshold_distance=9999999)

    net_fast = _vertical_line_network()
    net_fast.Channel_settings = LightningChannel()
    net_fast.Channel_settings.Velocity = 0.9 * 3e8
    net_fast.check_direct_strike(X0, Y0, IMAX, threshold_distance=9999999)

    assert net_fast.Vrusck_max > net_default.Vrusck_max


def test_check_direct_strike_threshold_distance_controls_fdtd_not_vrusck():
    """threshold_distance decide isFDTD (modelo LCC vs FDTD), no interviene
    en el calculo de Vrusck."""
    net_far_threshold = _vertical_line_network()
    net_far_threshold.check_direct_strike(X0, Y0, IMAX, threshold_distance=9999999)
    line_far = net_far_threshold.Lines[0]

    net_near_threshold = _vertical_line_network()
    net_near_threshold.check_direct_strike(X0, Y0, IMAX, threshold_distance=101)
    line_near = net_near_threshold.Lines[0]

    assert line_far.isFDTD is True
    assert line_near.isFDTD is False
    assert net_far_threshold.Vrusck_max == pytest.approx(net_near_threshold.Vrusck_max, rel=1e-9)
