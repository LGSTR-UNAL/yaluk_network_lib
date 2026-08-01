"""
Ejemplo: ingesta de rayos reales desde un archivo LLS.

Muestra como `Lightning_stat(net, M="Database", database_buffer=...)`
reemplaza el modelo estadistico (M="ProbDistribution") por rayos reales de
un sistema de localizacion de rayos (LLS), filtrados por el mismo corredor
alrededor de las lineas que usa el modo estadistico
(`buffer_radius`, default 1 km).

IMPORTANTE (coordenadas): en `yaluk-server/main.py::network_setting()`,
`net.InitXY` se fija directo desde las coordenadas locales de
`structures.csv`/`vertices.txt` (un sistema de coordenadas propio del caso,
NO el mismo que usa `CoordTransf`/EPSG:9377), mientras `net.InitLatLong`
queda en el valor default de `Network()` sin actualizarse -- ver
`context/reports/2026-08-01-ingesta-rayos-reales-lls.md`. Esto rompe la
conversion lat/lon -> XY relativo de `LoadFromDatabase` para el pipeline
real tal como esta hoy. Este ejemplo, en cambio, SI mantiene `InitXY`
consistente con `InitLatLong` (se deriva proyectando el mismo punto), que es
el patron correcto a seguir si se integra este modo en un flujo nuevo.

Correr: `python -m yaluk_network_lib.examples.example_lls_ingestion` desde
`src_libs` (el paquete se resuelve por nombre, igual que en los tests via
conftest.py; `python examples/example_lls_ingestion.py` directo no
funciona porque no agrega `src_libs` a sys.path).
"""
import io

import pandas as pd

import yaluk_network_lib.Network_lib as nl
import yaluk_network_lib.Lightning_lib as ls
from yaluk_network_lib.Network_lib.GeoTransform import CoordTransf, PointLatLng


def build_small_network():
    """Red de 3 nodos / 2 lineas (~300 m), georreferenciada cerca de
    Medellin (6.20 N, -75.40 W). InitXY se deriva proyectando InitLatLong
    (no se sobreescribe con coordenadas locales sueltas, ver nota del
    modulo) y los nodos se agregan con ctype="rel" (metros desde InitXY)."""
    net = nl.Network("uid_lls_example", "LLS_Example")
    net.InitLatLong = PointLatLng(6.20, -75.40)
    x0, y0 = CoordTransf().to_projected(net.InitLatLong.Lat, net.InitLatLong.Lng)
    net.InitXY = nl.PointXY(x0, y0)

    conductor = nl.Conductor()
    conductor.Radio = 0.0143
    conductor.Resistance = 0.2667
    conductor.Name = "Conductor 4/0"
    conductor.Description = "Conductor 4/0 AWG - catalogo CENTELSA"

    config = nl.Configuration_Type()
    config.id = "LAR1"
    config.Name = "Mono LAR1"
    config.Description = "Linea un solo conductor"
    config.Add_conductor(conductor, 10, 0)
    config.gen_parameters()

    net.AddNode(0, 0, Nodeidx=1, ctype="rel")
    net.AddNode(150, 0, Nodeidx=2, ctype="rel")
    net.AddNode(300, 50, Nodeidx=3, ctype="rel")
    net.AddLine(net.Nodes[0], net.Nodes[1], config)
    net.AddLine(net.Nodes[1], net.Nodes[2], config)
    return net


def make_sample_lls_csv(net) -> io.BytesIO:
    """Fabrica un CSV LLS de ejemplo con 4 filas: 2 rayos reales dentro del
    corredor de 1 km (se simulan), uno muy lejos y uno con datos invalidos
    (ambos se descartan por el filtro espacial / de validez)."""
    transf = CoordTransf()

    def latlon_near(x_rel, y_rel):
        # Inverso de to_projected, para fabricar una fila LLS en una
        # posicion XY relativa conocida. CoordTransf.to_geographic() tiene
        # un bug real conocido (devuelve (lon,lat) pero los nombra lat,lon,
        # ver reporte de la sesion 2026-08-01) -- se corrige aqui con un
        # swap explicito.
        x_abs, y_abs = x_rel + net.InitXY.X, y_rel + net.InitXY.Y
        raw_lon, raw_lat = transf.to_geographic(x_abs, y_abs)
        return raw_lat, raw_lon

    rows = []
    lat, lon = latlon_near(50, 30)        # cerca de la primera linea -> dentro del corredor
    rows.append((lat, lon, 22.5, "2026-01-15T03:12:00Z"))
    lat, lon = latlon_near(200, -10)      # cerca de la segunda linea -> dentro del corredor
    rows.append((lat, lon, 41.0, "2026-01-15T03:14:30Z"))
    lat, lon = latlon_near(5000, 5000)    # muy lejos -> se descarta (fuera del buffer_radius)
    rows.append((lat, lon, 15.0, "2026-01-15T03:20:00Z"))
    rows.append((float("nan"), float("nan"), 30.0, "2026-01-15T03:22:00Z"))  # datos invalidos -> se descarta

    df = pd.DataFrame(rows, columns=["lat", "lon", "current_kA", "timestamp"])
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


if __name__ == "__main__":
    net = build_small_network()
    lls_buffer = make_sample_lls_csv(net)

    print("Cargando rayos reales desde el CSV LLS de ejemplo (4 filas: "
          "2 dentro del corredor, 1 lejos, 1 invalida)...")
    lig_stat = ls.Lightning_stat(net, M="Database", database_buffer=lls_buffer)

    print(f"\nRayos reales dentro del corredor: {len(lig_stat.Lightnings)}")
    for L in lig_stat.Lightnings:
        print(
            f"  case={L.case}  Ih1={L.Ih1:.1f} A  "
            f"X0={L.X_location:.1f} m  Y0={L.Y_location:.1f} m  "
            f"tf1={L.tf1:.3e} s  direct_strike={L.direc_strike}"
        )
    print(f"\nArea del corredor: {lig_stat.Area:.1f} m2")
