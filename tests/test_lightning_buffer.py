import math
import time

import pytest

import yaluk_network_lib.Network_lib as nl
from yaluk_network_lib.Lightning_lib.Lightning_stat import (
    Lightning_stat,
    _dist_point_to_segment,
)


def test_dist_point_to_segment_proyeccion_interior():
    # segmento horizontal (0,0)-(10,0); punto (5,3) -> distancia 3
    assert _dist_point_to_segment(5, 3, 0, 0, 10, 0) == 3.0


def test_dist_point_to_segment_mas_alla_del_extremo():
    # punto detras del extremo A -> distancia al extremo, no a la recta
    assert _dist_point_to_segment(-5, 4, 0, 0, 10, 0) == math.hypot(5, 4)


def test_dist_point_to_segment_vertical():
    assert _dist_point_to_segment(3, 5, 0, 0, 0, 10) == 3.0


def test_dist_point_to_segment_degenerado():
    # nodos iguales -> distancia euclidiana simple al punto
    assert _dist_point_to_segment(3, 4, 0, 0, 0, 0) == 5.0


def test_init_sin_lineas_lanza_valueerror_si_no_es_bbox():
    net = nl.Network()
    net.AddNode(0, 0, Nodeidx=1, ctype="abs")  # fija xmin/xmax; net.Lines sigue vacio
    with pytest.raises(ValueError, match="no hay lineas"):
        Lightning_stat(net, num_events=10, sampling="buffer_reject")


def test_init_bbox_no_requiere_lineas():
    # M distinto de "ProbDistribution"/"Database" cae en el catch-all
    # (Lightnings vacio, area del rectangulo) sin necesitar lineas.
    net = nl.Network()
    net.AddNode(0, 0, Nodeidx=1, ctype="abs")
    ls = Lightning_stat(net, num_events=0, M="OtroModoNoImplementado", sampling="bbox")
    assert ls.Area == pytest.approx((ls.Xmax - ls.Xmin) * (ls.Ymax - ls.Ymin))
    assert ls.Lightnings == []


def _net_dos_nodos():
    """Red minima: dos nodos unidos por una linea de 1000 m sobre el eje X,
    (0,0)-(1000,0)."""
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


def test_cobertura_buffer_reject_todos_los_puntos_dentro_del_corredor():
    net = _net_dos_nodos()   # linea (0,0)-(1000,0)
    ls = Lightning_stat(net, num_events=200, sampling="buffer_reject", buffer_radius=1000.0)
    for L in ls.Lightnings:
        assert ls._min_dist_to_lines(L.X_location, L.Y_location) <= 1000.0 + 1e-6


def test_cobertura_buffer_capsule_todos_los_puntos_dentro_del_corredor():
    net = _net_dos_nodos()
    ls = Lightning_stat(net, num_events=200, sampling="buffer_capsule", buffer_radius=1000.0)
    for L in ls.Lightnings:
        assert ls._min_dist_to_lines(L.X_location, L.Y_location) <= 1000.0 + 1e-6


def test_sampling_bbox_reproduce_rectangulo_legacy():
    net = _net_dos_nodos()
    ls = Lightning_stat(net, num_events=200, sampling="bbox")
    for L in ls.Lightnings:
        assert ls.Xmin <= L.X_location <= ls.Xmax
        assert ls.Ymin <= L.Y_location <= ls.Ymax
    assert ls.Area == pytest.approx((ls.Xmax - ls.Xmin) * (ls.Ymax - ls.Ymin))


def _net_zigzag(n_segments=300, seg_length=50.0):
    """Red de muchos segmentos cortos en linea recta sobre el eje X (mismo
    patron que _net_dos_nodos, escalado) -- similar en cantidad de
    segmentos a una red real (~289 en Example_big_branch), para reproducir
    el costo de _min_dist_to_lines (O(segmentos) por punto candidato)
    dentro de _sample_reject sin necesitar cargar un caso real completo."""
    net = nl.Network("uid_test_zigzag", "Test_Network_Zigzag")
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

    for i in range(n_segments + 1):
        net.AddNode(i * seg_length, 0, Nodeidx=i + 1, ctype="abs")
    for i in range(n_segments):
        net.AddLine(net.Nodes[i], net.Nodes[i + 1], config)
    return net


def test_sample_reject_con_muchos_segmentos_es_rapido():
    # Corredor real (~17.6% del bbox: 300 segmentos de 50m = 15km de largo,
    # bbox 17000x2000m por el margen `dist`=1000 default, buffer_radius=200m)
    # -- ni degenerado (siempre acepta) ni patologico (rechaza casi
    # siempre), mismo orden de tasa de aceptacion que un caso real.
    net = _net_zigzag(n_segments=300, seg_length=50.0)
    start = time.perf_counter()
    ls = Lightning_stat(
        net, num_events=1500, sampling="buffer_reject", buffer_radius=200.0
    )
    elapsed = time.perf_counter() - start

    assert len(ls.Lightnings) == 1500
    for L in ls.Lightnings:
        assert ls._min_dist_to_lines(L.X_location, L.Y_location) <= 200.0 + 1e-6

    # Antes de estos 4 fixes (_sample_reject_pool, check_direct_strike
    # vectorizado, CoordTransf cacheado, _impute_front_time sin reconstruir
    # lognorm() por llamada) este mismo escenario tardaba ~17s con el
    # codigo original -- ahora ~1.7s, dominado casi enteramente por
    # _compute_buffer_area (~1-1.2s, ya vectorizado desde antes, costo
    # unico necesario -- ver su propia historia de optimizacion en su
    # docstring). Cota generosa para no ser fragil ante variacion de maquina.
    assert elapsed < 3.0, f"tardo {elapsed:.1f}s -- se esperaban los 4 fixes de esta ronda"


def test_impute_front_time_coincide_con_formula_lognorm_original():
    # Referencia = la formula original tal cual estaba (construye lognorm()
    # dos veces), calculada aca con los mismos valores fijos que usa la
    # clase, para comparar bit a bit (o casi) contra _impute_front_time ya
    # optimizado -- ver verificacion numerica en el reporte (median exacto,
    # ppf con diff ~1e-15 via scipy.special.ndtri en vez de reconstruir
    # lognorm() por llamada).
    from scipy.stats import lognorm

    net = _net_dos_nodos()
    ls = Lightning_stat(net, num_events=0, sampling="bbox", M="OtroModoNoImplementado")
    ls._rng.seed(12345)
    q = ls._rng.random()  # el mismo random() que consumira _impute_front_time
    ls._rng.seed(12345)  # rebobinar para que _impute_front_time consuma el mismo q

    for Ix_kA in (5.0, 30.0):  # ambas ramas: <=20 y >20
        if Ix_kA > 20:
            Std_I, Mean_Ip = ls.std_dev_I2, ls.Mean_Ip_2
        else:
            Std_I, Mean_Ip = ls.std_dev_I1, ls.Mean_Ip_1
        Mean_I_ref = lognorm(s=Std_I, scale=math.exp(math.log(Mean_Ip))).median()
        Xtf = math.log(ls.Mean_tf) + ls.tf_correlation * ls.std_dev_tf / Std_I * (
            math.log(Ix_kA) - math.log(Mean_I_ref)
        )
        Std_tf = ls.std_dev_tf * math.sqrt(1 - ls.tf_correlation**2)
        ls._rng.seed(12345)
        front_time_ref = lognorm(s=Std_tf, scale=math.exp(Xtf)).ppf(ls._rng.random()) * 1e-6

        ls._rng.seed(12345)
        front_time, _ = ls._impute_front_time(Ix_kA)
        assert front_time == pytest.approx(front_time_ref, rel=1e-9)


def test_impute_front_time_no_reconstruye_lognorm_por_llamada():
    net = _net_dos_nodos()
    ls = Lightning_stat(net, num_events=0, sampling="bbox", M="OtroModoNoImplementado")
    start = time.perf_counter()
    for _ in range(1500):
        ls._impute_front_time(30.0)
    elapsed = time.perf_counter() - start
    # antes (reconstruye lognorm() dos veces por llamada) tardaba ~2.5s
    # para 1500 llamadas -- con math.exp/scipy.special.ndtri deberia ser
    # varios ordenes de magnitud mas rapido.
    assert elapsed < 0.2, f"tardo {elapsed:.2f}s -- se esperaba evitar reconstruir lognorm()"


def test_check_direct_strike_batch_coincide_con_referencia_por_rayo():
    # Network.check_direct_strike (SIN tocar) es la referencia -- se llama
    # una por una para cada rayo ya generado y se compara contra lo que
    # dejo Lightning_stat.check_direct_strike (vectorizado) en el propio
    # objeto Lightning. Red chica (20 segmentos) para que la referencia
    # punto-a-punto sea rapida de correr en el test.
    net = _net_zigzag(n_segments=20, seg_length=50.0)
    ls = Lightning_stat(net, num_events=25, sampling="buffer_reject", buffer_radius=200.0)

    assert len(ls.Lightnings) == 25
    for L in ls.Lightnings:
        ref_direct, ref_vrusck, ref_dist, ref_line = net.check_direct_strike(
            L.X_location, L.Y_location, L.Ih1
        )
        assert L.direc_strike == ref_direct
        assert L.min_dist == pytest.approx(ref_dist, rel=1e-9)
        assert L.line_id_nearest == ref_line
        if not ref_direct:
            assert L.Rusck_max_voltage == pytest.approx(ref_vrusck, rel=1e-9)


def test_uniformidad_reject_vs_capsule_misma_area():
    net = _net_dos_nodos()
    ls_a = Lightning_stat(net, num_events=2000, sampling="buffer_reject", buffer_radius=1000.0)
    ls_b = Lightning_stat(net, num_events=2000, sampling="buffer_capsule", buffer_radius=1000.0)
    # ambas estiman la misma area real del corredor (misma geometria),
    # dentro del error Monte Carlo de _compute_buffer_area (n=200000)
    assert ls_a.Area == pytest.approx(ls_b.Area, rel=0.05)
