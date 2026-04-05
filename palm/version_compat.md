# PALM Version Compatibility and I/O Reference

**Status:** Documented from research. To be verified against actual PALM installation.
**Date:** 2026-03-28

---

## Recommended PALM Version

**PALM 23.10** (October 2023) or newer stable release.

- Version naming: `YY.MM` (year.month)
- Check latest: https://gitlab.palm-model.org/releases/palm_model_system/-/releases
- Note: v25.10 may exist as of late 2025. Evaluate if significant improvements to bio-met or USM modules warrant upgrading. Pin to a specific version for our product and document it.

### Required modules (all included in standard PALM distribution)

| Module | Purpose | Activation |
|---|---|---|
| Urban Surface Model (USM) | Building surface energy balance | Namelist: `&urban_surface_parameters` |
| Land Surface Model (LSM) | Ground surface energy balance | Namelist: `&land_surface_parameters` |
| Plant Canopy Model | Resolved vegetation (trees, LAD) | Namelist: `&plant_canopy_parameters` |
| Radiation (RRTMG) | Shortwave/longwave radiation, shadows | Namelist: `&radiation_parameters` |
| Biometeorology | PET, UTCI, MRT | Namelist: `&biometeorology_parameters` |
| Building Surface Model | Building wall/roof thermal processes | Part of USM |

All modules are compiled by default. Activation is via namelist inclusion at runtime.

---

## PALM Input File Structure

### Files PALM expects per simulation

| File | Format | Content | How we generate it |
|---|---|---|---|
| `<case>_p3d` | Fortran namelist (text) | All simulation parameters: grid, physics, output, module switches | Jinja2 template with variable substitution |
| `<case>_static` | NetCDF-4 (PIDS format) | Domain geometry: buildings, terrain, vegetation, surfaces, trees, soil | Our translation layer (custom, targeting PIDS spec) |
| `<case>_dynamic` | NetCDF-4 | Meteorological forcing: vertical profiles of T, u, v, q over time | Pre-built template files or user upload |

### Namelist structure (`_p3d` file)

The namelist file contains multiple Fortran namelist groups:

```fortran
&initialization_parameters
    nx = 49,  ny = 39,  nz = 40,          ! grid dimensions (0-indexed)
    dx = 10.0,  dy = 10.0,  dz = 10.0,    ! grid spacing [m]
    origin_date_time = '2025-07-19 06:00:00 +02',
    ! ... physics switches, boundary conditions
/

&runtime_parameters
    end_time = 21600.0,                     ! simulation duration [s] (6h)
    dt_data_output = 1800.0,                ! output interval [s]
    data_output = 'theta', 'u', 'v', 'w',
                  'bio_mrt*', 'bio_pet*', 'bio_utci*',
                  't_surface*',
    ! ... more output control
/

&radiation_parameters
    radiation_scheme = 'rrtmg',
/

&biometeorology_parameters
    thermal_comfort = .TRUE.,
/

&plant_canopy_parameters
    canopy_mode = 'read_from_file',         ! read LAD from static driver
/

&land_surface_parameters
    ! land surface model settings
/

&urban_surface_parameters
    ! urban surface model settings
/
```

### Static driver NetCDF structure (PIDS format)

The static driver must conform to the PALM Input Data Standard (PIDS), CF-1.7 conventions.

**Required global attributes:**
- `origin_lat` (float): geographic latitude of domain origin
- `origin_lon` (float): geographic longitude of domain origin
- `origin_x` (float): UTM easting of domain origin [m]
- `origin_y` (float): UTM northing of domain origin [m]
- `origin_z` (float): height above sea level of domain origin [m]
- `Conventions` = "CF-1.7"

**Required dimensions:**
- `x` (nx): grid cells in x-direction
- `y` (ny): grid cells in y-direction
- `z` (nz): vertical levels (for 3D variables)
- `zlad`: vertical levels for leaf area density
- `nsurface_fraction` (3): vegetation, pavement, water fractions
- `nvegetation_pars` (12): vegetation parameter indices
- `npavement_pars` (4): pavement parameter indices
- `nbuilding_surface_pars` (28): building surface parameter indices

**Key variables:**

| Variable | Dimensions | Type | Required | Description |
|---|---|---|---|---|
| `zt` | (y, x) | float | Yes | Terrain height [m]. No fill values allowed. |
| `buildings_2d` | (y, x) | float | If buildings | Building height above terrain [m] (LOD1) |
| `buildings_3d` | (z, y, x) | byte | If LOD2 | 3D building mask (1=building, 0=air) |
| `building_id` | (y, x) | int | If buildings | Unique building identifier |
| `building_type` | (y, x) | byte | If buildings | Building type classification |
| `vegetation_type` | (y, x) | byte | If vegetation | PALM vegetation type (0-18) |
| `pavement_type` | (y, x) | byte | If pavement | PALM pavement type (0-15) |
| `water_type` | (y, x) | byte | If water | PALM water type (0-5) |
| `soil_type` | (y, x) | byte | If soil | PALM soil type (0-6) |
| `surface_fraction` | (nsurface_fraction, y, x) | float | Yes | Fraction: [vegetation, pavement, water] per cell. Must sum to 1. |
| `lad` | (zlad, y, x) | float | If trees | Leaf area density [m2/m3] |
| `bad` | (zlad, y, x) | float | If trees | Basal area density [m2/m3] (trunks) |
| `tree_id` | (y, x) | int | If individual trees | Individual tree identifier |
| `tree_type` | (y, x) | byte | If individual trees | Tree species type (0-86 in palm_csd database) |
| `vegetation_pars` | (nvegetation_pars, y, x) | float | Optional | Per-pixel vegetation parameter overrides |
| `pavement_pars` | (npavement_pars, y, x) | float | Optional | Per-pixel pavement parameter overrides |

**Fill values:** `-9999.0` (float), `-9999` (int), `-127` (byte).

Full specification: https://palm.muk.uni-hannover.de/trac/wiki/doc/app/iofiles/pids/static

### Dynamic driver structure

Meteorological forcing as time-varying vertical profiles:

| Variable | Dimensions | Description |
|---|---|---|
| `init_atmosphere_pt` | (z) | Initial potential temperature profile [K] |
| `ls_forcing_left_pt` | (time, z) | Large-scale forcing: pot. temperature at boundaries |
| `ls_forcing_left_u` | (time, z) | Large-scale forcing: u-wind at boundaries |
| `ls_forcing_left_v` | (time, z) | Large-scale forcing: v-wind at boundaries |
| `ls_forcing_left_qv` | (time, z) | Large-scale forcing: specific humidity |
| `surface_forcing_surface_pressure` | (time) | Surface pressure [Pa] |

---

## PALM Output File Structure

### Output file naming

| Pattern | Content |
|---|---|
| `<case>_xy.nc` | 2D horizontal cross-section data |
| `<case>_xy_av.nc` | Time-averaged 2D horizontal data |
| `<case>_xz.nc` | 2D vertical cross-section (xz plane) |
| `<case>_yz.nc` | 2D vertical cross-section (yz plane) |
| `<case>_3d.nc` | 3D volume data |
| `<case>_3d_av.nc` | Time-averaged 3D volume data |
| `<case>_pr.nc` | Vertical profiles |
| `<case>_ts.nc` | Time series |

### Bio-met output variables

All biometeorology outputs are 2D (xy cross-section at ~1.1m above ground).

| Variable name | Description | Unit |
|---|---|---|
| `bio_mrt` | Mean Radiant Temperature (3D field) | degree_C |
| `bio_mrt*` | MRT at bio-met height (2D) | degree_C |
| `bio_pet*` | PET (instantaneous inputs) | degree_C |
| `bio_pet*_av` | PET (time-averaged inputs) | degree_C |
| `bio_utci*` | UTCI (instantaneous inputs) | degree_C |
| `bio_utci*_av` | UTCI (time-averaged inputs) | degree_C |
| `bio_perct*` | Perceived Temperature (PT) | degree_C |
| `bio_perct*_av` | PT (time-averaged inputs) | degree_C |

The `*` in variable names is literal — it is part of PALM's naming convention for 2D cross-section output.

### Standard meteorological output variables we need

| Variable | PALM name | Description |
|---|---|---|
| Potential temperature | `theta` | In Kelvin. Convert to Celsius: T_air = theta * (p/p0)^(R/cp) - 273.15 |
| u-wind | `u` | Wind component in x-direction [m/s] |
| v-wind | `v` | Wind component in y-direction [m/s] |
| w-wind | `w` | Vertical wind [m/s] |
| Wind speed | Computed: sqrt(u^2 + v^2) | Horizontal wind speed at given height |
| Surface temperature | `t_surface*` | [K] or [degree_C] depending on output config |

---

## Version Pinning Strategy

1. Pin to a specific PALM release (e.g., v23.10) for our product.
2. Test against that version's `urban_environment` case as our reference.
3. Namelist templates are version-specific (store in `translation/templates/v23.10/`).
4. When upgrading PALM version: create new template set, run reference case, verify output, then switch.
5. Report metadata always includes PALM version used.
