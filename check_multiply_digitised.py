import os
import math
import requests
import geopandas as gpd
from shapely.geometry import Point
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# === CONFIGURACIÓN ===
load_dotenv()
api_key = os.getenv("HERE_API_KEY")
if not api_key:
    raise ValueError("❌ HERE_API_KEY no encontrado en el archivo .env")

# === COORDENADAS A VALIDAR ===
latitude = 19.33573
longitude = -99.57503
user_point = Point(longitude, latitude)

# === FUNCIONES PARA IMAGEN SATELITAL ===
def lat_lon_to_tile(lat, lon, zoom):
    lat = min(max(lat, -85.0511), 85.0511)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
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

def fetch_satellite_tile(lat, lon, zoom, tile_format, api_key):
    x, y = lat_lon_to_tile(lat, lon, zoom)
    url = f'https://maps.hereapi.com/v3/base/mc/{zoom}/{x}/{y}/{tile_format}?apiKey={api_key}&style=satellite.day&size=512'
    response = requests.get(url)
    if response.status_code != 200:
        print("❌ Falló la descarga de imagen:", response.status_code)
        return None, None
    image = Image.open(BytesIO(response.content))
    return image, get_tile_bounds(x, y, zoom)

def latlon_to_pixel(lat, lon, bounds):
    lat1, lon1, lat2, lon2 = bounds
    x_rel = (lon - lon1) / (lon2 - lon1)
    y_rel = (lat1 - lat) / (lat1 - lat2)
    return int(x_rel * 512), int(y_rel * 512)

# === CARGAR SEGMENTOS NAV ===
nav_path = "STREETS_NAV/SREETS_NAV_4815075.geojson"
if not os.path.exists(nav_path):
    raise FileNotFoundError("❌ Archivo NAV no encontrado.")

nav_gdf = gpd.read_file(nav_path)
nav_gdf = nav_gdf[nav_gdf.geometry.type == "LineString"]
if nav_gdf.empty:
    raise ValueError("❌ El archivo no contiene segmentos tipo LineString.")

# Transformar a CRS proyectado para medir distancias
nav_proj = nav_gdf.to_crs(epsg=3857)
user_proj = gpd.GeoSeries([user_point], crs="EPSG:4326").to_crs(epsg=3857).iloc[0]

# Calcular distancia del punto a todos los segmentos
nav_proj["dist"] = nav_proj.geometry.distance(user_proj)
closest_idx = nav_proj["dist"].idxmin()
closest_seg = nav_gdf.loc[closest_idx]

print(f"\n📍 Segmento más cercano (index {closest_idx})")
print(f"link_id: {closest_seg['link_id']}")
print(f"MULTIDIGIT actual: {closest_seg['MULTIDIGIT']}")

# === MOSTRAR IMAGEN SATELITAL ===
zoom = 18
image, bounds = fetch_satellite_tile(latitude, longitude, zoom, 'png', api_key)

if image:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(image)
    px, py = latlon_to_pixel(latitude, longitude, bounds)
    ax.plot(px, py, 'ro', markersize=10)
    ax.set_title(f"Segmento más cercano al punto ({latitude:.5f}, {longitude:.5f})")
    ax.axis("off")
    plt.tight_layout()
    plt.show()
    input("Presiona Enter para continuar...")

# === PREGUNTA MANUAL DE VALIDACIÓN (FORZADA) ===
while True:
    respuesta = input("¿Este segmento está mal etiquetado como MULTIDIGIT? (s/n): ").strip().lower()
    if respuesta in ["s", "n"]:
        break
    print("❌ Entrada no válida. Escribe 's' o 'n'.")

# === COMPARACIÓN, ACTUALIZACIÓN Y GUARDADO ===
original = str(closest_seg["MULTIDIGIT"]).strip().upper()
nuevo_valor = None

if respuesta == "s":
    if original in ["YES", "Y"]:
        nuevo_valor = "N"
        print("✏️ MULTIDIGIT actualizado: YES → NO")
    else:
        print("✅ MULTIDIGIT ya estaba en NO. No es necesario cambiarlo.")
elif respuesta == "n":
    if original in ["YES", "Y"]:
        print("✅ MULTIDIGIT ya estaba en YES.")
    else:
        nuevo_valor = "Y"
        print("✏️ MULTIDIGIT actualizado: NO → YES")

# Si hay actualización, aplicar y guardar copia
if nuevo_valor:
    nav_gdf.loc[closest_idx, "MULTIDIGIT"] = nuevo_valor
    output_path = "STREETS_NAV/ACTUALIZADO_SREETS_NAV_4815075.geojson"
    nav_gdf.to_file(output_path, driver="GeoJSON")
    print(f"💾 Archivo actualizado guardado en: {output_path}")
