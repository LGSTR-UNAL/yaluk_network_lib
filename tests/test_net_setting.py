import pandas as pd

from yaluk_network_lib.Network_lib.net_setting import build_conductors_db


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
