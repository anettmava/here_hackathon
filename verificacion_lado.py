import pandas as pd
import geopandas as gpd
import glob
from shapely.geometry import LineString, Point
import os
import requests
from PIL import Image
from io import BytesIO
import math
from dotenv import load_dotenv
import matplotlib.pyplot as plt

# Cargar POIs
csv_files = sorted(glob.glob("POIs/*.csv"))[:1]
df_pois = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)

# Cargar calles
geojson_files = sorted(glob.glob("STREETS_NAMING_ADDRESSING/*.geojson"))[:1]
gdf_calles = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in geojson_files], ignore_index=True))

# Merge POIs con geometría de calles
df_merge = df_pois.merge(
    gdf_calles[['link_id', 'geometry']],
    left_on='LINK_ID',
    right_on='link_id',
    how='left'
)

# Convertimos a GeoDataFrame
gdf_pois = gpd.GeoDataFrame(df_merge, geometry='geometry', crs=gdf_calles.crs)
gdf_pois = gdf_pois.to_crs(epsg=3857)
gdf_pois['geometry'] = gdf_pois['geometry'].centroid
gdf_pois = gdf_pois.to_crs(epsg=4326)

# Normalizamos PERCFRREF y declaramos lado
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

# Recuperamos geometría original de calle para cada POI
gdf_pois = gdf_pois.merge(gdf_calles[['link_id', 'geometry']], on='link_id', how='left', suffixes=('', '_right'))

# Funcíón para determinar lado geométrico
def calcular_lado_geometrico(poi_point, line):
    if not isinstance(line, LineString) or not isinstance(poi_point, Point):
        return 'unknown'

    coords = list(line.coords)
    if len(coords) < 2:
        return 'unknown'

    # Vector de calle (inicio → fin)
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    dx, dy = x2 - x1, y2 - y1

    # Vector de calle → POI
    dxp, dyp = poi_point.x - x1, poi_point.y - y1

    # Producto cruzado
    cross = dx * dyp - dy * dxp

    if cross > 0:
        return 'L'
    elif cross < 0:
        return 'R'
    else:
        return 'center'

# Aplicar a cada fila
gdf_pois['GEOMETRIC_SIDE'] = gdf_pois.apply(lambda row: calcular_lado_geometrico(row.geometry, row.geometry_right), axis=1)

# Clasificar como relink si el lado declarado no coincide con el geométrico
def evaluar_discrepancia(declared, geo):
    if declared in ['L', 'R'] and geo in ['L', 'R'] and declared != geo:
        return 'relink'
    else:
        return 'ok'

gdf_pois['LOCATION_STATUS'] = gdf_pois.apply(lambda row: evaluar_discrepancia(row['DECLARED_SIDE'], row['GEOMETRIC_SIDE']), axis=1)

# Exportar resultados finales
gdf_pois[['POI_ID', 'DECLARED_SIDE', 'GEOMETRIC_SIDE', 'LOCATION_STATUS']].to_csv("POIs_side_evaluation.csv", index=False)
print("Evaluación de lado completada y guardada en 'POIs_side_evaluation.csv'")

relink_poi = gdf_pois[gdf_pois['LOCATION_STATUS'] == 'relink'].iloc[0]
lat = relink_poi.geometry.y
lon = relink_poi.geometry.x

# Construir la URL de imagen satelital
load_dotenv()
api_key = os.getenv("HERE_API_KEY")
url = f"https://image.maps.ls.hereapi.com/mia/1.6/mapview?apiKey={api_key}&c={lat},{lon}&z=19&w=600&h=600&t=satellite.day"

# Descargar y mostrar imagen
response = requests.get(url)
if response.status_code == 200:
    image = Image.open(BytesIO(response.content))
    image.show() 
    image.save("primer_poi_relink.jpg")
    print(f"Imagen satelital del POI {relink_poi['POI_ID']} guardada como 'primer_poi_relink.jpg'")

def lat_lon_to_tile(lat, lon, zoom):
    """
    Convierte una latitud y longitud a coordenadas de tile (x, y) para un nivel de zoom dado.
    Esto permite identificar en qué tile se encuentra un punto.
    """
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

def tile_coords_to_bounds(x, y, zoom):
    """
    Calcula los límites geográficos (latitud y longitud) de un tile dado por sus coordenadas (x, y) y nivel de zoom.
    Devuelve (lat1, lon1, lat2, lon2) donde (lat1, lon1) es la esquina superior izquierda y (lat2, lon2) la inferior derecha.
    """
    n = 2.0 ** zoom
    lon1 = x / n * 360.0 - 180.0
    lon2 = (x + 1) / n * 360.0 - 180.0
    lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat2 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return lat1, lon1, lat2, lon2

def lat_lon_to_pixel(lat, lon, bounds, tile_size=512):
    """
    Convierte una latitud y longitud a coordenadas de píxel (x, y) dentro de un tile de tamaño tile_size,
    usando los límites geográficos del tile.
    """
    lat1, lon1, lat2, lon2 = bounds
    x = int(((lon - lon1) / (lon2 - lon1)) * tile_size)
    y = int(((lat1 - lat) / (lat1 - lat2)) * tile_size)
    return x, y

# === Obtener primer POI con relink ===
relink_pois = gdf_pois[gdf_pois['LOCATION_STATUS'] == 'relink']
"""
Esta sección busca el primer POI cuya ubicación declarada (lado de la calle) no coincide con el lado geométrico calculado,
es decir, aquellos marcados como 'relink'. Luego descarga el tile satelital correspondiente usando la API de HERE,
calcula la posición del POI dentro de la imagen y genera una visualización donde el POI se marca con un punto rojo.
Esto permite revisar visualmente los casos donde hay discrepancia entre el lado declarado y el lado real según la geometría.
"""
if not relink_pois.empty:
    first = relink_pois.iloc[0]
    lat = first.geometry.y
    lon = first.geometry.x

    zoom = 18
    tile_size = 512
    tile_format = 'png'

    # HERE API (Tiles)
    x, y = lat_lon_to_tile(lat, lon, zoom)
    tile_url = f"https://maps.hereapi.com/v3/base/mc/{zoom}/{x}/{y}/{tile_format}?apiKey={api_key}&style=satellite.day&size={tile_size}"

    response = requests.get(tile_url)
    if response.status_code == 200:
        img = Image.open(BytesIO(response.content))
        bounds = tile_coords_to_bounds(x, y, zoom)
        px, py = lat_lon_to_pixel(lat, lon, bounds, tile_size)

        # Mostrar con matplotlib y punto rojo
        plt.imshow(img)
        plt.plot(px, py, 'ro', markersize=8)
        plt.title(f"POI_ID: {first['POI_ID']} - relink")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig("primer_poi_relink_marcado.png")
        plt.show()

        print("Imagen satelital descargada y punto marcado correctamente.")
    else:
        print("Error al descargar tile:", response.status_code)
else:
    print("No hay POIs con LOCATION_STATUS = 'relink'")