import os
import math
import requests
import geopandas as gpd
from shapely.geometry import LineString
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import glob

# === CARGAR VARIABLES DE ENTORNO ===
load_dotenv()
api_key = os.getenv("HERE_API_KEY")
if not api_key:
    raise ValueError("❌ HERE_API_KEY no encontrado en .env")

# === CREAR CARPETA PARA IMÁGENES CORREGIDAS ===
os.makedirs("imagenes_segmentos", exist_ok=True)

# === FUNCIONES ===
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

def fetch_satellite_tile(lat, lon, zoom, tile_format, api_key):
    x, y = lat_lon_to_tile(lat, lon, zoom)
    url = f'https://maps.hereapi.com/v3/base/mc/{zoom}/{x}/{y}/{tile_format}?apiKey={api_key}&style=satellite.day&size=512'
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Falló la descarga de imagen: {response.status_code}")
        return None, None
    image = Image.open(BytesIO(response.content))
    return image, get_tile_bounds(x, y, zoom)

def latlon_to_pixel(lat, lon, bounds):
    lat1, lon1, lat2, lon2 = bounds
    x_rel = (lon - lon1) / (lon2 - lon1)
    y_rel = (lat1 - lat) / (lat1 - lat2)
    return int(x_rel * 512), int(y_rel * 512)

def calculate_angle(line: LineString):
    coords = list(line.coords)
    if len(coords) < 2:
        return None
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180

# === ARCHIVO ===
geojson_files = sorted(glob.glob("STREETS_NAV/*.geojson"))
if not geojson_files:
    raise FileNotFoundError("❌ No se encontró ningún archivo GeoJSON en STREETS_NAV/")
nav_path = geojson_files[0]
print(f"📄 Procesando archivo: {os.path.basename(nav_path)}")

nav_gdf = gpd.read_file(nav_path)
nav_gdf = nav_gdf[nav_gdf.geometry.type == "LineString"]
if nav_gdf.empty:
    raise ValueError("❌ El archivo no contiene segmentos tipo LineString.")

nav_gdf_proj = nav_gdf.to_crs(epsg=3857)
nav_gdf_proj["original_MULTIDIGIT"] = nav_gdf["MULTIDIGIT"].values

updated_segments = []
imagenes_guardadas = 0  # contador para imágenes
zoom = 18

for idx, segment in nav_gdf_proj.iterrows():
    geom = segment.geometry
    link_id = segment.get("link_id")

    if geom.length < 5:
        continue

    angle_segment = calculate_angle(geom)
    if angle_segment is None:
        continue

    buffer = geom.buffer(25)
    nearby = nav_gdf_proj[
        (nav_gdf_proj.geometry.intersects(buffer)) &
        (nav_gdf_proj["link_id"] != link_id) &
        (nav_gdf_proj.index != idx)
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

        print(f"→ Segmento {idx}: angle diff={angle_diff:.1f}°, overlap={overlap_ratio:.2f}, dist={centroid_distance:.1f}")

        if angle_diff <= 20 and (overlap_ratio >= 0.05 or centroid_distance < 25):
            valid_neighbors.append(neighbor)

    inferred = "YES" if len(valid_neighbors) >= 1 else "NO"

    original = str(segment["original_MULTIDIGIT"]).strip().upper()
    if original not in ["YES", "Y", "NO", "N"]:
        original = "NO"

    was_correct = (
        (inferred == "YES" and original in ["YES", "Y"]) or
        (inferred == "NO" and original in ["NO", "N"])
    )

    if not was_correct:
        nav_gdf.at[idx, "MULTIDIGIT"] = inferred
        updated_segments.append(idx)

        # Mostrar y guardar imagen solo si fue corregido y aún no se ha llegado al límite
        if imagenes_guardadas < 20:
            centroid = nav_gdf.at[idx, "geometry"].centroid
            lat, lon = centroid.y, centroid.x
            image, bounds = fetch_satellite_tile(lat, lon, zoom, 'png', api_key)
            if image:
                fig, ax = plt.subplots(figsize=(6, 6))
                ax.imshow(image)
                px, py = latlon_to_pixel(lat, lon, bounds)
                ax.plot(px, py, 'ro', markersize=10)
                ax.set_title(f"Segmento {idx} | MULTIDIGIT: {original} → {inferred} | Corregido")
                ax.axis("off")
                plt.tight_layout()
                plt.savefig(f"imagenes_segmentos/segmento_{idx}.png")
                plt.close()
                imagenes_guardadas += 1

                if imagenes_guardadas == 10:
                    print("🛑 Límite de 10 imágenes alcanzado. No se guardarán más.")

# === GUARDAR SI HAY CAMBIOS ===
if updated_segments:
    filename = os.path.basename(nav_path)
    output_path = os.path.join("STREETS_NAV", f"ACTUALIZADO_{filename}")
    nav_gdf.to_file(output_path, driver="GeoJSON")
    print(f"\n💾 Archivo actualizado guardado en: {output_path}")
    print(f"🔁 Segmentos corregidos: {len(updated_segments)}")
else:
    print("✅ No se detectaron cambios en MULTIDIGIT.")
