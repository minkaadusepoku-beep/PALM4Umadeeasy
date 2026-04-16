# PALM4Umadeeasy — Scientific Methodology

**Version:** 1.0  
**Date:** 2026-04-09  
**Author:** Minka Aduse-Poku, PhD  
**Status:** Living document — updated as implementation progresses

This document describes the scientific methodology underpinning PALM4Umadeeasy. It is intended to be citable in reports and publications. Sections marked **[IMPLEMENTED]** describe methodology that is coded and tested. Sections marked **[PLANNED]** describe methodology that is designed but not yet implemented. Sections marked **[STUB]** describe components where a structural placeholder exists but the full methodology is pending.

---

## 1. Modelling Scope

### 1.1 Questions Addressed

PALM4Umadeeasy is designed to answer intervention-comparison questions of the form:

> "How does a specific set of green/blue infrastructure changes affect outdoor thermal comfort and wind conditions at the pedestrian level, compared to a baseline or alternative scenario?"

The platform does not answer questions about indoor climate, building energy demand, hydrology, or air quality (pollutant dispersion is planned for a future phase).

### 1.2 Physical Model

The underlying physics engine is PALM (Parallelized Large-Eddy Simulation Model), version 23.10 or later. PALM solves the non-hydrostatic, filtered Navier-Stokes equations using the Boussinesq approximation. It is a Large-Eddy Simulation (LES) model, meaning it explicitly resolves turbulent structures at the grid scale and parameterises sub-grid-scale turbulence.

Key PALM modules used:
- **Urban Surface Model (USM):** resolves building surfaces, walls, roofs, their radiation balance and heat storage
- **Land Surface Model (LSM):** resolves ground surface energy balance for vegetated and non-vegetated surfaces
- **Plant Canopy Model:** resolves drag and radiation absorption by tree canopies using leaf area density (LAD) profiles
- **Radiation Model (RRTMG):** computes shortwave and longwave radiation including shadows from buildings and vegetation
- **Biometeorology Module:** computes thermal comfort indices (PET, UTCI, MRT) at pedestrian height

PALM4Umadeeasy does not modify PALM's physics. It wraps PALM with a translation layer (scenario -> PALM inputs), a post-processing layer (PALM outputs -> classified results), and a comparison layer (scenario A vs B).

### 1.3 Spatial and Temporal Scope

- **Horizontal domain:** typically 200m x 200m to 2000m x 2000m
- **Horizontal resolution:** 1m to 50m (default: 10m)
- **Vertical grid:** stretched, with fine resolution near ground (default: dz = 2m near surface)
- **Simulation period:** typically 6-24 hours
- **Output interval:** 30 minutes (default)

### 1.4 Explicit Non-PALM Output Layers

**[IMPLEMENTED]** The platform includes one advisory layer that is explicitly NOT derived from PALM simulation:

- **Facade greening advisory:** First-order literature-based estimates of pollutant uptake, cooling effect, and energy savings for vertical greening systems. Every output from this module carries provenance flags:
  - `result_kind: "advisory_non_palm"`
  - `coupled_with_palm: false`
  - `uncertainty: "high"`

These estimates are never merged with PALM-derived outputs. They are presented in a separate UI panel with a prominent advisory banner. This separation is a structural enforcement, not a UI convention — the provenance flags are embedded in every API response and cannot be suppressed.

**Rationale:** Facade greening effects (deposition velocity, evapotranspiration cooling) cannot currently be represented in PALM's plant canopy model for vertical surfaces. Rather than omit the topic entirely, the platform provides transparent first-order estimates drawn from the author's published research (Aduse-Poku 2024, 2025) with explicit uncertainty labelling.

---

## 2. Input Data Tiers and Handling

### 2.1 Data Quality Tiers

**[IMPLEMENTED]** Every data source is tagged with one of three quality tiers:

| Tier | Label | Typical Sources | Typical Accuracy |
|---|---|---|---|
| SCREENING | Screening-grade (public data) | OSM buildings (estimated heights), Copernicus DEM (30m), Corine/OSM land use | Buildings: +/-2m height, +/-1m position. Terrain: +/-5m |
| PROJECT | Project-grade (verified data) | Municipal CityGML LoD2, surveyed tree cadaster, LiDAR DEM (1m) | Buildings: +/-0.5m. Terrain: +/-0.5m. Trees: individually positioned |
| RESEARCH | Research-grade (curated data) | LiDAR with QA, measured LAD profiles, in-situ forcing, calibrated soil | Highest available. Per-element field validation |

The scenario inherits the tier of its weakest major input category (buildings, terrain, or vegetation assessed separately).

### 2.2 Tier Propagation

**[IMPLEMENTED]** The weakest-link principle is enforced:

1. Each data source in a scenario is tagged with its tier
2. The scenario-level tier is `min(buildings_tier, terrain_tier, vegetation_tier)`
3. This tier propagates to every result, map, statistic, and report page
4. Tier-specific language is generated automatically (see S10)
5. Screening-grade results carry a visible "SCREENING" watermark on maps — non-removable

### 2.3 Building Edit Provenance Downgrade

**[IMPLEMENTED]** When users edit building geometry (add, modify, or remove buildings), the data quality tier is automatically downgraded:

| Condition | Maximum Tier |
|---|---|
| No building edits | Unchanged |
| >= 1 edit of any type | PROJECT (never RESEARCH) |
| >= 1 added building with height > 30m or footprint > 1000 m2 | SCREENING |

This prevents user-drawn buildings (which lack survey-grade accuracy) from being presented with unwarranted confidence.

### 2.4 Data Sources

| Source | Access | License |
|---|---|---|
| OpenStreetMap | Overpass API | ODbL 1.0 (attribution required) |
| Copernicus DEM (30m) | HTTP download | Copernicus licence (attribution required) |
| German state CityGML LoD2 | User upload / open data portals | Varies by state |
| LiDAR DEM | User upload | User's data |
| Tree inventories | User upload (CSV) | User's data |
| Meteorological forcing | Pre-built archetypes or user upload | DWD: GeoNutzV |

---

## 3. Preprocessing: Scenario Translation

### 3.1 Translation Layer Overview

**[IMPLEMENTED]** The translation layer converts a scenario JSON document into three PALM input files:

1. **Static driver** (NetCDF, PIDS-compliant) — terrain, buildings, vegetation, surfaces
2. **Namelist** (_p3d Fortran namelist) — simulation parameters, physics switches, output configuration
3. **Dynamic driver** (NetCDF) — meteorological forcing (initial and boundary conditions)

The translation layer targets the PIDS (PALM Input Data Standard) specification directly. palm_csd is NOT used — see ADR-002 for the documented blockers.

### 3.2 Static Driver Generation

**[IMPLEMENTED]** Module: `backend/src/translation/static_driver.py`

The static driver generator:
1. Accepts scenario JSON containing domain definition, tree placements, surface changes, green roof toggles, and building edits
2. Constructs a PALM-compatible grid based on domain bbox and resolution
3. Rasterises all spatial inputs to the grid using standard geospatial operations (Shapely, NumPy)
4. Writes PIDS-compliant NetCDF using netCDF4-python

**Domain grid computation:**

For geographic coordinates (EPSG:4326), bbox extents in degrees are converted to metres:
```
width_m  = (east - west) * 111,320 * cos(mid_latitude)
height_m = (north - south) * 111,320
nx = round(width_m / resolution_m)
ny = round(height_m / resolution_m)
```

For projected coordinates (e.g., EPSG:25832 UTM), bbox extents are already in metres and pass through directly.

**Building rasterisation [IMPLEMENTED]:**

Buildings are resolved from a base snapshot (typically OSM) plus an ordered chain of user edits (add, modify, remove). The resolution algorithm:

1. Load base building set from snapshot
2. Apply each edit in order (deterministic)
3. Project resolved building polygons from WGS84 to a local metric CRS using equirectangular projection centred on the domain centroid:
   ```
   x = R * (lon - lon0) * cos(lat0)
   y = R * (lat - lat0)
   ```
   where R = 6,378,137 m. At PALM-scale domains (< 2 km), this is sub-metre accurate.
4. For each grid cell centre, test containment against all building polygons. If multiple buildings overlap a cell, the tallest wins.
5. Write three NetCDF variables:
   - `buildings_2d` (float32): building height in metres
   - `building_id` (int32): unique integer per building
   - `building_type` (int8): PALM building type derived from wall material and roof type

**Building type mapping:**

| Wall Material | Roof Type | PALM Type | Description |
|---|---|---|---|
| concrete | flat | 3 | Office/commercial |
| brick | flat | 1 | Residential |
| brick | pitched | 2 | Residential, pitched |
| glass | flat | 5 | Modern commercial |
| steel | flat | 6 | Industrial |
| wood | pitched | 7 | Traditional |
| (default) | (any) | 1 | Generic residential |

**Tree representation [IMPLEMENTED]:**

Trees are represented as 3D leaf area density (LAD) profiles on the PALM grid. Each tree placement specifies species (from catalogue), position, and optionally height. The species catalogue provides:
- Crown height range
- Crown radius
- LAD vertical profile (normalised, then scaled to tree height)
- Trunk height

The LAD profile is written to the `lad` variable in the static driver at the appropriate grid cells and vertical levels.

**Topography [IMPLEMENTED]:**

A flat terrain stub is used (elevation = 0 everywhere). Full DEM integration is planned.

**Surface types [IMPLEMENTED]:**

Surface changes (e.g., asphalt -> grass) are rasterised to the `vegetation_type` and `pavement_type` variables using PALM's standard type codes.

### 3.3 Namelist Generation

**[IMPLEMENTED]** Module: `backend/src/translation/namelist.py`

The namelist generator uses Jinja2 templating to produce a PALM _p3d namelist. Key parameters:

- Grid dimensions (nx, ny, nz) derived from domain config
- Grid spacing (dx, dy, dz)
- Simulation period and output interval
- Biometeorology module enabled (thermal_comfort = .TRUE.)
- Radiation model (RRTMG) enabled
- Output variables: theta, u, v, bio_mrt*, bio_pet*, bio_utci*, t_surface*

The namelist includes a SHA-256 fingerprint of the scenario JSON for reproducibility tracing.

### 3.4 Dynamic Driver Generation

**[STUB]** Module: `backend/src/translation/dynamic_driver.py`

The current implementation generates synthetic meteorological forcing profiles for four archetypes:

| Archetype | Description |
|---|---|
| typical_hot_day | Representative NRW summer day (~30C peak) |
| heat_wave_day | Extreme heat event (~35C peak) |
| moderate_summer_day | Average summer conditions (~25C peak) |
| warm_night | Nocturnal assessment (~20C) |

**Limitation:** These are simplified single-level profiles, not full vertical atmospheric profiles. The variable names and dimensions are simplified for pipeline testing. A full rewrite targeting the PIDS dynamic driver specification with proper vertical profiles is required for production use.

**[PLANNED]** Production dynamic driver will:
- Accept user-uploaded measured forcing data (NetCDF) with format validation
- Generate profiles from DWD TRY (Test Reference Year) data for German locations
- Include proper vertical profiles (temperature, humidity, wind, pressure)
- Validate physical plausibility of all forcing variables

---

## 4. Validation Engine

### 4.1 Pre-Simulation Validation

**[IMPLEMENTED]** Module: `backend/src/validation/engine.py`

Every scenario is validated before translation. Validation produces blocking errors (prevent submission) and non-blocking warnings. There are no "warn and accept" paths for structural errors.

**Domain checks:**
- Minimum domain size (100m x 100m)
- Maximum domain size (resource-dependent)
- Grid dimension parity (even preferred for FFT performance)

**Tree checks:**
- Species exists in catalogue
- Position within domain bounds
- Height within species range
- Crown does not extend beyond domain
- No overlapping crowns (conflict detection)

**Surface checks:**
- Material exists in catalogue
- Polygon within domain bounds
- Minimum polygon area (4 x resolution^2)

**Building edit checks (ADR-004, 8 rules):**

| Rule | Check |
|---|---|
| Well-formed geometry | GeoJSON Polygon, >= 4 coords, closed ring, no self-intersection |
| Minimum footprint | >= 9 m2 in local metric CRS |
| Minimum edge length | >= 2 x domain resolution |
| Height bounds | [2.0, 300.0] m; warning above 80 m |
| Domain containment | Fully inside domain with one ghost-cell margin |
| No overlap | 0.5 m tolerance buffer against all existing buildings |
| Reference integrity | Modify/remove targets must exist at point of application |
| Deterministic ordering | Edit IDs unique; list order = application order |

**Simulation parameter checks:**
- Output interval does not exceed simulation duration
- Minimum simulation duration (1 hour)
- Resource estimation (total cells, estimated memory, estimated runtime)

**Comparison validation:**
- Baseline and intervention must share identical domain (bbox, resolution)
- Different forcing triggers a warning (valid but methodologically questionable)

### 4.2 Building Geometry Validation Coordinate System

**[IMPLEMENTED]** Module: `backend/src/validation/buildings.py`

All metric validation (area, edge length, overlap) uses a local equirectangular projection:

```
x = R * (lon - lon0) * cos(lat0)
y = R * (lat - lat0)
```

centred on the domain centroid (lon0, lat0). R = 6,378,137 m (WGS84 equatorial radius).

At PALM-scale domains (typically < 2 km), equirectangular projection error is < 0.01% — well below the 0.5 m overlap tolerance and 3 m minimum edge length (at 10 m resolution). This avoids a hard dependency on pyproj while maintaining sub-metre accuracy.

---

## 5. Simulation

### 5.1 PALM Execution

**[STUB — requires Linux environment]**

PALM is executed as an external process via MPI:
```
mpirun -np <N> palm <job_name>
```

The PALM runner monitors stdout for progress, detects completion or crash, and handles timeouts. PALM is compiled from unmodified source code (version pinned per product release).

### 5.2 Stub Mode (Current)

**[IMPLEMENTED]** For development and pipeline testing on Windows, the PALM runner generates synthetic output that mimics the structure of real PALM output:
- Correct NetCDF dimensions and variable names
- Physically plausible value ranges
- Deterministic output (same scenario -> identical stub output)

This allows the full pipeline (translation -> "execution" -> post-processing -> comparison -> report) to be tested without a Linux PALM installation. Stub results are clearly labelled and never presented as real simulation output.

---

## 6. Post-Processing

### 6.1 Variable Extraction

**[IMPLEMENTED]** Module: `backend/src/postprocessing/engine.py`

PALM output variables are extracted at the diagnostic height level (see S6.2). For each output timestep:

| PALM Variable | Derived Product | Display Name | Unit |
|---|---|---|---|
| `theta` | Air temperature (converted using surface pressure) | Air Temperature | C |
| `u`, `v`, `w` | Wind speed magnitude | Wind Speed | m/s |
| `bio_mrt*` | Mean radiant temperature | Radiant Temperature | C |
| Ta + Tmrt + wind + humidity | PET | Thermal Comfort (PET) | C |
| Ta + Tmrt + wind + humidity | UTCI | Thermal Comfort (UTCI) | C |
| `t_surface*` | Surface temperature | Surface Temperature | C |
| Wind speed | Lawson classification | Wind Comfort | Category |

### 6.2 Height Convention

**[IMPLEMENTED per ADR-003]**

PALM's biometeorology module computes thermal comfort indices at approximately **1.1 m above ground level**, representing the gravimetric centre of a standing reference person per VDI 3787 Blatt 2. This height is hardcoded in PALM (`biometeorology_mod.f90`, `bio_init`).

The actual output height depends on vertical grid spacing:

| dz (m) | Actual Output Height (m) | Deviation from 1.1 m |
|---|---|---|
| 1 | 1.5 | +0.4 |
| 2 | 1.0 | -0.1 |
| 5 | 2.5 | +1.4 |

The default configuration uses dz = 2 m near the ground (output at 1.0 m). A validation warning is issued if dz would place the output above 2.5 m.

Every result map and report states the actual output height.

### 6.3 Comfort Index Computation

**[IMPLEMENTED]**

**PET (Physiological Equivalent Temperature):**
- Computed using pythermalcomfort (Walther & Goestchel 2018 implementation)
- Inputs: air temperature, mean radiant temperature, wind speed, relative humidity
- Reference: Hoeppe (1999), with corrections per Walther & Goestchel (2018)
- **Known offset:** pythermalcomfort produces values 3-5C lower than RayMan for moderate conditions. This is expected — the Walther & Goestchel correction fixes known errors in the original Hoeppe implementation. This is documented in reports.

**UTCI (Universal Thermal Climate Index):**
- Computed using pythermalcomfort
- Reference: Broede et al. (2012)

**Our PET/UTCI computation serves as:**
- Validation check against PALM's internal bio-met computation
- Fallback if PALM's bio-met module is not enabled
- Path for indices PALM doesn't compute natively

### 6.4 Statistics

**[IMPLEMENTED]** For each output variable and timestep:
- Mean, median, standard deviation
- 5th and 95th percentiles
- Threshold exceedance area (m2 and % of domain)

---

## 7. Thermal Comfort Classification

### 7.1 PET Classification (VDI 3787 Blatt 2)

**[IMPLEMENTED]**

| PET (C) | Thermal Perception | Stress Grade | Map Colour |
|---|---|---|---|
| < 4 | Very cold | Extreme cold stress | Deep blue |
| 4-8 | Cold | Strong cold stress | Blue |
| 8-13 | Cool | Moderate cold stress | Light blue |
| 13-18 | Slightly cool | Slight cold stress | Cyan |
| 18-23 | Comfortable | No thermal stress | Green |
| 23-29 | Slightly warm | Slight heat stress | Yellow |
| 29-35 | Warm | Moderate heat stress | Orange |
| 35-41 | Hot | Strong heat stress | Red |
| > 41 | Very hot | Extreme heat stress | Dark red |

This colour scheme is non-negotiable and consistent across all maps, reports, and exports.

### 7.2 Wind Comfort Classification (Lawson / NEN 8100)

**[IMPLEMENTED]**

| Mean Wind (m/s) | Class | Acceptable For |
|---|---|---|
| < 2.5 | A — Sitting (long) | Outdoor dining, reading |
| 2.5-4.0 | B — Sitting (short) | Coffee, waiting |
| 4.0-6.0 | C — Standing | Bus stops, window shopping |
| 6.0-8.0 | D — Walking | Pedestrian through-routes |
| > 8.0 | E — Uncomfortable | Unacceptable for pedestrian use |

---

## 8. Comparison Methodology

### 8.1 Comparison Engine

**[IMPLEMENTED]** Module: `backend/src/postprocessing/comparison.py`

Every comparison produces:

1. **Difference grids:** Variable_intervention minus Variable_baseline at matched timesteps. Diverging colour scale (blue = improvement, white = no change, red = worsening).

2. **Delta statistics per zone:**
   - Mean change, max improvement, max worsening
   - Area improved (m2 and %)
   - Area worsened (m2 and %)
   - Percentage unchanged (within +/-0.5C tolerance)

3. **Threshold impact statement:** e.g., "In the baseline, 4,200 m2 (42%) exceeds PET 35C between 12:00-15:00. With the proposed tree planting, this reduces to 2,800 m2 (28%). Reduction: 1,400 m2 (14 pp)."

4. **Ranked zone summary:** Zones sorted by improvement magnitude.

5. **Fragmentation analysis:** Spatial coherence of improved/worsened areas.

### 8.2 Comparison Validity Requirements

- Baseline and intervention must share the same domain (bbox and resolution)
- Different forcing between scenarios is allowed but triggers a prominent warning
- Comparison is only meaningful when both scenarios use the same PALM version and configuration defaults

---

## 9. Confidence Propagation

### 9.1 Confidence Engine

**[IMPLEMENTED]** Module: `backend/src/confidence/engine.py`

Confidence levels map from data quality tiers:

| Data Quality Tier | Confidence Level | Suitable For |
|---|---|---|
| SCREENING | INDICATIVE | Initial assessment, feasibility screening |
| PROJECT | QUANTITATIVE | Planning decisions within stated limitations |
| RESEARCH | REFERENCE | Scientific analysis and publication |

### 9.2 Confidence Statement Generation

**[IMPLEMENTED]** Each result carries a structured confidence statement:
- **Headline:** one-sentence summary
- **Detail:** paragraph explaining basis and limitations
- **Caveats:** list of specific concerns
- **Suitable for / Not suitable for:** explicit guidance

### 9.3 Tier-Specific Report Language

**[IMPLEMENTED]**

- **SCREENING:** "Based on publicly available data (not independently verified). Suitable for initial assessment and feasibility screening. For planning decisions, verified project-grade data is recommended."
- **PROJECT:** "Based on verified project data. Suitable for planning decisions within stated model limitations."
- **RESEARCH:** "Based on curated research-grade data. Suitable for scientific analysis and publication, subject to stated model assumptions."

Visual indicators: screening-grade results carry a "SCREENING" watermark on maps. Not removable.

---

## 10. Reporting

### 10.1 Report Structure

**[IMPLEMENTED — stub mode]** Every generated PDF report follows this structure:

1. Cover page (project, scenarios, date, data tier)
2. Executive summary (3-5 sentences)
3. Study area description (map, data sources, quality tier)
4. Scenario descriptions (changes table, intervention map)
5. Methodology (PALM version, resolution, forcing, comfort indices, height convention)
6. Results: Baseline
7. Results: Intervention(s)
8. Comparison (difference maps, delta statistics, threshold impact)
9. Confidence and limitations
10. Appendix (full timestep data, zonal tables, technical parameters)
11. Footer (every page): "Model-based estimate. Not a measurement. See S9 for limitations."

### 10.2 Reproducibility

**[IMPLEMENTED]** Every run records:
- Frozen scenario JSON
- Catalogue versions
- PALM version
- Translation layer version
- Post-processing version
- SHA-256 fingerprint

Resubmitting the same scenario with the same software versions produces identical PALM inputs (deterministic translation).

---

## 11. Methodological Limitations

The following limitations apply to all results and are documented in every report:

### 11.1 Model Limitations
- PALM resolves turbulence at the grid scale. Features smaller than the horizontal resolution are parameterised, not resolved.
- Building geometry from OSM may differ from actual dimensions. Shadow patterns and wind channelling are sensitive to building accuracy.
- Vegetation representation uses idealised LAD profiles from literature, not measured profiles of specific trees on site.
- Soil moisture is set to a default assumption (field capacity for vegetated surfaces). Actual soil moisture affects evapotranspiration and surface temperature.

### 11.2 Forcing Limitations
- **[CURRENT]** Meteorological forcing uses simplified synthetic archetypes representative of NRW conditions, not site-specific or measured data. This limits results to relative comparison (intervention vs baseline) rather than absolute value prediction.
- **[PLANNED]** Production forcing from DWD TRY data will improve representativeness but still represents statistical climate, not specific weather events.

### 11.3 Domain Edge Effects
- PALM applies cyclic boundary conditions. Near domain edges, results may be influenced by artificial periodicity. The validation engine enforces ghost-cell margins for placed elements.

### 11.4 Comfort Index Limitations
- PET and UTCI assume a standardised reference person (35-year-old male, walking speed 1.1 m/s, typical clothing). Individual thermal perception varies.
- pythermalcomfort PET values are 3-5C lower than RayMan for moderate conditions due to corrected implementation (Walther & Goestchel 2018 vs original Hoeppe 1999).

### 11.5 Non-PALM Advisory Layer
- Facade greening estimates are first-order literature-based calculations, NOT simulation outputs. They carry high uncertainty and are not validated against site measurements. They are provided for screening-level comparison only.

---

## 12. Validation and Testing

### 12.1 Test Coverage

| Level | What | Method | Status |
|---|---|---|---|
| Translation unit tests | Each element type -> correct PIDS NetCDF | pytest with reference fragments | IMPLEMENTED (234 tests) |
| Comfort index validation | PET/UTCI vs reference implementations | Test matrix, tolerance +/-0.5C PET | IMPLEMENTED |
| Comparison engine tests | Known pair -> verify deltas | Synthetic grids, hand computation | IMPLEMENTED |
| Building rasteriser tests | Geometry -> correct grid cells | 4 deterministic regression tests | IMPLEMENTED |
| Building validation tests | 8-rule contract | 18 unit tests | IMPLEMENTED |
| Round-trip integration | Scenario -> translate -> run -> post-process | Full pipeline (stub PALM) | IMPLEMENTED |
| PALM integration | Real PALM execution | Linux required | PLANNED |
| Report regression | PDF sections, values, disclaimers | Text extraction + assertions | PLANNED |

### 12.2 Determinism Guarantee

The translation layer is verified deterministic: same scenario JSON -> byte-identical PALM inputs. This is tested in CI.

---

## References

- Aduse-Poku, M. (2024). Methodology for quantification of pollutant absorption by climbing plants. *ScienceDirect*. https://doi.org/10.1016/j.scitotenv.2024.170863
- Aduse-Poku, M. (2025). Quantifying pollutant absorption potential of facade climbing plants. *Springer Urban Ecosystems*. https://doi.org/10.1007/s11252-025-01689-4
- Broede, P. et al. (2012). Deriving the operational procedure for the Universal Thermal Climate Index (UTCI). *Int J Biometeorol*, 56, 481-494.
- Froehlich, D. & Matzarakis, A. (2020). Calculating human thermal comfort and thermal stress in the PALM model system 6.0. *Geosci. Model Dev.*, 13, 3055-3065.
- Hoeppe, P. (1999). The physiological equivalent temperature — a universal index for the biometeorological assessment of the thermal environment. *Int J Biometeorol*, 43, 71-75.
- Lawson, T.V. (1975). *The wind environment of buildings: a logical approach to the establishment of criteria.* Dept of Aeronautical Engineering, University of Bristol.
- Maronga, B. et al. (2020). Overview of the PALM model system 6.0. *Geosci. Model Dev.*, 13, 1335-1372.
- NEN 8100:2006. Wind comfort and wind danger in the built environment.
- Resler, J. et al. (2017). PALM-USM v1.0: A new urban surface model integrated into the PALM large-eddy simulation model. *Geosci. Model Dev.*, 10, 3635-3659.
- VDI 3787 Blatt 2:2008. Environmental meteorology — Methods for the human biometeorological evaluation of climate and air quality for urban and regional planning.
- Walther, E. & Goestchel, Q. (2018). The P.E.T. comfort index: Questioning the model. *Building and Environment*, 137, 1-10.

---

*End of Scientific Methodology v1.0*
