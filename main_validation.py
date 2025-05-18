import os
import math
import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point
from dotenv import load_dotenv

# === CARGAR VARIABLES DE ENTORNO ===
load_dotenv()
api_key = os.getenv("HERE_API_KEY")
if not api_key:
    raise ValueError("HERE_API_KEY no encontrado en .env")

# === FUNCIONES ===
def calculate_angle(line: LineString):
    coords = list(line.coords)
    if len(coords) < 2:
        return None
    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180

# === CARGA DE DATOS ===
csv_files = sorted(glob.glob("POIs/*.csv"))[:1]
df_pois = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)

geojson_calles = sorted(glob.glob("STREETS_NAMING_ADDRESSING/*.geojson"))[:1]
gdf_calles = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in geojson_calles], ignore_index=True))

geojson_nav = sorted(glob.glob("STREETS_NAV/*.geojson"))[:1]
gdf_nav = gpd.GeoDataFrame(pd.concat([gpd.read_file(f) for f in geojson_nav], ignore_index=True))

# === AGREGAR MULTIDIGIT A gdf_calles DESDE gdf_nav ===
if 'link_id' in gdf_nav.columns and 'MULTIDIGIT' in gdf_nav.columns:
    gdf_nav['link_id'] = gdf_nav['link_id'].astype(str)
    gdf_calles['link_id'] = gdf_calles['link_id'].astype(str)
    gdf_calles = gdf_calles.merge(
        gdf_nav[['link_id', 'MULTIDIGIT']],
        on='link_id',
        how='left'
    )

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

# === EVALUACIÓN DE LADO ===
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
gdf_pois = gdf_pois[~gdf_pois['geometry_right'].isna()].copy()

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
    return 'ok'

gdf_pois['EVAL_SIDE'] = gdf_pois.apply(lambda row: evaluar_discrepancia(row['DECLARED_SIDE'], row['GEOMETRIC_SIDE']), axis=1)

# === EXCEPCIONES LEGÍTIMAS Y MULTIDIGIT ===
gdf_nav = gdf_nav[gdf_nav.geometry.type == "LineString"].to_crs(epsg=3857)
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

# === MERGE EXCEPTION_LEGIT ===
gdf_nav.to_file("STREETS_NAV/FINAL_SEGMENTOS.geojson", driver="GeoJSON")
gdf_nav_subset = gdf_nav[['link_id', 'EXCEPTION_LEGIT']].copy()
gdf_pois['link_id'] = gdf_pois['link_id'].astype(str)
gdf_nav_subset['link_id'] = gdf_nav_subset['link_id'].astype(str)
gdf_pois = gdf_pois.merge(gdf_nav_subset, on='link_id', how='left')

# === EVALUACIÓN FINAL MULTIDIGIT ===
def evaluar_multidigit(multidigit, excepcion):
    if str(multidigit).strip().upper() in ['Y', 'YES']:
        return 'ok' if excepcion == 'YES' else 'delete'
    return 'ok'

gdf_pois['EVAL_MULTIDIGIT'] = gdf_pois.apply(
    lambda row: evaluar_multidigit(row['MULTIDIGIT'], row['EXCEPTION_LEGIT']), axis=1
)

# === EXPORTAR RESULTADOS ===
gdf_pois[['POI_ID', 'POI_NAME', 'EVAL_MULTIDIGIT', 'EVAL_SIDE']].to_csv("resultado_pois.csv", index=False)
gdf_invalid_all = gdf_pois[
    (gdf_pois['EVAL_MULTIDIGIT'] == 'delete') & 
    (gdf_pois['EVAL_SIDE'] == 'relink')
]
gdf_invalid_all[['POI_ID', 'POI_NAME', 'EVAL_MULTIDIGIT', 'EVAL_SIDE']].to_csv("pois_invalidos_completos.csv", index=False)

print("✅ Validación completa.")
print(f"📄 POIs totales evaluados: {len(gdf_pois)}")
print(f"❌ POIs inválidos detectados: {len(gdf_invalid_all)}")
print("📝 Archivos generados:")
print("- resultado_pois.csv")
print("- pois_invalidos_completos.csv")
print("- STREETS_NAV/FINAL_SEGMENTOS.geojson")