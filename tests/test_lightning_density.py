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


def _net_curva(n_segments=7, seg_length=140.0, angle_deg_per_seg=8.0):
    """Cadena de `n_segments` segmentos SIN ninguna bifurcacion (grado 2 en
    todos los nodos internos) que gira `angle_deg_per_seg` grados en cada
    poste -- ~140 m entre postes y ~8 grados de giro acumulado por tramo son
    realistas para una red de distribucion real que sigue el trazado de una
    via/terreno (no una linea perfectamente recta)."""
    net = nl.Network("uid_test", "Test_Network_Curva")
    net.InitXY = nl.PointXY(0, 0)
    config = _config_mono()
    pts = [(0.0, 0.0)]
    heading = 0.0
    for i in range(n_segments):
        heading += math.radians(angle_deg_per_seg)
        x, y = pts[-1]
        pts.append((x + seg_length * math.cos(heading), y + seg_length * math.sin(heading)))
    for i, (x, y) in enumerate(pts):
        net.AddNode(x, y, Nodeidx=i + 1, ctype="abs")
    for i in range(n_segments):
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


def test_compute_density_check_area_no_duplica_circulos_por_segmento_corto():
    # Un tramo de ~1000 m compuesto por 7 segmentos CORTOS (~143 m c/u, como
    # los tramos reales entre postes) con buffer_radius=1000 m: el area del
    # tramo tiene que ser la franja rectangular (2*r*L) MAS el casquete
    # completo de sus 2 extremos reales (son terminales, es el unico tramo),
    # NO la suma de 7 capsulas individuales (cada una con su propio circulo
    # pi*r^2 ~3.14 km^2 -- eso daria ~24 km^2, el bug real reportado por el
    # usuario contra el caso real: se veian ~11-12 km^2 por tramo de 1 km en
    # vez de los ~5 km^2 esperados aca). rel=0.05: el area ahora se estima
    # por Monte Carlo (ver compute_density_check, punto 4 de su historia),
    # no una formula analitica exacta -- tolerancia de muestreo, no de bug.
    net = _net_linea(n_nodos=8, paso=1000.0 / 7)  # 7 segmentos, ~1000 m total
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=1000.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=1.0)
    assert result["n_tramos"] == 1
    rect_km2 = 2 * 1000.0 * 1000.0 / 1e6
    casquete_km2 = math.pi * 1000.0**2 / 1e6  # los 2 extremos son terminales -> circulo completo
    assert result["tramos"][0]["A_i_km2"] == pytest.approx(rect_km2 + casquete_km2, rel=0.05)


def test_compute_density_check_suma_de_tramos_es_consistente_con_el_buffer_total():
    # Sanity check pedido a raiz del hallazgo original de seg_weights: la
    # suma del area de todos los tramos tiene que dar EXACTAMENTE el area
    # total del buffer, no varias veces mas grande. Con el area estimada
    # por Monte Carlo esto ya no es una aproximacion sino una identidad:
    # cada punto aceptado del muestreo cae en UN solo tramo (via
    # nearest_segment_index), asi que sumar count/total*A_buffer sobre
    # todos los tramos da A_buffer exacto (salvo redondeo de punto flotante).
    net = _net_linea(n_nodos=8, paso=1000.0 / 7)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=1000.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.2)
    suma_tramos_km2 = sum(t["A_i_km2"] for t in result["tramos"])
    assert suma_tramos_km2 == pytest.approx(result["A_buffer_km2"], rel=1e-9)


def test_compute_density_check_un_solo_tramo_terminal_en_ambos_extremos_incluye_el_circulo_completo():
    # Isla corta de un solo segmento: el unico tramo cubre TODA la red, asi
    # que su area (Monte Carlo) tiene que converger al area total del
    # buffer -- que a su vez converge (ver test_buffer_area_dinamico_*) a la
    # capsula analitica exacta (2*r*L + pi*r^2) que ya usa seg_weights para
    # un solo segmento.
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=1000.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=5.0)  # n=1
    assert result["n_tramos"] == 1
    assert result["tramos"][0]["A_i_km2"] == pytest.approx(ls.seg_weights[0] / 1e6, rel=0.05)


def test_compute_density_check_solo_los_tramos_extremos_llevan_casquete():
    net = _net_linea(n_nodos=5, paso=250.0)  # 4 segmentos de 250 m
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.25)  # n=4, 1 segmento/tramo
    assert result["n_tramos"] == 4
    areas = [t["A_i_km2"] for t in result["tramos"]]
    rect_only = (2 * 100.0 * 250.0) / 1e6
    con_casquete = rect_only + (math.pi * 100.0**2 / 2) / 1e6
    # rel=0.1: 4 tramos comparables en tamano compiten por el mismo
    # presupuesto de muestras Monte Carlo -- tolerancia de muestreo.
    assert areas[0] == pytest.approx(con_casquete, rel=0.1)   # primer tramo: extremo real
    assert areas[1] == pytest.approx(rect_only, rel=0.1)       # tramo interno: sin casquete
    assert areas[2] == pytest.approx(rect_only, rel=0.1)       # tramo interno: sin casquete
    assert areas[3] == pytest.approx(con_casquete, rel=0.1)    # ultimo tramo: extremo real


# NOTA: el escenario de "un punto de grado>=3 no debe contar como terminal"
# ahora esta cubierto por el camino de cluster de bifurcacion, no por el
# conteo de terminales -- ver test_compute_density_check_bifurcacion_*
# mas abajo.


def test_compute_density_check_tramo_normal_curvo_no_usa_franja_recta():
    # Hallazgo real (2026-08-18, corrida real de 20000 rayos: varios tramos
    # NORMALES -- sin ninguna bifurcacion cerca -- con Ng_i hasta -47% por
    # debajo de Ng_real). La franja rectangular (2*r*L) asume que el tramo
    # es recto; en una red real que sigue el trazado de una via/terreno, un
    # tramo con una curva (aunque sea suave, sin bifurcacion) tiene un area
    # de buffer VERDADERA menor que la franja recta -- el area real se
    # solapa consigo misma en el interior de la curva. Con 20 segmentos de
    # ~140 m y 15 grados de giro por poste (realista), la franja recta
    # sobreestima el area real en mas de un 15%.
    net = _net_curva(n_segments=20, seg_length=140.0, angle_deg_per_seg=15.0)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=1000.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=5.0)  # n=1: toda la curva en un solo tramo
    assert result["n_tramos"] == 1

    length_m = sum(math.hypot(bx - ax, by - ay) for (ax, ay, bx, by) in ls.segments)
    franja_recta_km2 = (2 * 1000.0 * length_m + math.pi * 1000.0**2) / 1e6  # naive + 2 terminales

    assert result["tramos"][0]["A_i_km2"] < franja_recta_km2 * 0.85  # la franja recta sobreestima >15%


def test_compute_density_check_bifurcacion_se_agrupa_en_un_solo_tramo_con_area_real():
    # Los 3 brazos de la estrella tocan directamente el centro (grado 3) ->
    # los 3 segmentos entran al mismo cluster de bifurcacion y se reportan
    # como UN SOLO tramo, con el area real (Monte Carlo), no la suma de 3
    # franjas+casquetes independientes (que exagera el solape cerca del
    # centro).
    net = _net_estrella()
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.1)
    assert result["n_tramos"] == 1

    # El area real tiene que ser MENOR que sumar 3 franjas+casquete
    # independientes (el bug que se queria evitar: contar el solape cerca
    # del centro varias veces).
    naive_km2 = sum(
        (2 * 100.0 * math.hypot(bx - ax, by - ay) + math.pi * 100.0**2 / 2) / 1e6
        for (ax, ay, bx, by) in ls.segments
    )
    assert result["tramos"][0]["A_i_km2"] < naive_km2


def test_compute_density_check_tramos_cercanos_no_adyacentes_no_se_pisan():
    # Hallazgo principal de la investigacion (2026-08-18, corrida real de
    # 20000 rayos): incluso con la union geometrica correcta de curvas y
    # bifurcaciones, 3 tramos de esa corrida seguian con Ng_i hasta -49%
    # por debajo de Ng_real, sin tener ninguna curva pronunciada. Causa:
    # dos tramos NO adyacentes en el indice de self.segments pueden estar
    # geometricamente CERCA en el espacio (un recodo o paralelismo real de
    # la red) -- el area de un tramo aislado no puede saber que parte de su
    # "propio" corredor en realidad esta mas cerca de OTRO tramo, que se
    # queda con esos rayos via nearest_segment_index (la misma regla que
    # asigna los rayos reales). Repro minimo: 2 segmentos paralelos de
    # 1000 m, SIN conectar entre si (islas separadas, para aislar el
    # efecto), a solo 50 m de distancia con buffer_radius=100 m (2*r=200 >
    # 50 -> sus corredores se solapan bastante en el medio).
    net = nl.Network("uid_test", "Test_Network_Paralelas")
    net.InitXY = nl.PointXY(0, 0)
    config = _config_mono()
    net.AddNode(0.0, 0.0, Nodeidx=1, ctype="abs")
    net.AddNode(0.0, 1000.0, Nodeidx=2, ctype="abs")
    net.AddNode(50.0, 0.0, Nodeidx=3, ctype="abs")
    net.AddNode(50.0, 1000.0, Nodeidx=4, ctype="abs")
    net.AddLine(net.Nodes[0], net.Nodes[1], config)  # pierna A: x=0
    net.AddLine(net.Nodes[2], net.Nodes[3], config)  # pierna B: x=50

    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=1.0)
    assert result["n_tramos"] == 2

    # La suma de las 2 areas tiene que dar (casi) exactamente el area total
    # del corredor -- por construccion del metodo Monte Carlo (cada punto
    # aceptado cae en UN tramo), a diferencia de calcular cada pierna por
    # separado (union geometrica aislada, el metodo que este caso dejo de
    # usar), que SI se solaparia entre las 2 piernas.
    suma_km2 = sum(t["A_i_km2"] for t in result["tramos"])
    assert suma_km2 == pytest.approx(result["A_buffer_km2"], rel=1e-6)

    # La franja+casquete de UNA pierna aislada (el area que le habria dado
    # el metodo geometrico anterior, sin saber de la pierna vecina) tiene
    # que ser bien mayor que lo que el codigo real le asigna -- la mitad
    # del ancho solapado (donde 50 < 2*100) en realidad le pertenece a la
    # OTRA pierna.
    aislada_km2 = (2 * 100.0 * 1000.0 + math.pi * 100.0**2) / 1e6
    for t in result["tramos"]:
        assert t["A_i_km2"] < aislada_km2 * 0.85


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
    assert result["L_lin_km"] == pytest.approx(1.0)


def test_compute_density_check_ng_i_esta_normalizado_por_tsim():
    # Ng_i tiene que estar en las mismas unidades que Ng_real (rayos/km2/año),
    # no en rayos/km2 "crudo" acumulados durante los T_sim años simulados --
    # sin dividir por T_sim_years, Ng_i queda T_sim veces mas grande que
    # Ng_real para cualquier T_sim != 1 (bug real reportado por el usuario:
    # la comparacion Ng_i vs Ng_real en la UI asume que estan normalizados
    # igual).
    net = _net_dos_nodos(1000.0)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    ls.Lightnings = [_rayo(10, 0) for _ in range(20)]
    result = ls.compute_density_check(Ng_real=2.0, segment_length_km=5.0)  # n=1
    assert result["n_tramos"] == 1
    tramo = result["tramos"][0]
    assert result["T_sim_years"] == pytest.approx(20 / (2.0 * result["A_buffer_km2"]))
    ng_i_crudo = tramo["m_i"] / tramo["A_i_km2"]
    assert tramo["Ng_i"] == pytest.approx(ng_i_crudo / result["T_sim_years"])
    # Un unico tramo que cubre toda la linea (m_i == m_t) tiene que dar un
    # Ng_i normalizado cercano a Ng_real -- la franja rectangular+casquete
    # es una buena aproximacion del area Monte Carlo real sin bifurcaciones.
    assert tramo["Ng_i"] == pytest.approx(2.0, rel=0.05)


def test_compute_density_check_l_lin_km_suma_todos_los_segmentos():
    # 4 segmentos de 250 m = 1000 m = 1.0 km en total, repartidos en 2 tramos.
    net = _net_linea(n_nodos=5, paso=250.0)
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=0.5)
    assert result["L_lin_km"] == pytest.approx(1.0)


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


def test_compute_density_check_no_genera_tramo_fantasma_vacio():
    # Hallazgo real (caso 216-13_a04/a06 del caso real, reproducido aca sin
    # depender de esa geometria): el bucketing por longitud acumulada hace
    # `bucket_indices.append(current)` sin condicion al final del bucle --
    # si el ultimo flush intermedio (el que llega a n-1 buckets) consume
    # justo el ultimo segmento de la red, "current" queda vacio y se agrega
    # como un tramo fantasma (m_i=0, A_i_km2=0.0), inflando n_tramos sin
    # representar ningun segmento real. Repro minimo: 4 segmentos iguales
    # (250 m c/u, 1000 m total) pidiendo 3 tramos via segment_length_km=1/3
    # -> bucketize da [2, 2, 0] antes del fix.
    net = _net_linea(n_nodos=5, paso=250.0)  # 4 segmentos de 250 m, linea de 1000 m
    ls = Lightning_stat(net, num_events=0, sampling="buffer_reject", buffer_radius=100.0)
    ls.Lightnings = [_rayo(10, 0), _rayo(900, 0)]
    result = ls.compute_density_check(Ng_real=1.0, segment_length_km=1.0 / 3.0)
    assert all(t["A_i_km2"] > 0 for t in result["tramos"])
    assert result["n_tramos"] == 2  # 2 tramos reales de 2 segmentos c/u, no 3 con uno vacio
