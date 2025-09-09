# === Install Required Packages (run once) ===
# !pip install geopandas keplergl requests shapely pyproj

# === Imports ===
import geopandas as gpd
import requests
import pandas as pd
from keplergl import KeplerGl
from pathlib import Path

# === Config ===
GEOPACKAGE_PATH = "path/to/your_geopackage.gpkg"  # <-- update
OUTPUT_DIR = "output"
Path(OUTPUT_DIR).mkdir(exist_ok=True)

# === Download Helper (paging ArcGIS) ===
def fetch_all_features(url, base_params, page_size=2000, timeout=60):
    params = base_params.copy()
    params['resultRecordCount'] = page_size
    params['resultOffset'] = 0
    features = []
    while True:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        feats = data.get('features', [])
        features.extend(feats)
        if len(feats) < page_size:
            break
        params['resultOffset'] += page_size
    return {'type': 'FeatureCollection', 'features': features}

# === Load stores ===
gdf_stores = gpd.read_file(GEOPACKAGE_PATH)
if gdf_stores.crs is None:
    gdf_stores.set_crs(epsg=4326, inplace=True)
print(f"Loaded {len(gdf_stores)} stores")

# === Get income polygons ===
arcgis_url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Median_Income_by_Race_and_Age_Selp_Emp_Boundaries/FeatureServer/0/query"
params = {
    "where": "1=1",
    "outFields": "B19053_001M,B19053_001E,GEOID,NAME",
    "f": "geojson",
    "returnGeometry": "true"
}
income_geojson = fetch_all_features(arcgis_url, params, page_size=2000)
gdf_income = gpd.GeoDataFrame.from_features(income_geojson['features']).set_crs(epsg=4326)
print(f"Downloaded {len(gdf_income)} income polygons")

# === Project to Albers Equal Area (better for distance) ===
gdf_stores_proj = gdf_stores.to_crs(epsg=5070)
gdf_income_proj = gdf_income.to_crs(epsg=5070)

# === Create 10‑mile buffers ===
buffer_dist_m = 10 * 1609.34  # 10 miles in meters
gdf_stores_proj['buffer_10mi'] = gdf_stores_proj.geometry.buffer(buffer_dist_m)
gdf_buffers = gpd.GeoDataFrame(
    gdf_stores_proj.drop(columns='geometry'),
    geometry='buffer_10mi',
    crs=gdf_stores_proj.crs
)

# === Spatial Join: income polygons intersecting buffers ===
print("Performing spatial join...")
joined = gpd.sjoin(gdf_income_proj, gdf_buffers, how='inner', predicate='intersects')
print(f"Created {len(joined)} tract-buffer matches")

# === Aggregate income per buffer (by buffer index) ===
income_field = 'B19053_001M' if 'B19053_001M' in joined.columns else None
if income_field is None:
    numeric_cols = joined.select_dtypes(include=['number']).columns
    income_field = numeric_cols[0]
    print(f"Fallback using field: {income_field}")

agg = joined.groupby('index_right')[income_field].agg(['mean', 'count']).rename(
    columns={'mean': 'avg_median_income_10mi', 'count': 'tract_count'}
)

# === Merge back onto buffers with GeoPandas .join (preserves geometry) ===
gdf_buffers = gdf_buffers.join(agg, how='left')
gdf_buffers['avg_median_income_10mi'] = gdf_buffers['avg_median_income_10mi'].fillna(0).round(2)
gdf_buffers['tract_count'] = gdf_buffers['tract_count'].fillna(0).astype(int)

# === Reproject to WGS84 for web viz ===
gdf_stores_wgs84  = gdf_stores_proj.to_crs(epsg=4326)
gdf_buffers_wgs84 = gdf_buffers.to_crs(epsg=4326)
gdf_income_wgs84  = gdf_income_proj.to_crs(epsg=4326)

print(f"Buffer columns: {list(gdf_buffers_wgs84.columns)}")
print(f"Active geometry: {gdf_buffers_wgs84.geometry.name}")

# Optional: simplify for performance
gdf_buffers_wgs84.geometry = gdf_buffers_wgs84.geometry.simplify(0.002)
gdf_income_wgs84.geometry  = gdf_income_wgs84.geometry.simplify(0.001)

# === Clean up multiple geometry columns before saving ===
# Check for multiple geometry columns and keep only the active one
geom_cols = [col for col in gdf_buffers_wgs84.columns if gdf_buffers_wgs84[col].dtype == 'geometry']
if len(geom_cols) > 1:
    # Keep only the active geometry column
    active_geom = gdf_buffers_wgs84.geometry.name
    cols_to_drop = [col for col in geom_cols if col != active_geom]
    gdf_buffers_wgs84 = gdf_buffers_wgs84.drop(columns=cols_to_drop)
    print(f"Dropped extra geometry columns: {cols_to_drop}")

# === Save outputs ===
gdf_buffers_wgs84.to_file(f"{OUTPUT_DIR}/store_buffers_income_10mi.geojson", driver="GeoJSON")
print("Saved buffers with income stats")

# === Kepler.gl viz: three layers ===
map_1 = KeplerGl(height=700)
map_1.add_data(data=gdf_income_wgs84, name="Income Polygons")
map_1.add_data(data=gdf_buffers_wgs84, name="Store Buffers (10 mi) w/ Income Avg + Count")
map_1.add_data(data=gdf_stores_wgs84, name="Store Points")

dashboard_html = f"{OUTPUT_DIR}/kepler_spatial_join_10mi.html"
try:
    map_1.save_to_html(file_name=dashboard_html)
    print(f"Dashboard saved to {dashboard_html}")
except Exception as e:
    print(f"Error saving dashboard: {e}")

map_1
