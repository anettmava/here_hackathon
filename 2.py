import pandas as pd
import geopandas as gpd
import glob
from shapely.geometry import LineString, Point
import math

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
print("✅ Evaluación de lado completada y guardada en 'POIs_side_evaluation.csv'")