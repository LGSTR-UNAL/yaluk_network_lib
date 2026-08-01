import io
import math
import random

import pytest

import yaluk_network_lib.Network_lib as nl
from yaluk_network_lib.Lightning_lib.Lightning_stat import Lightning_stat


def _net_dos_nodos():
    """Red minima: dos nodos unidos por una linea de 1000 m sobre el eje X,
    (0,0)-(1000,0). Igual al helper de tests/test_lightning_buffer.py."""
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

    net.AddNode(0, 0, Nodeidx=1, ctype="abs")
    net.AddNode(1000, 0, Nodeidx=2, ctype="abs")
    net.AddLine(net.Nodes[0], net.Nodes[1], config)
    return net


def test_impute_front_time_coincide_con_formula_manual():
    from scipy.stats import lognorm

    net = _net_dos_nodos()
    ls_obj = Lightning_stat(net, num_events=1, sampling="bbox")

    Ix_kA = 15.0  # < 20 -> rama std_dev_I1/Mean_Ip_1
    Std_I = ls_obj.std_dev_I1
    Mean_I = lognorm(
        s=ls_obj.std_dev_I1, scale=math.exp(math.log(ls_obj.Mean_Ip_1))
    ).median()
    Xtf = math.log(ls_obj.Mean_tf) + ls_obj.tf_correlation * ls_obj.std_dev_tf / Std_I * (
        math.log(Ix_kA) - math.log(Mean_I)
    )
    Std_tf = ls_obj.std_dev_tf * math.sqrt(1 - ls_obj.tf_correlation ** 2)
    rng_snapshot = random.Random(42)
    expected_front_time = (
        lognorm(s=Std_tf, scale=math.exp(Xtf)).ppf(rng_snapshot.random()) * 1e-6
    )
    expected_tf1 = (
        expected_front_time ** (ls_obj.n1 + 1) / (ls_obj.n1 * ls_obj.tc)
    ) ** (1 / ls_obj.n1)

    ls_obj._rng = random.Random(42)  # reproducibilidad solo para este test
    front_time, tf1 = ls_obj._impute_front_time(Ix_kA)
    assert front_time == pytest.approx(expected_front_time)
    assert tf1 == pytest.approx(expected_tf1)


def test_impute_front_time_rama_corriente_alta():
    # Ix > 20 -> usa std_dev_I2/Mean_Ip_2, no debe lanzar excepcion
    net = _net_dos_nodos()
    ls_obj = Lightning_stat(net, num_events=1, sampling="bbox")
    ls_obj._rng = random.Random(1)
    front_time, tf1 = ls_obj._impute_front_time(35.0)
    assert front_time > 0
    assert tf1 > 0


def test_coordtransf_conversion_relativa_a_initxy():
    from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf

    # Network() SIN override de InitXY: InitXY se calcula proyectando
    # InitLatLong (Network.py:74-77) -> proyectar ese mismo punto debe dar
    # exactamente (InitXY.X, InitXY.Y).
    net = nl.Network()
    transf = CoordTransf()
    xp, yp = transf.to_projected(net.InitLatLong.Lat, net.InitLatLong.Lng)
    assert xp == pytest.approx(net.InitXY.X, abs=1e-6)
    assert yp == pytest.approx(net.InitXY.Y, abs=1e-6)


def _csv_lls(rows):
    lines = ["lat,lon,current_kA,timestamp"]
    for r in rows:
        lines.append(",".join(str(v) for v in r))
    return io.BytesIO(("\n".join(lines) + "\n").encode())


def test_load_from_database_filtra_por_corredor():
    net = _net_dos_nodos()  # linea (0,0)-(1000,0), InitLatLong = Network() default
    from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf
    transf = CoordTransf()

    def latlon_for_xy(x_rel, y_rel):
        # inverso de to_projected, para fabricar filas LLS en una posicion XY
        # relativa conocida (dentro/fuera del corredor de 1 km default).
        x_abs = x_rel + net.InitXY.X
        y_abs = y_rel + net.InitXY.Y
        lat, lon = transf.to_geographic(x_abs, y_abs)
        return lat, lon

    lat_dentro, lon_dentro = latlon_for_xy(500.0, 100.0)   # a 100 m de la linea -> dentro (<=1000)
    lat_fuera, lon_fuera = latlon_for_xy(500.0, 5000.0)    # a 5000 m -> fuera del corredor

    buf = _csv_lls([
        (lat_dentro, lon_dentro, 25.3, "2026-01-01T00:00:00Z"),
        (lat_fuera, lon_fuera, 40.0, "2026-01-01T00:01:00Z"),
    ])

    ls_obj = Lightning_stat(net, M="Database", database_buffer=buf)
    assert len(ls_obj.Lightnings) == 1
    Li = ls_obj.Lightnings[0]
    assert Li.Ih1 == pytest.approx(25.3 * 1000)
    assert Li.X_location == pytest.approx(500.0, abs=1.0)
    assert Li.Y_location == pytest.approx(100.0, abs=1.0)
    assert Li.tf1 > 0
    assert Li.Front_time > 0


def test_load_from_database_descarta_filas_invalidas():
    net = _net_dos_nodos()
    from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf
    transf = CoordTransf()
    x_abs, y_abs = 500.0 + net.InitXY.X, 100.0 + net.InitXY.Y
    lat_ok, lon_ok = transf.to_geographic(x_abs, y_abs)

    buf = io.BytesIO((
        "lat,lon,current_kA,timestamp\n"
        f"{lat_ok},{lon_ok},18.0,2026-01-01T00:00:00Z\n"
        "not_a_number,also_bad,0,2026-01-01T00:01:00Z\n"
        f"{lat_ok},{lon_ok},0,2026-01-01T00:02:00Z\n"
    ).encode())

    ls_obj = Lightning_stat(net, M="Database", database_buffer=buf)
    assert len(ls_obj.Lightnings) == 1  # las otras 2 filas se descartan


def test_load_from_database_descarta_filas_con_nan():
    # float('nan') no lanza excepcion al convertir, y las comparaciones con
    # NaN dan False -- sin el chequeo explicito de isfinite(), una fila con
    # lat/lon NaN pasaria el filtro del corredor silenciosamente.
    net = _net_dos_nodos()
    from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf
    transf = CoordTransf()
    x_abs, y_abs = 500.0 + net.InitXY.X, 100.0 + net.InitXY.Y
    lat_ok, lon_ok = transf.to_geographic(x_abs, y_abs)

    buf = io.BytesIO((
        "lat,lon,current_kA,timestamp\n"
        f"{lat_ok},{lon_ok},18.0,2026-01-01T00:00:00Z\n"
        ",,25.0,2026-01-01T00:01:00Z\n"  # lat/lon vacios -> NaN tras read_csv
    ).encode())

    ls_obj = Lightning_stat(net, M="Database", database_buffer=buf)
    assert len(ls_obj.Lightnings) == 1


def test_load_from_database_cero_rayos_en_corredor_lanza_valueerror():
    net = _net_dos_nodos()
    from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf
    transf = CoordTransf()
    x_abs, y_abs = 500.0 + net.InitXY.X, 50000.0 + net.InitXY.Y  # muy lejos
    lat_lejos, lon_lejos = transf.to_geographic(x_abs, y_abs)

    buf = _csv_lls([(lat_lejos, lon_lejos, 25.0, "2026-01-01T00:00:00Z")])
    with pytest.raises(ValueError, match="cero rayos"):
        Lightning_stat(net, M="Database", database_buffer=buf)
