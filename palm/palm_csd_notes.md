# palm_csd Evaluation Notes

**Status:** Evaluated from documentation and source inspection. Not executed (requires Linux + PALM environment).
**Date:** 2026-03-28
**Verdict:** palm_csd has hard blockers for our use case. See ADR-002 for the decision.

---

## What palm_csd Is

- Part of the PALM model system distribution: `packages/static_driver/palm_csd/`
- Written in **Python 3**
- Purpose: generates PALM static driver files (NetCDF) from pre-processed geodata
- Configuration: INI file format (parsed by Python's `ConfigParser`)
- License: GPL-3.0+ (same as PALM)
- Invocation: `palm_csd <config_file>` (command-line only, no importable Python API)

## What palm_csd Handles

- Terrain (DEM)
- Buildings (2D heights at LOD1, 3D at LOD2, building IDs, building types)
- Vegetation (type, LAI, height, patches)
- Individual street trees (height, crown diameter, trunk diameter, species type — 87-species database)
- Water bodies
- Pavement types
- Green roofs (extensive/intensive)
- Bridges
- Streets (for multi-agent modeling)
- Soil type

## Critical Blockers for Our Use Case

### Blocker 1: NetCDF-only input

palm_csd accepts **only pre-rasterised NetCDF files** as input. All variables must be named `'Band1'`. It cannot process GeoTIFF, shapefile, GeoJSON, CityGML, or CSV directly.

This means we would need an entire upstream pipeline to:
1. Fetch geodata from OSM / CityGML / user uploads (various formats)
2. Rasterise to the PALM grid
3. Convert to NetCDF with `Band1` variable naming
4. Then call palm_csd

This defeats the purpose of wrapping palm_csd — we'd be doing most of the hard work ourselves before palm_csd even runs.

### Blocker 2: City-specific hardcoding

The palm_csd documentation explicitly states it currently works **"only for the demo cities Berlin, Hamburg, and Stuttgart."** Adapting to other cities requires modification of the code. Our product must work for any location.

### Blocker 3: Slated for replacement

The palm_csd documentation states it will be **"replaced by a more generic and universal tool"** in the mid-term. Investing in wrapping a tool that its own maintainers plan to replace is poor strategy.

### Blocker 4: No Python API

palm_csd is command-line only. There is no importable Python interface. We would have to shell out to it, which is fragile and makes error handling harder.

## What IS Reusable from palm_csd

Despite the blockers against wrapping it as a subprocess, palm_csd contains valuable reference material:

1. **Tree species database** — 87 species with LAD/BAD profiles. This is directly reusable as seed data for our species catalogue.
2. **NetCDF output routines** — The code that writes PIDS-compliant static driver files. These routines show the exact variable names, dimensions, attributes, and fill values PALM expects.
3. **LOD logic** — How palm_csd distinguishes LOD1 (2D building heights) from LOD2 (3D voxel buildings) and sets the appropriate variables.
4. **Parameter mapping** — How vegetation types, pavement types, water types map to PALM's internal classification integers.

## Alternative Tools Discovered

| Tool | Language | Input formats | Key feature | Status |
|---|---|---|---|---|
| **palmpy** | Python | GeoTIFF, shapefile | Importable Python API (`palmpy.staticcreation`). Handles standard geodata formats. GPL-3.0. | Last release Feb 2023 (v1.1.0). May be stale. |
| **GEO4PALM** | Python | GeoTIFF, shapefile | Web GUI (Panel/Bokeh). Automated data download (NASA/ESA/OSM). Nested domains. Peer-reviewed in GMD 2024. | Active. |
| **SanDyPALM** | Python | Raster + vector, OSM, WRF | Creates both static AND dynamic drivers. OSM2PALM and LCZ4PALM automated extraction. Published in GMD 2025. | Newest and most complete. |
| **rPALM** | R | Raster from QGIS/ArcGIS | R6 classes. LOD2. | Available. |

## Recommendation

Do not wrap palm_csd as a subprocess backbone. Instead:

1. **Write our own static driver generator** targeting the PIDS NetCDF spec directly (the spec is well-documented at the PALM wiki).
2. **Use palm_csd's species database and parameter mappings** as reference data (copy the data, not the code — data is factual, not copyrightable).
3. **Evaluate palmpy and SanDyPALM** as potential Python libraries to import or reference, particularly for:
   - palmpy's `staticcreation` module (if it produces PIDS-compliant output)
   - SanDyPALM's OSM integration (if the code is reusable under its license)
4. **Target the PIDS specification directly** as our contract. This is more future-proof than depending on any one tool.

See ADR-002 for the formal decision.

## References

- palm_csd documentation: https://palm.muk.uni-hannover.de/trac/wiki/doc/app/iofiles/pids/palm_csd
- PALM static driver format (PIDS): https://palm.muk.uni-hannover.de/trac/wiki/doc/app/iofiles/pids/static
- palm_csd source (v22.10): https://gitlab.palm-model.org/releases/palm_model_system/-/tree/v22.10/packages/static_driver/palm_csd
- Heldens et al. (2020): Geospatial input data for PALM 6.0, GMD
- palmpy: https://github.com/stefanfluck/palmpy
- GEO4PALM: https://github.com/dongqi-DQ/GEO4PALM (GMD 2024)
- SanDyPALM: GMD 2025 (https://gmd.copernicus.org/articles/18/6063/2025/)
