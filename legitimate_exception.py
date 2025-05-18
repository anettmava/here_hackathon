import os
import math
import glob
import geopandas as gpd
from shapely.geometry import LineString
import folium

def calculate_angle(line: LineString):
    coords = list(line.coords)
    if len(coords) < 2:
        return None
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180

archivos = sorted(glob.glob("STREETS_NAV/*.geojson"))
if not archivos:
    raise FileNotFoundError("No se encontró ningún archivo en STREETS_NAV/")

archivo = archivos[0]
print(f"Analizando archivo: {os.path.basename(archivo)}")

gdf = gpd.read_file(archivo)
gdf = gdf[gdf.geometry.type == "LineString"]
gdf = gdf.to_crs(epsg=3857)
gdf["EXCEPTION_LEGIT"] = "NO"

for idx, segment in gdf.iterrows():
    geom = segment.geometry
    link_id = segment.get("link_id")

    if geom.length < 5:
        continue

    angle_segment = calculate_angle(geom)
    if angle_segment is None:
        continue

    buffer = geom.buffer(25)
    nearby = gdf[
        (gdf.geometry.intersects(buffer)) &
        (gdf["link_id"] != link_id) &
        (gdf.index != idx)
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

    multidigit = str(segment.get("MULTIDIGIT", "NO")).strip().upper()
    if multidigit in ["YES", "Y"] and len(valid_neighbors) >= 1 and geom.length > 10:
        gdf.at[idx, "EXCEPTION_LEGIT"] = "YES"

output_path = os.path.join("STREETS_NAV", f"EXCEPCIONES_{os.path.basename(archivo)}")
gdf.to_file(output_path, driver="GeoJSON")

print(f"\nArchivo con excepciones guardado como: {output_path}")
print("Excepciones legítimas detectadas:", (gdf["EXCEPTION_LEGIT"] == "YES").sum())