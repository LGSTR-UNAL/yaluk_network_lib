import math

import pytest

import yaluk_network_lib.Network_lib as nl
from yaluk_network_lib.Lightning_lib.Lightning import Lightning
from yaluk_network_lib.Lightning_lib.Lightning_stat import Lightning_stat


def _config_mono():
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
    return config


def _net_dos_nodos(largo=1000.0):
    """Red minima: dos nodos unidos por una linea de `largo` m sobre el eje X."""
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)
    config = _config_mono()
    net.AddNode(0, 0, Nodeidx=1, ctype="abs")
    net.AddNode(largo, 0, Nodeidx=2, ctype="abs")
    net.AddLine(net.Nodes[0], net.Nodes[1], config)
    return net


def _net_linea(n_nodos=5, paso=250.0):
    """Linea recta de (n_nodos-1) segmentos iguales de `paso` m cada uno."""
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)
    config = _config_mono()
    for i in range(n_nodos):
        net.AddNode(i * paso, 0, Nodeidx=i + 1, ctype="abs")
    for i in range(n_nodos - 1):
        net.AddLine(net.Nodes[i], net.Nodes[i + 1], config)
    return net


def _rayo(x, y):
    L = Lightning(case=0)
    L.X_location = x
    L.Y_location = y
    return L


# ---------------------------------------------------------------------------
# _compute_buffer_area dinamico
# ---------------------------------------------------------------------------

def test_buffer_area_dinamico_converge_al_valor_analitico():
    # Un solo segmento: el area real es EXACTAMENTE la capsula analitica
    # (2*r*L + pi*r^2), sin solapamiento que la complique.
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(
        net, num_events=0, sampling="buffer_reject", buffer_radius=200.0,
        buffer_area_rel_error=0.01,
    )
    area_analitica = 2 * 200.0 * 1000.0 + math.pi * 200.0**2
    assert ls.Area == pytest.approx(area_analitica, rel=0.05)


def test_buffer_area_dinamico_para_antes_del_tope_en_caso_simple():
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(
        net, num_events=0, sampling="buffer_reject", buffer_radius=200.0,
        buffer_area_rel_error=0.01, buffer_area_max_samples=200000,
    )
    assert ls._buffer_area_n_used < 200000


def test_buffer_area_dinamico_corta_en_el_tope_si_el_error_es_inalcanzable():
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(
        net, num_events=0, sampling="buffer_reject", buffer_radius=200.0,
        buffer_area_rel_error=1e-9, buffer_area_max_samples=20000,
    )
    assert ls._buffer_area_n_used == 20000


def test_buffer_area_rel_error_no_positivo_cae_al_default():
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(
        net, num_events=0, sampling="buffer_reject", buffer_radius=200.0,
        buffer_area_rel_error=0,
    )
    assert ls.buffer_area_rel_error == 0.01


def test_buffer_area_max_samples_no_positivo_cae_al_default():
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(
        net, num_events=0, sampling="buffer_reject", buffer_radius=200.0,
        buffer_area_max_samples=-1,
    )
    assert ls.buffer_area_max_samples == 200000


# ---------------------------------------------------------------------------
# compute_density_check
# ---------------------------------------------------------------------------

def test_compute_density_check_cuenta_rayos_por_tramo_consecutivo():
    net = _net_linea(n_nodos=5, paso=250.0)  # 4 segmentos de 250 m, linea de 1000 m
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    # segment_length_km=0.5 -> n = round(1.0/0.5) = 2 tramos, 2 segmentos c/u
    ls.Lightnings = [
        _rayo(10, 0), _rayo(200, 0), _rayo(400, 0),  # tramo 0: segmentos [0,250)/[250,500)
        _rayo(600, 0), _rayo(900, 0),                 # tramo 1: segmentos [500,750)/[750,1000]
    ]
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.5)
    assert result["n_tramos"] == 2
    assert [t["m_i"] for t in result["tramos"]] == [3, 2]
    assert result["m_t"] == 5


def test_compute_density_check_tsim():
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    ls.Lightnings = [_rayo(10, 0) for _ in range(10)]
    result = ls.compute_density_check(Ng_real=2.0, segment_length_km=1.0)
    area_km2 = ls.Area / 1e6
    assert result["T_sim_years"] == pytest.approx(10 / (2.0 * area_km2))
    assert result["A_buffer_km2"] == pytest.approx(area_km2)


def test_compute_density_check_ng_real_no_positivo_da_tsim_none():
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    ls.Lightnings = [_rayo(10, 0)]
    result = ls.compute_density_check(Ng_real=0, segment_length_km=1.0)
    assert result["T_sim_years"] is None


def test_compute_density_check_segment_length_no_positivo_da_un_solo_tramo():
    net = _net_linea(n_nodos=5, paso=250.0)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    ls.Lightnings = [_rayo(10, 0), _rayo(900, 0)]
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0)
    assert result["n_tramos"] == 1
    assert result["tramos"][0]["m_i"] == 2
