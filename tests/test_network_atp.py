"""ATP sin rayo asociado (generacion de diagnostico)."""

from Network_lib.Network import Network


def test_makeatpbuffer_sin_rayo_no_hereda_impacto_directo():
    """La instancia de Network se reutiliza entre rayos. Si el ultimo fue un
    impacto directo y despues se pide un ATP sin rayo, write_sources entraba a
    la rama de impacto directo y desreferenciaba stroke.Ih1 sobre None. Visto
    como falla intermitente en la suite de yaluk-server (RNG sin semilla: solo
    fallaba cuando el ultimo rayo salia directo)."""
    net = Network("uid_test", "linea_test")
    net.direct_strike = True  # estado dejado por un rayo directo anterior

    try:
        net.MakeATPBuffer()
    except AttributeError as exc:
        if "Ih1" in str(exc):
            raise AssertionError(
                "MakeATPBuffer() sin rayo heredo el direct_strike anterior"
            ) from exc
    except Exception:
        pass  # otros fallos (red vacia) no son lo que este test verifica

    assert net.direct_strike is False
