import os
import math
import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
from PIL import Image
from io import BytesIO
import requests
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# === CARGAR VARIABLES DE ENTORNO ===
load_dotenv()
api_key = os.getenv("HERE_API_KEY")
if not api_key:
    raise ValueError("HERE_API_KEY no encontrado en .env")

# === FUNCIONES GEOGRÁFICAS ===
def calculate_angle(line: LineString):
    coords = list(line.coords)
    if len(coords) < 2:
        return None
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180

def lat_lon_to_tile(lat, lon, zoom):
    lat = min(max(lat, -85.0511), 85.0511)
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

def tile_coords_to_lat_lon(x, y, zoom):
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg

def get_tile_bounds(x, y, zoom):
    lat1, lon1 = tile_coords_to_lat_lon(x, y, zoom)
    lat2, lon2 = tile_coords_to_lat_lon(x + 1, y + 1, zoom)
    return lat1, lon1, lat2, lon2

def fetch_satellite_tile(lat, lon, zoom, tile_format):
    x, y = lat_lon_to_tile(lat, lon, zoom)
    url = f'https://maps.hereapi.com/v3/base/mc/{zoom}/{x}/{y}/{tile_format}?apiKey={api_key}&style=satellite.day&size=512'
    response = requests.get(url)
    if response.status_code != 200:
        return None, None
    image = Image.open(BytesIO(response.content))
    return image, get_tile_bounds(x, y, zoom)

def latlon_to_pixel(lat, lon, bounds):
    lat1, lon1, lat2, lon2 = bounds
    x_rel = (lon - lon1) / (lon2 - lon1)
    y_rel = (lat1 - lat) / (lat1 - lat2)
    return int(x_rel * 512), int(y_rel * 512)

# El resto del procesamiento unificado lo incluiré en el archivo .py

# === CARGA DE DATOS ===
csv_files = sorted(glob.glob("POIs/*.csv"))[:1]
df_pois = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)

geojson_calles = sorted(glob.glob("STREETS_NAMING_ADDRESSING/*.geojson"))[:1]
gdf_calles = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in geojson_calles], ignore_index=True))

geojson_nav = sorted(glob.glob("STREETS_NAV/*.geojson"))[:1]
gdf_nav = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in geojson_nav], ignore_index=True))

# === MULTIDIGIT MERGE ===
if 'link_id' in gdf_nav.columns and 'MULTIDIGIT' in gdf_nav.columns:
    gdf_calles = gdf_calles.merge(gdf_nav[['link_id', 'MULTIDIGIT']], on='link_id', how='left')

# === MERGE POIs ===
df_merge = df_pois.merge(
    gdf_calles[['link_id', 'geometry', 'MULTIDIGIT']],
    left_on='LINK_ID',
    right_on='link_id',
    how='left'
)

# === CENTROIDES ===
gdf_pois = gpd.GeoDataFrame(df_merge, geometry='geometry', crs=gdf_calles.crs)
gdf_pois = gdf_pois.to_crs(epsg=3857)
gdf_pois['geometry'] = gdf_pois['geometry'].centroid
gdf_pois = gdf_pois.to_crs(epsg=4326)

# === EVALUACIÓN: NO POI IN REALITY ===
gdf_pois['EVAL_MULTIDIGIT'] = gdf_pois['MULTIDIGIT'].apply(lambda x: 'delete' if str(x).strip().upper() in ['Y', 'YES'] else 'ok')

# === EVALUACIÓN: INCORRECT SIDE ===
gdf_pois['PERCFRREF_NORM'] = gdf_pois['PERCFRREF'] / 1000.0

def lado_declaro(pct):
    if pd.isna(pct):
        return 'unknown'
    elif pct < 0.3:
        return 'L'
    elif pct > 0.7:
        return 'R'
    else:
        return 'center'

gdf_pois['DECLARED_SIDE'] = gdf_pois['PERCFRREF_NORM'].apply(lado_declaro)
gdf_pois = gdf_pois.merge(gdf_calles[['link_id', 'geometry']], on='link_id', how='left', suffixes=('', '_right'))

def calcular_lado_geometrico(poi_point, line):
    if not isinstance(line, LineString) or not isinstance(poi_point, Point):
        return 'unknown'
    coords = list(line.coords)
    if len(coords) < 2:
        return 'unknown'
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    dx, dy = x2 - x1, y2 - y1
    dxp, dyp = poi_point.x - x1, poi_point.y - y1
    cross = dx * dyp - dy * dxp
    if cross > 0:
        return 'L'
    elif cross < 0:
        return 'R'
    else:
        return 'center'

gdf_pois['GEOMETRIC_SIDE'] = gdf_pois.apply(lambda row: calcular_lado_geometrico(row.geometry, row.geometry_right), axis=1)

def evaluar_discrepancia(declared, geo):
    if declared in ['L', 'R'] and geo in ['L', 'R'] and declared != geo:
        return 'relink'
    else:
        return 'ok'

gdf_pois['EVAL_SIDE'] = gdf_pois.apply(lambda row: evaluar_discrepancia(row['DECLARED_SIDE'], row['GEOMETRIC_SIDE']), axis=1)

# === GUARDAR RESULTADOS ===
gdf_pois[['POI_ID', 'POI_NAME', 'EVAL_MULTIDIGIT', 'EVAL_SIDE']].to_csv("resultado_pois.csv", index=False)

# === EXCEPCIONES LEGÍTIMAS Y CORRECCIÓN MULTIDIGIT ===
gdf_nav = gdf_nav[gdf_nav.geometry.type == "LineString"]
gdf_nav = gdf_nav.to_crs(epsg=3857)
gdf_nav["EXCEPTION_LEGIT"] = "NO"
gdf_nav["original_MULTIDIGIT"] = gdf_nav["MULTIDIGIT"].values

for idx, segment in gdf_nav.iterrows():
    geom = segment.geometry
    link_id = segment.get("link_id")
    if geom.length < 5:
        continue
    angle_segment = calculate_angle(geom)
    if angle_segment is None:
        continue
    buffer = geom.buffer(25)
    nearby = gdf_nav[
        (gdf_nav.geometry.intersects(buffer)) &
        (gdf_nav["link_id"] != link_id) &
        (gdf_nav.index != idx)
    ]

    valid_neighbors = []
    for _, neighbor in nearby.iterrows():
        angle_neighbor = calculate_angle(neighbor.geometry)
        if angle_neighbor is None:
            continue
        angle_diff = abs(angle_segment - angle_neighbor)
        if angle_diff > 90:
            angle_diff = 180 - angle_diff
        overlap = geom.intersection(neighbor.geometry)
        overlap_ratio = overlap.length / geom.length if geom.length > 0 else 0
        centroid_distance = geom.centroid.distance(neighbor.geometry.centroid)
        if angle_diff <= 20 and (overlap_ratio >= 0.05 or centroid_distance < 25):
            valid_neighbors.append(neighbor)

    inferred = "YES" if len(valid_neighbors) >= 1 else "NO"
    gdf_nav.at[idx, "MULTIDIGIT"] = inferred
    if str(segment.get("MULTIDIGIT")).strip().upper() in ["YES", "Y"] and len(valid_neighbors) >= 1 and geom.length > 10:
        gdf_nav.at[idx, "EXCEPTION_LEGIT"] = "YES"

# === GUARDAR ARCHIVO FINAL CON EXCEPCIONES ===
gdf_nav.to_file("STREETS_NAV/FINAL_SEGMENTOS.geojson", driver="GeoJSON")
print("Validación completa. Archivos generados:")
print("- resultado_pois.csv")
print("- STREETS_NAV/FINAL_SEGMENTOS.geojson")


# === FILTRAR POIs que fallaron TODAS las validaciones ===
gdf_invalid_all = gdf_pois[
    (gdf_pois['EVAL_MULTIDIGIT'] == 'delete') & 
    (gdf_pois['EVAL_SIDE'] == 'relink')
]

# Guardar solo los completamente inválidos
gdf_invalid_all[['POI_ID', 'POI_NAME', 'EVAL_MULTIDIGIT', 'EVAL_SIDE']].to_csv("pois_invalidos_completos.csv", index=False)

print(f"POIs que fallaron todas las validaciones: {len(gdf_invalid_all)}")
print("Archivo generado: pois_invalidos_completos.csv")

