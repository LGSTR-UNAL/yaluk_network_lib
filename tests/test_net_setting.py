import pytest
import pandas as pd

from yaluk_network_lib.Network_lib.net_setting import (
    build_conductors_db,
    build_configurations_db,
    network_setting,
)


def test_build_conductors_db_creates_conductor_per_row():
    cables = pd.DataFrame([
        {"id": "COND_4_0", "label": "Conductor 4/0",
         "description": "Conductor 4/0 AWG - catálogo CENTELSA",
         "radio": 0.0143, "resistance": 0.2667},
        {"id": "GUARDA_ACSR_110", "label": "Cable de guarda ACSR 110 KCMIL",
         "description": "Cable de guarda ACSR 110 KCMIL",
         "radio": 0.0061, "resistance": 0.5163},
    ])

    db = build_conductors_db(cables)

    assert set(db.keys()) == {"COND_4_0", "GUARDA_ACSR_110"}
    assert db["COND_4_0"].Radio == 0.0143
    assert db["COND_4_0"].Resistance == 0.2667
    assert db["COND_4_0"].Name == "Conductor 4/0"
    assert db["COND_4_0"].Description == "Conductor 4/0 AWG - catálogo CENTELSA"
    assert db["GUARDA_ACSR_110"].Radio == 0.0061
    assert db["GUARDA_ACSR_110"].Resistance == 0.5163


def _make_conductor(radio, resistance):
    import yaluk_network_lib.Network_lib as nl
    c = nl.Conductor()
    c.Radio = radio
    c.Resistance = resistance
    c.Name = "test"
    c.Description = "test"
    return c


def test_build_configurations_db_creates_configuration_per_row():
    conductors_db = {"COND_4_0": _make_conductor(0.0143, 0.2667)}
    config_types = pd.DataFrame([
        {"id": "R-580", "name": "R-580", "description": "Linea un solo conductor",
         "Geometry": "[('COND_4_0', 12, 2), ('COND_4_0', 12, 0), ('COND_4_0', 12, -2)]"},
    ])

    db = build_configurations_db(config_types, conductors_db)

    assert set(db.keys()) == {"R-580"}
    cfg = db["R-580"]
    assert cfg.Num_conductors == 3
    heights = [c.Height for c in cfg.Conductors._list]
    assert heights == [12, 12, 12]
    x_positions = [c.Relative_X_location for c in cfg.Conductors._list]
    assert x_positions == [2, 0, -2]


def test_build_configurations_db_unknown_conductor_raises():
    config_types = pd.DataFrame([
        {"id": "BAD", "name": "BAD", "description": "",
         "Geometry": "[('MISSING_ID', 12, 2)]"},
    ])

    with pytest.raises(ValueError, match="unknown conductor_id 'MISSING_ID'"):
        build_configurations_db(config_types, {})


def test_build_configurations_db_bad_geometry_literal_raises():
    config_types = pd.DataFrame([
        {"id": "BAD", "name": "BAD", "description": "", "Geometry": "not a literal"},
    ])

    with pytest.raises(ValueError, match="not a valid Python literal"):
        build_configurations_db(config_types, {})


def test_network_setting_wires_catalog_into_lines():
    Nodes = pd.DataFrame([
        {"id": 1, "label": "N1", "x": 1000.0, "y": 2000.0},
        {"id": 2, "label": "N2", "x": 1050.0, "y": 2000.0},
    ])
    Lines = pd.DataFrame([
        {"id": 1, "label": "L1", "from_node": "N1", "to_node": "N2", "configuration_type": "R-580"},
    ])
    Transformers = pd.DataFrame(columns=["id", "label", "from_node", "phases", "trf_type"])
    Surge_Arresters = pd.DataFrame(columns=["id", "label", "node", "phases", "file"])
    Trftype = pd.DataFrame(columns=["id", "CHV", "CLV", "CHL", "ground"])
    Cables = pd.DataFrame([
        {"id": "COND_4_0", "label": "Conductor 4/0", "description": "d",
         "radio": 0.0143, "resistance": 0.2667},
    ])
    Config_types = pd.DataFrame([
        {"id": "R-580", "name": "R-580", "description": "d",
         "Geometry": "[('COND_4_0', 12, 2), ('COND_4_0', 12, 0), ('COND_4_0', 12, -2)]"},
    ])

    net = network_setting(Nodes, Lines, Transformers, Surge_Arresters, Trftype,
                           Cables, Config_types, "TestNet")

    assert len(net.Lines) == 1
    assert net.Lines[0].Configuration.Num_conductors == 3
