import requests
import math
import geopandas as gpd
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os

# === CARGAR VARIABLES DE ENTORNO ===
load_dotenv()
api_key = os.getenv("HERE_API_KEY")

if not api_key:
    raise ValueError("❌ No se encontró HERE_API_KEY en el archivo .env")

# === FUNCIONES ===

def lat_lon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)

def tile_coords_to_lat_lon(x, y, zoom):
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

def get_tile_bounds(x, y, zoom):
    lat1, lon1 = tile_coords_to_lat_lon(x, y, zoom)
    lat2, lon2 = tile_coords_to_lat_lon(x + 1, y + 1, zoom)
    return lat1, lon1, lat2, lon2

def get_satellite_tile_with_overlay(lat, lon, zoom, tile_format, api_key):
    x, y = lat_lon_to_tile(lat, lon, zoom)
    url = f'https://maps.hereapi.com/v3/base/mc/{zoom}/{x}/{y}/{tile_format}?apiKey={api_key}&style=satellite.day&size=512'

    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to fetch tile:", response.status_code)
        return None

    image = Image.open(BytesIO(response.content))
    lat1, lon1, lat2, lon2 = get_tile_bounds(x, y, zoom)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(image)

    def latlon_to_pixel(lat, lon):
        x_rel = (lon - lon1) / (lon2 - lon1)
        y_rel = (lat1 - lat) / (lat1 - lat2)
        px = int(x_rel * 512)
        py = int(y_rel * 512)
        return px, py

    px, py = latlon_to_pixel(lat, lon)
    ax.plot(px, py, 'ro', markersize=10)
    ax.set_title(f'POI at ({lat:.5f}, {lon:.5f})')
    ax.axis('off')
    plt.tight_layout()
    plt.show()

    return True  # confirm image was shown

# === MAIN FLOW ===

# Leer POIs
gdf = gpd.read_file("output_POIs.geojson")
points = gdf[gdf.geometry.type == "Point"]

# Solo el primero por ahora
first = points.iloc[0]
latitude = first.geometry.y
longitude = first.geometry.x

# Mostrar imagen
zoom_level = 18
tile_format = 'png'

shown = get_satellite_tile_with_overlay(latitude, longitude, zoom_level, tile_format, api_key)

# Interacción con el usuario
if shown:
    user_input = input("¿Se observa un edificio o estructura en este punto? (s/n): ").strip().lower()
    if user_input == "n":
        print("Este POI se marcaría como 'para eliminación'.")
    elif user_input == "s":
        print("Este POI parece válido.")
    else:
        print("Entrada no reconocida.")
