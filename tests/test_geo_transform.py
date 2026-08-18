import time

import pytest

from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf


def test_coord_transf_reutiliza_el_mismo_pyproj_transformer_para_el_mismo_epsg():
    # pyproj.Transformer.from_crs es caro de construir -- medido: ~6.2s
    # para 1500 instancias con el mismo par de EPSG, exactamente lo que
    # hacia Lightning.__init__ una vez por rayo generado en GenStatCurrents.
    a = CoordTransf(4326, 9377)
    b = CoordTransf(4326, 9377)
    assert a._transformer is b._transformer


def test_coord_transf_no_comparte_transformer_entre_epsg_distintos():
    a = CoordTransf(4326, 9377)
    b = CoordTransf(4326, 3116)
    assert a._transformer is not b._transformer


def test_coord_transf_construccion_repetida_mismo_epsg_es_rapida():
    start = time.perf_counter()
    for _ in range(500):
        CoordTransf(4326, 9377)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"tardo {elapsed:.2f}s -- se esperaba cache del pyproj.Transformer"


def test_to_geographic_round_trip_no_intercambia_lat_lon():
    lat0, lon0 = 6.1924, -75.3979  # coordenadas reales del proyecto (Network.py InitLatLong default)
    transf = CoordTransf()

    x, y = transf.to_projected(lat0, lon0)
    lat1, lon1 = transf.to_geographic(x, y)

    assert lat1 == pytest.approx(lat0, abs=1e-6)
    assert lon1 == pytest.approx(lon0, abs=1e-6)
