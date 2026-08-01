import pytest

from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf


def test_to_geographic_round_trip_no_intercambia_lat_lon():
    lat0, lon0 = 6.1924, -75.3979  # coordenadas reales del proyecto (Network.py InitLatLong default)
    transf = CoordTransf()

    x, y = transf.to_projected(lat0, lon0)
    lat1, lon1 = transf.to_geographic(x, y)

    assert lat1 == pytest.approx(lat0, abs=1e-6)
    assert lon1 == pytest.approx(lon0, abs=1e-6)
