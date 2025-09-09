# === Install Required Packages ===
# Run this manually before running the script, e.g.:
# pip install geopandas keplergl requests shapely pyproj pandas

import geopandas as gpd
import requests
import pandas as pd
from keplergl import KeplerGl

# For file dialogs (used here for local file selection, adjust if running outside Jupyter)
import tkinter as tk
from tkinter import filedialog
import os

def select_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Select Dollar General GeoPackage file", 
                                           filetypes=[("GeoPackage Files", "*.gpkg")])
    return file_path

def main():
    # === Upload / Select your GeoPackage file ===
    gpkg_filename = select_file()
    if not gpkg_filename:
        print("No file selected, exiting.")
        return
    
    print(f"Selected GeoPackage file: {gpkg_filename}")

    # === Load GeoPackage (Dollar General stores) ===
    gdf_stores = gpd.read_file(gpkg_filename)

    # === Download ACS Median Income Boundaries from ArcGIS REST API ===
    arcgis_url = 'https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/ACS_Median_Income_by_Race_and_Age_Selp_Emp_Boundaries/FeatureServer/0/query'
    params = {
        'where': '1=1',
        'outFields': '*',
        'f': 'geojson',
        'returnGeometry': 'true'
    }

    # Add error handling for API request
    try:
        response = requests.get(arcgis_url, params=params)
        response.raise_for_status()  # Raises HTTPError for bad responses
        income_geojson = response.json()
        print(f"Successfully downloaded {len(income_geojson['features'])} features")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading data: {e}")
        return

    # === Convert JSON Response to GeoDataFrame ===
    gdf_income = gpd.GeoDataFrame.from_features(income_geojson['features'])
    gdf_income.set_crs(epsg=4326, inplace=True)

    # === Ensure CRS Consistency and Project to a Conformal Projection for Buffering ===
    if gdf_stores.crs is None:
        gdf_stores.set_crs(epsg=4326, inplace=True)
        print("Set CRS for stores to EPSG:4326")

    if gdf_stores.crs != gdf_income.crs:
        gdf_stores = gdf_stores.to_crs(gdf_income.crs)
        print(f"Reprojected stores to {gdf_income.crs}")

    # Project both to EPSG:3857 (Web Mercator) for accurate buffering in meters
    gdf_stores_proj = gdf_stores.to_crs(epsg=3857)
    gdf_income_proj = gdf_income.to_crs(epsg=3857)

    # === Buffer Stores by 3 miles (1 mile = 1609.34 meters) ===
    buffer_distance = 3 * 1609.34  # 3 miles in meters
    gdf_stores_proj['buffer_3mi'] = gdf_stores_proj.geometry.buffer(buffer_distance)

    # Make a GeoDataFrame of buffers
    gdf_buffers = gpd.GeoDataFrame(gdf_stores_proj.drop(columns='geometry'), geometry='buffer_3mi', crs=gdf_stores_proj.crs)

    # === Spatial Join: Find ACS Tracts intersecting each buffer ===
    joined = gpd.sjoin(gdf_income_proj, gdf_buffers, how='inner', predicate='intersects')

    # === Calculate Average Median Income for each buffer polygon ===
    income_fields = [col for col in joined.columns if 'income' in col.lower() or 'B19' in col]
    print(f"Available income fields: {income_fields}")

    income_field = None
    possible_fields = ['B19053_001M', 'B19053_001E', 'MedianIncome', 'MEDIAN_INCOME', 'MedInc']
    for field in possible_fields:
        if field in joined.columns:
            income_field = field
            break

    if income_field is None:
        numeric_cols = joined.select_dtypes(include=['number']).columns
        income_field = numeric_cols[0] if len(numeric_cols) > 0 else 'B19053_001M'
        print(f"Using field: {income_field}")

    avg_income = joined.groupby('index_right')[income_field].agg(['mean', 'count']).reset_index()
    avg_income.columns = ['index_right', 'avg_median_income_3mi', 'tract_count']
    avg_income = avg_income[avg_income['tract_count'] > 0]

    gdf_buffers = gdf_buffers.merge(avg_income, left_index=True, right_on='index_right', how='left')

    # === Filter buffers for high median income (threshold $100,000) ===
    gdf_buffers['avg_median_income_3mi'] = gdf_buffers['avg_median_income_3mi'].fillna(0)
    high_income_buffers = gdf_buffers[gdf_buffers['avg_median_income_3mi'] >= 100000]
    print(f"Found {len(high_income_buffers)} high-income buffer areas out of {len(gdf_buffers)} total")

    high_income_buffers = gpd.GeoDataFrame(high_income_buffers, geometry='buffer_3mi', crs=gdf_buffers.crs)

    # === Reproject back to WGS84 for visualization ===
    high_income_buffers_wgs84 = high_income_buffers.to_crs(epsg=4326)
    gdf_stores_wgs84 = gdf_stores_proj.to_crs(epsg=4326)

    # === Create Kepler.gl Dashboard ===
    map_1 = KeplerGl(height=600)

    if len(high_income_buffers_wgs84) > 0:
        map_1.add_data(data=high_income_buffers_wgs84, name="High Income Areas (3 mi)")
        print(f"Added {len(high_income_buffers_wgs84)} high-income buffer areas to map")
    else:
        print("No high-income areas found to display")

    map_1.add_data(data=gdf_stores_wgs84, name="Dollar Stores")
    print(f"Added {len(gdf_stores_wgs84)} store locations to map")

    # === Save Dashboard ===
    dashboard_html = "kepler_dashboard.html"
    try:
        map_1.save_to_html(file_name=dashboard_html)
        print(f"Dashboard saved as {dashboard_html}")
    except Exception as e:
        print(f"Error saving dashboard: {e}")

if __name__ == "__main__":
    main()
