"""write_misc_file (Project_lib/proj_functions.py) debe respetar
Soil_settings.Perfectsoil.

Bug real encontrado documentando los parametros de sim_settings.csv
(2026-08-15): catalog_io.py castea la fila `Soil,Perfectsoil,...` como el
atributo `Soil_settings.Perfectsoil` (con mayuscula, igual que Conductivity/
Permitivity), pero write_misc_file leia `Soil_settings.perfect_soil`
(minuscula, el atributo original de Soil.__init__) -- un mismatch de
nombre que hacia que la fila `Perfectsoil` del archivo no tuviera ningun
efecto sobre el `miscelaneo.txt` generado.
"""

import yaluk_network_lib.Network_lib as nl
import yaluk_network_lib.Project_lib as yp


def _proj_settings(perfectsoil):
    settings = yp.ProjectSettings()
    # Mismo patron que catalog_io.py: en uso real, el catalogo base de
    # sim_settings.csv SIEMPRE setea estos 3 atributos en PascalCase (con
    # setattr), incluso sin ningun archivo subido por el usuario -- un
    # ProjectSettings() recien construido no los trae (solo su version
    # lowercase, sin usar). Se replican aca para no depender de catalog_io
    # en un test de yaluk_network_lib, que no lo importa.
    settings.Soil_settings.Conductivity = settings.Soil_settings.conductivity
    settings.Soil_settings.Permitivity = settings.Soil_settings.permitivity
    settings.Soil_settings.Perfectsoil = perfectsoil
    return settings


def _red_minima():
    net = nl.Network("uid_test", "Test_Network")
    net.InitXY = nl.PointXY(0, 0)
    return net


def test_perfectsoil_true_desactiva_la_conductividad():
    settings = _proj_settings(perfectsoil=True)
    net = _red_minima()

    misc = yp.write_misc_file(settings, net, buffer=True)

    linea_conductividad = misc.read().decode().splitlines()[5]
    assert linea_conductividad.startswith("0 "), (
        f"con Perfectsoil=True, 'Conductividad activa' debe ser 0 -- linea real: {linea_conductividad!r}"
    )


def test_perfectsoil_false_mantiene_la_conductividad_activa():
    settings = _proj_settings(perfectsoil=False)
    net = _red_minima()

    misc = yp.write_misc_file(settings, net, buffer=True)

    linea_conductividad = misc.read().decode().splitlines()[5]
    assert linea_conductividad.startswith("1 "), (
        f"con Perfectsoil=False, 'Conductividad activa' debe ser 1 -- linea real: {linea_conductividad!r}"
    )
