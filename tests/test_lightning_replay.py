import pytest

import yaluk_network_lib.Network_lib as nl
from yaluk_network_lib.Lightning_lib.Lightning_stat import Lightning_stat


def _net_linea(x0, y0, x1, y1):
    """Red minima de dos nodos unidos por una linea recta, en las
    coordenadas dadas -- permite armar dos "areas" vecinas con segmentos
    distintos pero cercanos entre si (mismo patron que
    tests/test_lightning_lls.py::_net_dos_nodos, parametrizado en x/y)."""
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

    net.AddNode(x0, y0, Nodeidx=1, ctype="abs")
    net.AddNode(x1, y1, Nodeidx=2, ctype="abs")
    net.AddLine(net.Nodes[0], net.Nodes[1], config)
    return net


def _replay_df(rows):
    """rows: lista de dicts con al menos X0/Y0 -- completa el resto con
    valores por defecto reconocibles."""
    import pandas as pd

    columns = ["Ih1", "Ih2", "tao11", "tao21", "tao12", "tao22", "n1", "n2", "X0", "Y0"]
    defaults = {
        "Ih1": 30000.0, "Ih2": 0.0, "tao11": 3e-6, "tao21": 5e-5,
        "tao12": 0.0, "tao22": 0.0, "n1": 4, "n2": 0,
    }
    full_rows = [{**defaults, **r} for r in rows]
    return pd.DataFrame(full_rows, columns=columns)


def test_load_from_previous_run_reconstruye_valores_exactos_sin_rng():
    net = _net_linea(0, 0, 1000, 0)
    df = _replay_df([
        {"Ih1": 45230.0, "tao11": 3.21e-6, "tao21": 6.5e-5, "X0": 500.0, "Y0": 50.0},
    ])
    ls_obj = Lightning_stat(net, M="Replay", replay_df=df)
    assert len(ls_obj.Lightnings) == 1
    Li = ls_obj.Lightnings[0]
    assert Li.Ih1 == pytest.approx(45230.0)
    assert Li.tf1 == pytest.approx(3.21e-6)
    assert Li.tc1 == pytest.approx(6.5e-5)
    assert Li.X_location == pytest.approx(500.0)
    assert Li.Y_location == pytest.approx(50.0)


def test_load_from_previous_run_no_recalcula_front_time(monkeypatch):
    def _boom(self, Ix_kA):
        raise AssertionError("LoadFromPreviousRun no debe recalcular Front_time/tf1")

    monkeypatch.setattr(Lightning_stat, "_impute_front_time", _boom)

    net = _net_linea(0, 0, 1000, 0)
    df = _replay_df([{"X0": 500.0, "Y0": 50.0, "tao11": 9.9e-6, "tao21": 8.8e-5}])
    ls_obj = Lightning_stat(net, M="Replay", replay_df=df)
    assert ls_obj.Lightnings[0].tf1 == pytest.approx(9.9e-6)
    assert ls_obj.Lightnings[0].tc1 == pytest.approx(8.8e-5)


def test_load_from_previous_run_filtra_fuera_del_corredor():
    net = _net_linea(0, 0, 1000, 0)
    df = _replay_df([
        {"X0": 500.0, "Y0": 100.0},   # dentro (buffer_radius default 1000 m)
        {"X0": 500.0, "Y0": 5000.0},  # fuera
    ])
    ls_obj = Lightning_stat(net, M="Replay", replay_df=df)
    assert len(ls_obj.Lightnings) == 1
    assert ls_obj.Lightnings[0].Y_location == pytest.approx(100.0)


def test_load_from_previous_run_sin_rayos_en_el_corredor_no_lanza_excepcion():
    # A diferencia de LoadFromDatabase (que lanza ValueError con "cero
    # rayos"), Replay debe aceptar el hueco en silencio -- ver spec §3,
    # decision 3 ("aceptar el hueco, sin generar rayos nuevos").
    net = _net_linea(0, 0, 1000, 0)
    df = _replay_df([{"X0": 500.0, "Y0": 50000.0}])
    ls_obj = Lightning_stat(net, M="Replay", replay_df=df)
    assert ls_obj.Lightnings == []


def test_load_from_previous_run_recalcula_min_dist_contra_la_red():
    net = _net_linea(0, 0, 1000, 0)
    df = _replay_df([{"X0": 500.0, "Y0": 10.0}])
    ls_obj = Lightning_stat(net, M="Replay", replay_df=df)
    assert ls_obj.Lightnings[0].min_dist == pytest.approx(10.0, abs=1.0)


def test_load_from_previous_run_rayo_en_zona_comun_aparece_en_las_dos_areas():
    # Area A: linea (0,0)-(1000,0). Area B: linea (1000,0)-(2000,0) --
    # vecina, comparten el nodo (1000,0). Un rayo en (1000,100) esta a
    # ~100 m de AMBAS lineas -- dentro del buffer_radius=1000 de las dos.
    net_a = _net_linea(0, 0, 1000, 0)
    net_b = _net_linea(1000, 0, 2000, 0)
    df = _replay_df([{"X0": 1000.0, "Y0": 100.0}])

    ls_a = Lightning_stat(net_a, M="Replay", replay_df=df)
    ls_b = Lightning_stat(net_b, M="Replay", replay_df=df)

    assert len(ls_a.Lightnings) == 1
    assert len(ls_b.Lightnings) == 1


def test_load_from_previous_run_usa_area_de_corredor_no_bbox():
    # uses_corridor debe incluir "Replay": si cayera al fallback de bbox,
    # el area (y por lo tanto Tsim/Ng_real de la Fase 1) saldria mal para
    # cualquier sub-caso que reutilice rayos.
    net = _net_linea(0, 0, 1000, 0)
    df = _replay_df([{"X0": 500.0, "Y0": 50.0}])
    ls_replay = Lightning_stat(net, M="Replay", replay_df=df, buffer_radius=100.0)
    ls_prob = Lightning_stat(net, num_events=0, M="ProbDistribution", buffer_radius=100.0)

    bbox_area = (ls_replay.Xmax - ls_replay.Xmin) * (ls_replay.Ymax - ls_replay.Ymin)
    assert ls_replay.Area == pytest.approx(ls_prob.Area, rel=0.05)
    assert ls_replay.Area < bbox_area * 0.5
