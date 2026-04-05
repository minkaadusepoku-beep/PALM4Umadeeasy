# ADR-002: Static Driver Generation Strategy

**Status:** Accepted — overrides IMPLEMENTATION_PLAN.md default assumption
**Date:** 2026-03-28
**Author:** Minka Aduse-Poku

## Context

The implementation plan (v3.0, section 5.2) stated:

> "Default assumption: reuse/wrap palm_csd as the preprocessing backbone unless Phase 0 proves a hard blocker."

Phase 0 evaluation has identified hard blockers. This ADR documents them and records the revised decision.

## palm_csd Evaluation Findings

### Blocker 1: NetCDF-only input format

palm_csd accepts only pre-rasterised NetCDF files with all variables named `'Band1'`. It cannot process GeoTIFF, shapefile, GeoJSON, CityGML, or CSV — the formats our users and data sources provide.

**Impact:** Wrapping palm_csd would require building an entire upstream pipeline to convert diverse geodata into palm_csd's specific NetCDF format. This upstream pipeline would contain most of the complexity. palm_csd itself would add an unnecessary format-conversion step rather than reducing work.

### Blocker 2: City-specific hardcoding

palm_csd documentation states it works "only for the demo cities Berlin, Hamburg, and Stuttgart." Our product must work for any location.

**Impact:** Adapting palm_csd to arbitrary locations would require modifying its source code, which means maintaining a fork of GPL code with ongoing merge conflicts as PALM evolves.

### Blocker 3: Slated for replacement

palm_csd's own documentation states it will be "replaced by a more generic and universal tool." Building on a tool that its maintainers plan to deprecate is poor strategy.

### Blocker 4: No Python API

palm_csd is command-line only (`palm_csd <config_file>`). No importable Python interface. Integration would require subprocess calls with INI config file generation — fragile and hard to validate.

## Decision

**Do not wrap palm_csd.** Build our own static driver generator targeting the PIDS NetCDF specification directly.

### What we build

A Python module (`backend/src/translation/static_driver.py`) that:

1. Accepts our scenario JSON + geodata (GeoJSON buildings, GeoTIFF DEM, tree placement points, surface polygons)
2. Rasterises all inputs to the PALM grid using standard Python geospatial tools (rasterio, shapely, numpy)
3. Writes a PIDS-compliant NetCDF static driver file using netCDF4-python
4. Validates the output against PIDS requirements (dimensions, attributes, fill values, value ranges)

### What we reuse from palm_csd (as reference data, not code)

1. **Tree species database** — The 87-species catalogue with LAD/BAD profiles and parameters. This is factual data, not copyrightable code. We will extract the species parameter values and include them in our `catalogues/species.json` with citation.
2. **PALM parameter mappings** — The integer codes for vegetation types (0-18), pavement types (0-15), water types (0-5), soil types (0-6), and building types. These are PALM-defined constants, not palm_csd intellectual property.
3. **LOD logic** — The distinction between LOD1 (2D building heights) and LOD2 (3D voxel buildings) and how each is represented in the static driver. This is defined by the PIDS spec, not by palm_csd.

### Alternative tools evaluated

| Tool | Verdict |
|---|---|
| **palmpy** (stefanfluck/palmpy) | Has importable Python API and handles GeoTIFF/shapefile. Last release Feb 2023 — possibly stale. Evaluate `palmpy.staticcreation` module as a potential shortcut for rasterisation logic. If it produces PIDS-compliant output and its code quality is acceptable, we may use parts of it (GPL-3.0 licensed — compatible if our static driver module is also GPL or if we call it as a separate process). |
| **GEO4PALM** | Peer-reviewed (GMD 2024). Has automated OSM download and nested domain support. Heavier dependency (Panel/Bokeh GUI). Evaluate for reference on OSM-to-PALM data conversion patterns. |
| **SanDyPALM** | Newest (GMD 2025). Creates both static AND dynamic drivers. OSM integration. Most complete. Evaluate for reference and potentially for dynamic driver generation. |

**Action:** Evaluate palmpy's `staticcreation` module in early Phase 1. If it cleanly produces PIDS-compliant output from GeoTIFF/shapefile inputs, use it as a library dependency rather than reimplementing rasterisation from scratch. If it doesn't, implement our own using the PIDS spec as the contract.

## Consequences

1. **The IMPLEMENTATION_PLAN.md section 5.2 default assumption is overridden.** References to "palm_csd backbone" in the plan should be read as "custom static driver generator targeting PIDS spec" going forward.
2. **Our translation layer is more custom code than originally planned.** This increases Phase 1 scope but gives us full control over the input pipeline and eliminates a fragile subprocess dependency.
3. **The PIDS specification becomes our contract**, not palm_csd's behavior. This is more future-proof — as PALM evolves, we track the spec, not a tool that may be deprecated.
4. **We must write thorough integration tests** that verify our generated static drivers produce valid PALM simulations. We cannot rely on palm_csd's implicit validation.
5. **palmpy evaluation is added to early Phase 1** as a potential shortcut. This is not a blocker — we can build from scratch if palmpy doesn't fit.

## References

- palm_csd documentation: https://palm.muk.uni-hannover.de/trac/wiki/doc/app/iofiles/pids/palm_csd
- PIDS static driver spec: https://palm.muk.uni-hannover.de/trac/wiki/doc/app/iofiles/pids/static
- Detailed evaluation notes: `palm/palm_csd_notes.md`
- palmpy: https://github.com/stefanfluck/palmpy
- GEO4PALM: https://github.com/dongqi-DQ/GEO4PALM
- SanDyPALM: https://gmd.copernicus.org/articles/18/6063/2025/
