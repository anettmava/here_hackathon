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
    """
    Calcula el ángulo (en grados, 0-180) de un segmento LineString respecto al eje X.
    Si el segmento tiene menos de dos puntos, devuelve None.
    """
    coords = list(line.coords)
    if len(coords) < 2:
        return None
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180

def lat_lon_to_tile(lat, lon, zoom):
    """
    Convierte una latitud y longitud a coordenadas de tile (x, y) para un nivel de zoom dado.
    """
    lat = min(max(lat, -85.0511), 85.0511)
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

def tile_coords_to_lat_lon(x, y, zoom):
    """
    Convierte coordenadas de tile (x, y) y nivel de zoom a latitud y longitud.
    """
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg

def get_tile_bounds(x, y, zoom):
    """
    Devuelve los límites geográficos (lat1, lon1, lat2, lon2) de un tile.
    """
    lat1, lon1 = tile_coords_to_lat_lon(x, y, zoom)
    lat2, lon2 = tile_coords_to_lat_lon(x + 1, y + 1, zoom)
    return lat1, lon1, lat2, lon2

def fetch_satellite_tile(lat, lon, zoom, tile_format):
    """
    Descarga una imagen satelital de HERE para una latitud, longitud y zoom dados.
    Devuelve la imagen y los límites geográficos del tile.
    """
    x, y = lat_lon_to_tile(lat, lon, zoom)
    url = f'https://maps.hereapi.com/v3/base/mc/{zoom}/{x}/{y}/{tile_format}?apiKey={api_key}&style=satellite.day&size=512'
    response = requests.get(url)
    if response.status_code != 200:
        return None, None
    image = Image.open(BytesIO(response.content))
    return image, get_tile_bounds(x, y, zoom)

def latlon_to_pixel(lat, lon, bounds):
    """
    Convierte una latitud y longitud a coordenadas de píxel (x, y) dentro de una imagen de 512x512 píxeles,
    usando los límites geográficos del tile.
    """
    lat1, lon1, lat2, lon2 = bounds
    x_rel = (lon - lon1) / (lon2 - lon1)
    y_rel = (lat1 - lat) / (lat1 - lat2)
    return int(x_rel * 512), int(y_rel * 512)

# === CARGA DE DATOS ===
csv_files = sorted(glob.glob("POIs/*.csv"))
df_pois = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)

geojson_calles = sorted(glob.glob("STREETS_NAMING_ADDRESSING/*.geojson"))
gdf_calles = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in geojson_calles], ignore_index=True))

geojson_nav = sorted(glob.glob("STREETS_NAV/*.geojson"))
gdf_nav = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in geojson_nav], ignore_index=True))

if 'link_id' in gdf_nav.columns and 'MULTIDIGIT' in gdf_nav.columns:
    gdf_calles = gdf_calles.merge(gdf_nav[['link_id', 'MULTIDIGIT']], on='link_id', how='left')

# Segmentos proyectados para longitud
gdf_calles_proj = gdf_calles.to_crs(epsg=3857)
gdf_calles_proj["segment_length"] = gdf_calles_proj.geometry.length

# Merge POIs con geometría y longitud
df_merge = df_pois.merge(
    gdf_calles_proj[['link_id', 'geometry', 'segment_length', 'MULTIDIGIT']],
    left_on='LINK_ID',
    right_on='link_id',
    how='left'
)

# GeoDataFrame de POIs
gdf_pois = gpd.GeoDataFrame(df_merge, geometry='geometry', crs=gdf_calles_proj.crs)
gdf_pois = gdf_pois.to_crs(epsg=3857)
gdf_pois['geometry'] = gdf_pois['geometry'].centroid

# Evaluación MULTIDIGIT más estricta

def evaluate_multidigit(row):
    """
    Marca como 'delete' los POIs en segmentos largos (>=50m) y MULTIDIGIT=Y/YES.
    """
    if row['segment_length'] >= 50 and str(row['MULTIDIGIT']).strip().upper() in ['Y', 'YES']:
        return 'delete'
    return 'ok'

gdf_pois['EVAL_MULTIDIGIT'] = gdf_pois.apply(evaluate_multidigit, axis=1)

# Declaración de lado
gdf_pois['PERCFRREF_NORM'] = gdf_pois['PERCFRREF'] / 1000.0

def lado_declaro(pct):
    """
    Determina el lado declarado del POI según el valor normalizado de PERCFRREF.
    """
    if pd.isna(pct): return 'unknown'
    if pct < 0.01: return 'L'
    if pct > 0.99: return 'R'
    return 'center'

gdf_pois['DECLARED_SIDE'] = gdf_pois['PERCFRREF_NORM'].apply(lado_declaro)

# Geometría proyectada de nuevo
gdf_calles = gdf_calles.to_crs(epsg=3857)
gdf_pois = gdf_pois.merge(gdf_calles[['link_id', 'geometry']], on='link_id', how='left', suffixes=('', '_right'))

# Cálculo de lado geométrico
def calcular_lado_geometrico(poi_point, line):
    """
    Determina el lado geométrico del POI respecto a la calle usando el producto cruzado.
    """
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
    return 'L' if cross > 0 else 'R' if cross < 0 else 'center'

gdf_pois['GEOMETRIC_SIDE'] = gdf_pois.apply(lambda row: calcular_lado_geometrico(row.geometry, row.geometry_right), axis=1)

def evaluar_discrepancia(declared, geo):
    """
    Marca como 'relink' si el lado declarado y el geométrico son diferentes (y ambos válidos).
    """
    if declared in ['center', 'unknown'] or geo in ['center', 'unknown']:
        return 'ok'
    elif declared != geo:
        return 'relink'
    else:
        return 'ok'

gdf_pois['EVAL_SIDE'] = gdf_pois.apply(lambda row: evaluar_discrepancia(row['DECLARED_SIDE'], row['GEOMETRIC_SIDE']), axis=1)

# Guardar
gdf_pois[['POI_ID', 'POI_NAME', 'EVAL_MULTIDIGIT', 'EVAL_SIDE']].to_csv("resultado_pois.csv", index=False)

# Filtrar inválidos completos
gdf_invalid_all = gdf_pois[
    (gdf_pois['EVAL_MULTIDIGIT'] == 'delete') & 
    (gdf_pois['EVAL_SIDE'] == 'relink')
]
gdf_invalid_all[['POI_ID', 'POI_NAME', 'EVAL_MULTIDIGIT', 'EVAL_SIDE']].to_csv("pois_invalidos_completos.csv", index=False)

print(f"POIs que fallaron todas las validaciones: {len(gdf_invalid_all)}")
print("Archivo generado: pois_invalidos_completos.csv")
