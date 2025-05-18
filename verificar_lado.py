from shapely.geometry import LineString, Point, MultiLineString
import geopandas as gpd

def determine_side(line, point, dir_travel):
    """
    Determina de qué lado del segmento de calle está el punto (POI),
    ignorando MultiLineStrings.
    """
    if line is None or point is None:
        return 'C'

    if isinstance(line, MultiLineString):
        return 'C'

    if not isinstance(line, LineString) or len(line.coords) < 2:
        return 'C'
    
    coords = list(line.coords)

    if dir_travel == 'T':
        coords = coords[::-1]
    elif dir_travel in ('N', ' '):
        return 'C'

    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    dx = x2 - x1
    dy = y2 - y1
    px = point.x - x1
    py = point.y - y1
    cross = dx * py - dy * px

    if cross > 0:
        return 'L'
    elif cross < 0:
        return 'R'
    else:
        return 'C'

# === CARGA DE DATOS ===
poipath = "output_POIs.geojson"
navpath = "C:\\Users\\mont_\\OneDrive\\Desktop\\Here_hack\\data\\STREETS_NAV\\SREETS_NAV_4815075.geojson"

# Cargar POIs y STREETS_NAV
pois = gpd.read_file(poipath)
streets_nav = gpd.read_file(navpath)

# Asegurar que los IDs sean string
pois["LINK_ID"] = pois["LINK_ID"].astype(str)
streets_nav["link_id"] = streets_nav["link_id"].astype(str)

# Hacer el merge
joined = pois.merge(
    streets_nav[["link_id", "DIR_TRAVEL", "geometry"]],
    left_on="LINK_ID",
    right_on="link_id",
    how="left",
    suffixes=("_poi", "_street")
)

# Calcular lado correcto
correct_sides = []
for _, row in joined.iterrows():
    line = row["geometry_street"]  # geometría de calle
    point = row["geometry_poi"]    # geometría del POI
    dir_travel = row["DIR_TRAVEL"]
    correct = determine_side(line, point, dir_travel)
    correct_sides.append(correct)

joined["correct_POI_ST_SD"] = correct_sides
joined["needs_update"] = joined["POI_ST_SD"] != joined["correct_POI_ST_SD"]

# Filtrar y copiar solo los POIs que necesitan corrección
to_update = joined[joined["needs_update"]].copy()

# Usar solo la geometría del POI
to_update = to_update.set_geometry("geometry_poi")

# (Opcional) Convertir geometría de calle a texto WKT
to_update["street_geom_wkt"] = to_update["geometry_street"].to_wkt()

# Eliminar la geometría adicional antes de exportar
to_update = to_update.drop(columns=["geometry_street"])

# Exportar a GeoJSON
to_update.to_file("POIs_lado_incorrecto.geojson", driver="GeoJSON")

print(f"Se encontraron {len(to_update)} POIs con lado incorrecto.")
print("Archivo exportado: POIs_lado_incorrecto.geojson")
