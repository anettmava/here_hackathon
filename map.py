import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import os

# --- 1. Cargar POIs CSV ---
poi_path = "/Users/danieledenwynter/Desktop/HERE-Hackathon/POIs/POI_4815075_CLEAN.csv"  # reemplaza con el nombre real
df_pois = pd.read_csv(poi_path, dtype={"LINK_ID": str})  # forzamos LINK_ID como string

# --- 2. Cargar archivo STREETS_NAMING_ADDRESSING ---
naming_path = "/Users/danieledenwynter/Desktop/HERE-Hackathon/STREETS_NAMING_ADDRESSING/SREETS_NAMING_ADDRESSING_4815075.geojson"
gdf_streets = gpd.read_file(naming_path)
gdf_streets["link_id"] = gdf_streets["link_id"].astype(str)  # importante: mismo tipo que en POIs

# --- 3. Merge por LINK_ID ---
merged = df_pois.merge(gdf_streets[["link_id", "geometry"]], left_on="LINK_ID", right_on="link_id", how="left")

from shapely.geometry import LineString

# Filtrar filas con geometría válida
valid_geom = merged["geometry"].notnull()

# Crear GeoSeries solo con las válidas
geo_series = gpd.GeoSeries(merged.loc[valid_geom, "geometry"]).set_crs("EPSG:4326")

# Calcular centroides y asignarlos
merged.loc[valid_geom, "geometry"] = geo_series.centroid

# --- 5. Convertir a GeoDataFrame ---
gdf_pois = gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")

# --- 6. Guardar resultado ---
gdf_pois.to_file("output_POIs.geojson", driver="GeoJSON")
print("Archivo exportado como 'output_POIs.geojson'")

