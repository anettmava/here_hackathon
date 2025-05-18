import pandas as pd
import geopandas as gpd
import glob
from shapely.geometry import Point
import folium
import math
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
here_api_key = os.getenv("HERE_API_KEY")

# Funciones para tile y WKT con HERE
def lat_lon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    return x, y

def tile_coords_to_lat_lon(x, y, zoom):
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

def get_tile_bounds(x, y, zoom):
    lat1, lon1 = tile_coords_to_lat_lon(x, y, zoom)
    lat2, lon2 = tile_coords_to_lat_lon(x + 1, y, zoom)
    lat3, lon3 = tile_coords_to_lat_lon(x + 1, y + 1, zoom)
    lat4, lon4 = tile_coords_to_lat_lon(x, y + 1, zoom)
    return (lat1, lon1), (lat2, lon2), (lat3, lon3), (lat4, lon4)

def create_wkt_polygon(bounds):
    (lat1, lon1), (lat2, lon2), (lat3, lon3), (lat4, lon4) = bounds
    return f"POLYGON(({lon1} {lat1}, {lon2} {lat2}, {lon3} {lat3}, {lon4} {lat4}, {lon1} {lat1}))"

# 1. Cargar CSV de POIs
csv_files = sorted(glob.glob("POIs/*.csv"))[:1]
df_pois = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)

# 2. Cargar GEOJSON de calles
geojson_files = sorted(glob.glob("STREETS_NAMING_ADDRESSING/*.geojson"))[:1]
gdf_calles = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in geojson_files], ignore_index=True))

# 3. Cargar archivos de navegación para MULTIDIGIT
nav_files = sorted(glob.glob("STREETS_NAV/*.geojson"))[:3]
gdf_nav = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in nav_files], ignore_index=True))

# 4. Merge MULTIDIGIT con calles
if 'link_id' in gdf_nav.columns and 'MULTIDIGIT' in gdf_nav.columns:
    gdf_calles = gdf_calles.merge(gdf_nav[['link_id', 'MULTIDIGIT']], on='link_id', how='left')

# 5. Merge POIs con calles
df_merge = df_pois.merge(
    gdf_calles[['link_id', 'geometry', 'MULTIDIGIT']],
    left_on='LINK_ID',
    right_on='link_id',
    how='left'
)

# 6. Centroides y reproyección
gdf_pois = gpd.GeoDataFrame(df_merge, geometry='geometry', crs=gdf_calles.crs)
gdf_pois = gdf_pois.to_crs(epsg=3857)
gdf_pois['geometry'] = gdf_pois['geometry'].centroid
gdf_pois = gdf_pois.to_crs(epsg=4326)

# 7. Evaluación + Tile WKT
gdf_pois['EVALUATION'] = gdf_pois['MULTIDIGIT'].apply(lambda x: 'delete' if x == 'Y' else 'correct')

zoom_level = 18
gdf_pois['TILE_WKT'] = gdf_pois['geometry'].apply(
    lambda geom: create_wkt_polygon(get_tile_bounds(*lat_lon_to_tile(geom.y, geom.x, zoom_level), zoom_level))
)

# 8. Filtrar sospechosos
gdf_pois_sospechosos = gdf_pois[gdf_pois['EVALUATION'] == 'delete']
print(f"🔍 Total de POIs sospechosos (MULTIDIGIT = YES): {len(gdf_pois_sospechosos)}")

# 9. Visualización con HERE
centro = [gdf_pois.geometry.y.mean(), gdf_pois.geometry.x.mean()]

tiles_url = (
    f"https://1.base.maps.ls.hereapi.com/maptile/2.1/maptile/newest/normal.day/"
    f"{{z}}/{{x}}/{{y}}/256/png8?apiKey={here_api_key}&lg=spa"
)

m = folium.Map(location=centro, zoom_start=15, tiles=None)
folium.TileLayer(
    tiles=tiles_url,
    attr='HERE Maps',
    name='HERE',
    overlay=False,
    control=True
).add_to(m)

# 10. Marcadores
for _, row in gdf_pois.iterrows():
    lat = row.geometry.y
    lon = row.geometry.x
    popup_text = (
        f"{row.get('POI_NAME', 'POI')}<br>"
        f"Lat: {lat:.6f}<br>Lon: {lon:.6f}<br>"
        f"Status: <b>{row['EVALUATION']}</b><br>"
        f"<small>{row['TILE_WKT']}</small>"
    )
    color = 'red' if row['EVALUATION'] == 'delete' else 'green'
    folium.Marker(
        location=[lat, lon],
        popup=popup_text,
        icon=folium.Icon(color=color, icon='info-sign')
    ).add_to(m)

# 11. Guardar archivo CSV
gdf_pois[['POI_ID', 'POI_NAME', 'geometry', 'EVALUATION', 'TILE_WKT']].to_csv("POIs_Evaluados.csv", index=False)
print("✅ Archivo 'POIs_Evaluados.csv' generado.")

# 12. Guardar mapa
m.save("mapa_pois.html")
print("✅ Mapa generado con evaluación y tile WKT: 'mapa_pois.html'")
