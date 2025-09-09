# Dollar General Store Locations and Median Income Spatial Analysis

This project performs a spatial analysis of Dollar General store locations across the United States in relation to median household income data from the US Census ACS. Using a 3-mile buffer around each store, the average median income of intersecting census tracts is calculated. The resulting data is visualized via an interactive Kepler.gl dashboard highlighting stores near areas of high median income.

## Data Sources

- **Dollar General Store Locations**  
  A free community-curated dataset of Dollar General store locations is referenced in this Reddit discussion:  
  [Dollar General Locations - r/gis Reddit](https://www.reddit.com/r/gis/comments/1bjn0sb/dollar_general_locations/)  
  The post includes links and methods for obtaining geospatial data for store locations.

- **Median Household Income Data**  
  Median income boundaries are sourced via the ArcGIS REST API, built on American Community Survey data. This data provides block group level median income estimates used in the spatial join.

- **Market Insights**  
  Research articles highlight the growing appeal of Dollar General stores among middle- and high-income shoppers. For context on Dollar General's market penetration and shopper demographics, see:  
  [Dollar Stores Draw in Six-Figure Income Shoppers - Yahoo Finance](https://finance.yahoo.com/news/dollar-stores-draw-in-more-shoppers-making-six-figures-as-americans-across-income-levels-look-to-save-080041053.html?guccounter=1&guce_referrer=aHR0cHM6Ly93d3cuZ29vZ2xlLmNvbS8&guce_referrer_sig=AQAAAGA-vEr7oJVdq60lBstlJqpfLja9Pq8ZpIS0h4OvzzdhjYrWSFCbw3pSf1BA-ztAyQ2ncZCPl_lxL-q6IUf3n8RsCA6ycrUqBlHb6Wu7eM9NKnZzXwXyLpAsi_eTCDGBPd-Q32SQag52M5q5pX_Fs17xdSqiQ3IsvlJXW7nNj1GO)

## Workflow Overview

1. Load the Dollar General store locations from a GeoPackage file.
2. Download median household income polygons from the ACS ArcGIS REST service in GeoJSON format, with error handling on the request.
3. Set CRS on input data if missing, ensuring consistent projections.
4. Project data to EPSG:3857 for accurate buffering (3-mile radius around each store).
5. Perform a spatial join to find census tracts intersecting each buffer.
6. Dynamically detect the median income field in the data for averaging.
7. Calculate the average median income for intersecting tracts per buffer.
8. Filter buffers for areas with average median income **≥ $100,000**, handling missing data.
9. Visualize results interactively using Kepler.gl, showing:
   - The high income buffer areas labeled "High Income Areas (3 mi)"
   - The Dollar General store points

## Usage Instructions

- Run the provided Python script in Google Colab or a compatible environment.
- Upload your Dollar General stores GeoPackage when prompted.
- The script reports how many features were downloaded and processed.
- The interactive Kepler.gl dashboard HTML file is saved and automatically downloaded.
- If no high-income areas are found at the threshold, only the store points are shown in the map.

## Requirements

- Python environment with `geopandas`, `keplergl`, `requests`, `shapely`, `pyproj`, and `pandas` installed.
- GeoPackage file containing Dollar General store point locations.
- Internet access to query ACS data via ArcGIS REST API.

## Notes

- The median income field is automatically detected among common ACS fields to accommodate slight variations in schema.
- The script includes error handling for API requests and dashboard saving.
- Coordinate reference systems are managed explicitly for correct spatial calculations.

---

