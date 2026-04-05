# ADR-003: Biometeorology Output Height Convention

**Status:** Accepted
**Date:** 2026-03-28
**Author:** Minka Aduse-Poku

## Context

PALM's biometeorology module computes thermal comfort indices (PET, UTCI, MRT) at a specific height above ground level. Our product must display and report these values with an accurate height label. The implementation plan (v3.0) flagged that the commonly cited "1.4m" may be incorrect and required this to be resolved in Phase 0.

## Findings

### PALM bio-met module: 1.1m above ground (hardcoded)

The PALM biometeorology module (`biometeorology_mod.f90`) targets **1.1m above ground level**, representing the gravimetric center of a standard standing person.

From the source code (`bio_init` subroutine):

```fortran
bio_cell_level = INT( 1.099_wp / dz(1) )
bio_output_height = 0.5_wp * dz(1) + bio_cell_level * dz(1)
```

The module finds the **vertical grid cell center closest to 1.1m**. The actual output height depends on vertical grid spacing:
- dz = 1m: output at cell center 1.5m (cell level 1)
- dz = 2m: output at cell center 1.0m (cell level 0)
- dz = 5m: output at cell center 2.5m (cell level 0)
- dz = 10m: output at cell center 5.0m (cell level 0)

### This height is NOT configurable

The `&biometeorology_parameters` namelist has only two parameters:
- `switch_off_module` (logical)
- `thermal_comfort` (logical)

There is no `bio_agent_height` or equivalent. The 1.1m target is hardcoded.

### Why 1.1m, not 1.4m

| Height | Convention | Used by |
|---|---|---|
| **1.1m** | VDI 3787 Blatt 2: gravimetric center of a standing reference person. Standard for German biometeorology. | PALM, RayMan, VDI standards |
| **1.4m** | WMO standard sensor height for air temperature measurement at weather stations. | Meteorological observations |

The 1.4m value often seen in biometeorology literature refers to the **measurement height** of input meteorological data (weather station observations), not the **reference height** for thermal comfort assessment. PALM's bio-met module correctly uses the VDI 3787 standard of 1.1m.

### Implications for grid resolution

For our target configurations:

| Grid resolution (dz) | Actual bio-met output height | Deviation from 1.1m |
|---|---|---|
| 1m | 1.5m | +0.4m |
| 2m | 1.0m | -0.1m |
| 5m | 2.5m | +1.4m |
| 10m | 5.0m | +3.9m |

At 10m vertical resolution, the bio-met output is at 5m — far from pedestrian level. This means **our recommended minimum vertical grid spacing near the ground should be 2m or finer** for credible pedestrian-level comfort results. PALM supports vertical grid stretching (fine near ground, coarser aloft), which we should configure by default.

## Decision

### Height convention for PALM4Umadeeasy

1. **We report the PALM bio-met output height as "approximately 1.1m above ground level (pedestrian height, per VDI 3787 Blatt 2)."** This is the target height. The actual output height depends on grid resolution.

2. **We do NOT claim the output is at 1.4m.** This would be inaccurate.

3. **Every result map, report, and export includes the actual output height** based on the configured vertical grid spacing. Example: "Thermal comfort computed at 1.5m above ground level (nearest grid cell center to the VDI 3787 reference height of 1.1m, at dz=1m vertical resolution)."

4. **Our default vertical grid configuration uses dz=2m near the ground** (with stretching above 50m). This gives an actual bio-met output height of 1.0m — close to the VDI target.

5. **We enforce a validation rule:** if the configured vertical grid spacing would place the bio-met output above 2.5m, the validation engine issues a **warning**: "Vertical grid spacing of {dz}m places the thermal comfort output at {actual_height}m above ground. For pedestrian-level assessment, a vertical spacing of 2m or finer near the ground is recommended."

6. **Our own post-processing PET/UTCI computation** (from raw PALM theta, MRT, wind, humidity) will also target the same grid cell as PALM's bio-met module. We do NOT interpolate to a different height unless explicitly justified and documented.

### Why not compute our own PET at exactly 1.1m?

PALM's bio-met module already computes PET and UTCI internally using consistent input variables (theta, MRT, wind at the same grid cell). Computing PET ourselves from PALM output variables introduces risk of inconsistency — we'd need to interpolate each variable to 1.1m independently, which may not match PALM's internal computation. We should use PALM's `bio_pet*` output directly when available.

Our own PET computation (pythermalcomfort) serves as:
- A **validation check** against PALM's internal computation
- A **fallback** if PALM's bio-met module is not enabled or produces unexpected values
- A path for computing comfort indices that PALM doesn't provide natively

## Consequences

1. All result labels, legends, reports, and documentation use the correct height.
2. Default vertical grid configuration ensures bio-met output is near pedestrian level.
3. Validation engine warns if grid spacing would produce misleading height placement.
4. Methodology document explains the height convention and its dependence on grid resolution.

## References

- PALM biometeorology module source: `biometeorology_mod.f90`, `bio_init` subroutine
- PALM bio-met documentation: https://palm.muk.uni-hannover.de/trac/wiki/doc/tec/biomet
- PALM bio-met output docs: https://palm.muk.uni-hannover.de/trac/wiki/doc/tec/biomet/output
- Froehlich & Matzarakis (2020): "Calculating human thermal comfort and thermal stress in the PALM model system 6.0", GMD
- VDI 3787 Blatt 2: Environmental meteorology — Methods for human-biometeorological evaluation
- Hoeppe (1999): "The physiological equivalent temperature", Int J Biometeorol
