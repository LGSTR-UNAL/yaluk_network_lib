from pyproj import Transformer as PyProjTransformer
import math
class CoordTransf:
    """
    Generic Lat/Lon → Projected coordinate transformer using EPSG codes.
    """

    def __init__(self, src_epsg: int = 4326, dst_epsg: int = 9377):
        """
        src_epsg : source CRS (default = WGS84 lat/lon)
        dst_epsg : destination CRS (e.g. SIRGAS / UTM zone)  #Defecto "Origen Nacional"
        """
        self.src_epsg = src_epsg
        self.dst_epsg = dst_epsg

        self._transformer = PyProjTransformer.from_crs(
            f"EPSG:{src_epsg}",
            f"EPSG:{dst_epsg}",
            always_xy=True  # lon, lat order
        )

    def to_projected(self, lat: float, lon: float) -> tuple[float, float]:
        """
        Convert lat/lon → x/y (meters)
        """
        x, y = self._transformer.transform(lon, lat)
        return x, y

    def to_geographic(self, x: float, y: float) -> tuple[float, float]:
        """
        Convert x/y → lat/lon
        """
        lon, lat = self._transformer.transform(x, y, direction="INVERSE")
        return lat, lon
class PointLatLng:
    Lat: float = 0.0
    Lng: float = 0.0
    def __str__(self): return f"({self.Lat},{self.Lng})"
    def equals(self, other): return isinstance(other, PointLatLng) and math.isclose(self.Lat, other.Lat) and math.isclose(self.Lng, other.Lng)
    def __init__(self, lat: float = 0.0, lng: float = 0.0):
        self.Lat = lat
        self.Lng = lng
class PointXY:
    X: float = 0.0
    Y: float = 0.0
    def __str__(self): return f"({self.X},{self.Y})"
    def equals(self, other): return isinstance(other, PointXY) and math.isclose(self.X, other.X) and math.isclose(self.Y, other.Y)
    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.X = x
        self.Y = y
