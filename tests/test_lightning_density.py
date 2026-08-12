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


def _net_estrella():
    """3 brazos que salen de un centro C compartido (grado 3) -- C NO es
    terminal (aparece como extremo de las 3 lineas), las 3 puntas A/B/D si."""
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)
    config = _config_mono()
    net.AddNode(0, 0, Nodeidx=1, ctype="abs")        # C (centro)
    net.AddNode(500, 0, Nodeidx=2, ctype="abs")      # A
    net.AddNode(-500, 300, Nodeidx=3, ctype="abs")   # B
    net.AddNode(-500, -300, Nodeidx=4, ctype="abs")  # D
    net.AddLine(net.Nodes[0], net.Nodes[1], config)  # C-A
    net.AddLine(net.Nodes[0], net.Nodes[2], config)  # C-B
    net.AddLine(net.Nodes[0], net.Nodes[3], config)  # C-D
    return net


def _net_con_lateral():
    """Linea principal de 10 nodos (9 segmentos de 200 m, 1800 m total) con
    un lateral corto (1 segmento de 300 m) saliendo perpendicular del nodo
    en x=1000 (grado 3: dos tramos de la principal + el lateral)."""
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)
    config = _config_mono()
    for i in range(10):
        net.AddNode(i * 200.0, 0, Nodeidx=i + 1, ctype="abs")
    net.AddNode(1000.0, 300.0, Nodeidx=11, ctype="abs")  # punta del lateral
    for i in range(9):
        net.AddLine(net.Nodes[i], net.Nodes[i + 1], config)
    net.AddLine(net.Nodes[5], net.Nodes[10], config)  # lateral desde x=1000 (Nodes[5])
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


def test_compute_density_check_area_no_duplica_circulos_por_segmento_corto():
    # Un tramo de ~1000 m compuesto por 7 segmentos CORTOS (~143 m c/u, como
    # los tramos reales entre postes) con buffer_radius=1000 m: el area del
    # tramo tiene que ser la franja rectangular (2*r*L) MAS el casquete
    # completo de sus 2 extremos reales (son terminales, es el unico tramo),
    # NO la suma de 7 capsulas individuales (cada una con su propio circulo
    # pi*r^2 ~3.14 km^2 -- eso daria ~24 km^2, el bug real reportado por el
    # usuario contra el caso real: se veian ~11-12 km^2 por tramo de 1 km en
    # vez de los ~5 km^2 esperados aca).
    net = _net_linea(n_nodos=8, paso=1000.0 / 7)  # 7 segmentos, ~1000 m total
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=1000.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=1.0)
    assert result["n_tramos"] == 1
    rect_km2 = 2 * 1000.0 * 1000.0 / 1e6
    casquete_km2 = math.pi * 1000.0**2 / 1e6  # los 2 extremos son terminales -> circulo completo
    assert result["tramos"][0]["A_i_km2"] == pytest.approx(rect_km2 + casquete_km2, rel=0.02)


def test_compute_density_check_suma_de_tramos_es_consistente_con_el_buffer_total():
    # Sanity check pedido a raiz del hallazgo: para una linea recta (sin
    # ramificaciones), sumar el area de todos los tramos (franja rectangular
    # + casquete solo en los 2 tramos extremos) tiene que dar CASI
    # exactamente el area total del buffer -- no varias veces mas grande,
    # que es lo que pasaba con el bug de seg_weights.
    net = _net_linea(n_nodos=8, paso=1000.0 / 7)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=1000.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.2)
    suma_tramos_km2 = sum(t["A_i_km2"] for t in result["tramos"])
    assert suma_tramos_km2 == pytest.approx(result["A_buffer_km2"], rel=0.05)


def test_compute_density_check_un_solo_tramo_terminal_en_ambos_extremos_incluye_el_circulo_completo():
    # Isla corta de un solo segmento: los dos extremos son terminales (grado
    # 1), asi que el tramo unico debe llevar el CASQUETE COMPLETO (los dos
    # medios circulos de cada punta), igual que el capsula analitica exacta
    # que ya usa seg_weights para un solo segmento.
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=1000.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=5.0)  # n=1
    assert result["n_tramos"] == 1
    assert result["tramos"][0]["A_i_km2"] == pytest.approx(ls.seg_weights[0] / 1e6)


def test_compute_density_check_solo_los_tramos_extremos_llevan_casquete():
    net = _net_linea(n_nodos=5, paso=250.0)  # 4 segmentos de 250 m
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.25)  # n=4, 1 segmento/tramo
    assert result["n_tramos"] == 4
    areas = [t["A_i_km2"] for t in result["tramos"]]
    rect_only = (2 * 100.0 * 250.0) / 1e6
    con_casquete = rect_only + (math.pi * 100.0**2 / 2) / 1e6
    assert areas[0] == pytest.approx(con_casquete)   # primer tramo: extremo real
    assert areas[1] == pytest.approx(rect_only)       # tramo interno: sin casquete
    assert areas[2] == pytest.approx(rect_only)       # tramo interno: sin casquete
    assert areas[3] == pytest.approx(con_casquete)    # ultimo tramo: extremo real


# NOTA: el escenario de "un punto de grado>=3 no debe contar como terminal"
# ahora esta cubierto por el camino de cluster de bifurcacion, no por el
# conteo de terminales -- ver test_compute_density_check_bifurcacion_*
# mas abajo (agrupan la estrella en un tramo con area por union geometrica).


def test_compute_density_check_excluye_terminales_marcados_como_puntos_de_corte():
    # Un punto de corte artificial (limite de un area particionada,
    # terminado con R=Zc) es degree 1 DENTRO de este sub-caso, pero NO es un
    # extremo real de la linea -- el corredor sigue en el area vecina.
    # excluded_terminal_points lo deja afuera del casquete aunque localmente
    # parezca terminal (evita el sobre-conteo real medido en areas
    # particionadas del caso real: el casquete se sumaba tambien en cada
    # punto de corte, empeorando la sobreestimacion en vez de mejorarla).
    net = _net_linea(n_nodos=5, paso=250.0)  # 4 segmentos de 250 m
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    punto_de_corte = (0.0, 0.0)  # extremo del primer nodo (x=0, y=0)
    result = ls.compute_density_check(
        Ng_real=1.0, segment_length_km=0.25,
        excluded_terminal_points={punto_de_corte},
    )
    rect_only = (2 * 100.0 * 250.0) / 1e6
    con_casquete = rect_only + (math.pi * 100.0**2 / 2) / 1e6
    assert result["tramos"][0]["A_i_km2"] == pytest.approx(rect_only)      # excluido -> sin casquete
    assert result["tramos"][3]["A_i_km2"] == pytest.approx(con_casquete)   # extremo real -> con casquete


def test_compute_density_check_bifurcacion_se_agrupa_en_un_solo_tramo_con_area_real():
    # Los 3 brazos de la estrella tocan directamente el centro (grado 3) ->
    # los 3 segmentos entran al mismo cluster de bifurcacion y se reportan
    # como UN SOLO tramo, con el area real (union geometrica), no la suma
    # de 3 franjas+casquetes independientes (que exagera el solape cerca
    # del centro).
    from shapely.geometry import LineString
    from shapely.ops import unary_union

    net = _net_estrella()
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.1)
    assert result["n_tramos"] == 1

    union = unary_union([
        LineString([(ax, ay), (bx, by)]).buffer(100.0) for (ax, ay, bx, by) in ls.segments
    ])
    assert result["tramos"][0]["A_i_km2"] == pytest.approx(union.area / 1e6, rel=1e-6)

    # El area real tiene que ser MENOR que sumar 3 franjas+casquete
    # independientes (el bug que se queria evitar: contar el solape cerca
    # del centro varias veces).
    naive_km2 = sum(
        (2 * 100.0 * math.hypot(bx - ax, by - ay) + math.pi * 100.0**2 / 2) / 1e6
        for (ax, ay, bx, by) in ls.segments
    )
    assert result["tramos"][0]["A_i_km2"] < naive_km2


def test_compute_density_check_bifurcacion_lejos_de_tramos_rectos_no_los_afecta():
    # Solo los segmentos CERCA de la bifurcacion (dentro de buffer_radius)
    # se agrupan en el tramo de cluster; el resto de la linea recta, lejos
    # del nodo de grado 3, sigue con los tramos normales de siempre.
    net = _net_con_lateral()  # rama de grado 3 en x=1000, buffer_radius=100
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.7)
    # 1 tramo de cluster (los 3 segmentos que tocan el nodo x=1000) + los
    # tramos normales de los 1400 m de linea recta que quedan afuera.
    assert result["n_tramos"] > 1
    assert result["m_t"] == sum(t["m_i"] for t in result["tramos"])

    # Un rayo lejos de la bifurcacion (extremo x=0) tiene que caer en un
    # tramo NORMAL (franja rectangular), no en el tramo de cluster de la
    # bifurcacion -- el cluster siempre se agrega al final de la lista.
    ls.Lightnings = [_rayo(10, 0)]
    result2 = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.7)
    tramo_con_rayo = next(t for t in result2["tramos"] if t["m_i"] == 1)
    cluster_tramo = result2["tramos"][-1]
    assert tramo_con_rayo["tramo"] != cluster_tramo["tramo"]


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
