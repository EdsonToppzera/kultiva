# Design & UI/UX

Mobile-First, Offline-First (PWA) interface guidelines and visual standards for evolving the React/Vite frontend (`frontend/`).

## Geospatial UX Suggestions (Inspired by the FAO GAEZ v5 Portal)

To bring the strategic layer closer to the farmer without exposing GIS technical complexity in `frontend/src/pages/MapTerrainPage.tsx` and the `[M2]`/`[M3]` screens:

1. **Direct WMS/WMTS Layers in Leaflet:**
   - Consume FAO's public OGC WMS service (`https://data.apps.fao.org/geoserver/wms`) over the interactive map to visualize regional suitability for the selected crop and soil class without downloading full rasters on the client.
2. **Side-by-Side Comparison (Split View):**
   - Slider splitting the map between **historical climate (`HP0120`) vs. CMIP6 future scenario (`2021–2040 SSP370`)** or between **Rainfed (`LRLM`) vs. Irrigated (`HILM`)** management.
3. **Point-Based Query (Feature Information):**
   - When clicking a point/plot on the map, display a simple summary connected to `GET /api/v1/culturas/aptidao-gaez` containing:
     - Recommended crop and estimated attainable yield (`kg/ha`);
     - Soil class (HWSD v2.01) and slope (`SLOPE-MED`);
     - Main limiting factor (`SQ-IDX`, e.g., nutrient retention, drainage, or acidity) translated into everyday language.
4. **Transparency in Simulator `[M3]` Cards:**
   - Visually display `score_breakdown` (water suitability, heat stress, temporal stability, FAO GAEZ suitability, and `kg/ha`) always accompanied by the plain-language explanation and legal disclaimer (`DISCLAIMER`).
