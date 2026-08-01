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
