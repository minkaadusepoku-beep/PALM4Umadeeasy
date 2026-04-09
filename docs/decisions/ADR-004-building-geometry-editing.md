# ADR-004: Building Geometry Editing

**Status:** Accepted
**Date:** 2026-04-08
**Accepted:** 2026-04-09
**Author:** Minka Aduse-Poku
**Unblocks:** Implementation item 3.13

## Context

Phase 3 of the implementation plan calls for an in-tool building geometry
editor: users should be able to add, remove, and modify buildings inside
their PALM4Umadeeasy projects so they can run "what-if" scenarios such as
removing a building, raising its height, or proposing a new development
on a vacant lot.

The Phase 3 review explicitly required this ADR before any code is
written, because building geometry sits at a sensitive intersection:

1. It is the **dominant control** on local microclimate (wind shadowing,
   shading, channelling, surface temperature). Editing it changes
   everything PALM produces. Errors here are not visually obvious to
   the user but can silently invalidate every result.
2. It is the **most expensive thing to validate**. A polygon that is
   geometrically valid in lat/lon may still be invalid for PALM (too
   small for the grid, overlapping a building, hanging in the air,
   inside terrain, etc.).
3. It must remain **traceable**: every PALM run must be reproducible
   from a saved scenario, and that scenario must record every edit so
   that two runs of the "same" scenario cannot diverge.
4. It interacts with the **provenance/quality tier** model already in
   place. A scenario whose buildings were hand-edited is no longer a
   pure OSM-derived scenario and the data quality tier must reflect
   that.

This ADR fixes the data model, the editing primitives, the validation
contract, the persistence story, and the relationship between edits
and PALM's static driver. It does not specify UI styling.

## Decision

### 1. Storage format: GeoJSON FeatureCollection in scenario JSON

Edited building geometry lives **inside the scenario JSON document**,
not in a separate table, not in a separate file. The scenario already
fully specifies a PALM run; building edits are part of that
specification and must travel with it.

Concretely, the `Scenario` model gains an optional field:

```json
{
  "buildings_edits": {
    "base_source": "osm",
    "base_snapshot_id": "osm-2026-04-01",
    "edits": [
      {
        "id": "e1",
        "op": "add",
        "geometry": { "type": "Polygon", "coordinates": [...] },
        "height_m": 18.0,
        "roof_type": "flat",
        "wall_material_id": "concrete",
        "created_at": "2026-04-08T10:00:00Z",
        "created_by": 7
      },
      {
        "id": "e2",
        "op": "modify",
        "target_building_id": "osm:way/123456789",
        "set": { "height_m": 24.0 }
      },
      {
        "id": "e3",
        "op": "remove",
        "target_building_id": "osm:way/987654321"
      }
    ]
  }
}
```

**Rationale:**
- **Reproducibility**: re-running a scenario re-applies the same edits
  to the same base snapshot. No "live" coupling to the OSM tile that
  was current at run time.
- **Diff-friendly**: edits are an ordered, named list. Two scenarios
  can be compared edit-by-edit.
- **Portable**: a scenario JSON exported from one project can be
  imported into another and re-run identically, provided the same base
  snapshot is available.
- **Audit-friendly**: each edit carries `created_at` and `created_by`,
  giving us a per-feature audit trail without a separate table.

### 2. Coordinate system: WGS84 in storage, projected for editing and PALM

All persisted geometry is **WGS84 (EPSG:4326)** GeoJSON. This is the
universal interchange format and matches OSM, MapLibre, and the rest
of the stack.

For editing operations (snapping, validation of metric distances,
overlap checks) and for translation into PALM's static driver, the
backend reprojects to a **local metric CRS** (UTM zone of the project
centroid). All metric thresholds (minimum building footprint, edge
length, separation distance) are evaluated in the projected CRS.

We do **not** store projected coordinates. The single source of truth
is WGS84.

### 3. Editing primitives (v1 scope)

Three operations only:

| op | What it does | Required fields |
|---|---|---|
| `add` | Insert a new building polygon. | `geometry`, `height_m`, `roof_type` |
| `modify` | Change attributes of an existing building (from base or from a previous `add`). | `target_building_id`, `set` |
| `remove` | Delete an existing building. | `target_building_id` |

**Out of scope for v1** (and explicitly *deferred*, not forgotten):
- multi-polygon buildings,
- per-floor edits,
- holes / courtyards in polygons,
- pitched-roof shape parameters beyond a `roof_type` enum,
- attached/articulated facade elements,
- merging or splitting buildings.

These are listed in §8 so we do not silently grow the scope.

### 4. Validation contract (server-side, blocking)

Every edit must pass **all** of the following before it is accepted by
the backend. There is no "warn and accept" path for any of these:

1. **Geometry well-formedness**: valid GeoJSON Polygon, no
   self-intersection, ≥4 coordinates, closed ring, CCW outer ring.
2. **Footprint area in local CRS** ≥ `min_building_area_m2`
   (default 9 m², i.e. 3×3, well above the dx=2m grid).
3. **Minimum edge length** in local CRS ≥ `2 * dx` of the configured
   PALM grid. Edges shorter than two cells cannot be resolved and
   produce stair-step artefacts that look like data but are not.
4. **Height** in `[2.0, 300.0]` metres, with a soft warning above 80 m.
5. **Inside the project domain bounding box**, with a margin of one
   PALM ghost-cell layer. Edits hanging off the simulation edge are
   rejected.
6. **No overlap** with another building (base or edited) after all
   prior edits have been applied. Overlap is computed in the local
   metric CRS with a 0.5 m tolerance.
7. **Reference integrity**: `modify` and `remove` must target a
   building that exists in the snapshot view (= base buildings minus
   prior `remove`s, plus prior `add`s). Targeting a non-existent or
   already-removed id is a hard error.
8. **Edit log determinism**: edits are applied in list order. Re-ordering
   the list is a different scenario and must be saved as such.

These rules live in `backend/src/validation/buildings.py` and have
their own dedicated test suite. They run on every save, not only on
job submission.

### 5. PALM coupling: edits become part of the static driver

At PALM-job-creation time, the executor performs the following
deterministic pipeline:

1. Load `base_snapshot_id` building footprints.
2. Apply each edit in `buildings_edits.edits` in order, producing a
   final building set.
3. Re-run the validation contract against the final set as a
   defence-in-depth check.
4. Rasterise to the PALM static driver:
   - `building_id_2d`: integer ID per cell where a building exists.
   - `building_height_2d`: float metres per cell.
   - `building_type_2d`: PALM building-type integer derived from
     `roof_type` + `wall_material_id` + epoch heuristic.
5. Write the static driver NetCDF file consumed by PALM.

The rasterisation step is the **only** place that crosses the boundary
between vector edits and PALM grid cells. Any future change to the
PALM building model lives in this single function and nowhere else.

### 6. Provenance / data-quality tier coupling

A scenario that contains any edit at all is no longer a pure OSM
scenario. We therefore **downgrade the buildings data quality tier** as
follows:

| Number / nature of edits | Effect on `buildings.quality_tier` |
|---|---|
| 0 edits | unchanged (whatever the base source declares) |
| ≥1 edit, any op | tier is at most `PROFESSIONAL`, never `AUTHORITATIVE` |
| ≥1 `add` of a building > 30 m or > 1000 m² footprint | tier is at most `SCREENING` |

The validation engine surfaces this in the existing data-quality
warnings panel. Reports must show the edit count and the resulting
tier in the methodology section.

### 7. API surface (v1)

All routes are scenario-scoped. There is no global "buildings" API.

```
GET    /api/projects/{pid}/scenarios/{sid}/buildings
       Returns the resolved building set (base + applied edits).

POST   /api/projects/{pid}/scenarios/{sid}/buildings/edits
       Body: { op, geometry?, target_building_id?, set? }
       Validates and appends a single edit. Returns the new edit
       and the updated resolved set summary.

DELETE /api/projects/{pid}/scenarios/{sid}/buildings/edits/{edit_id}
       Removes an edit from the list. Re-validates the remaining
       edit chain (a later edit may have depended on this one).

POST   /api/projects/{pid}/scenarios/{sid}/buildings/edits:reorder
       Body: { ordered_ids: [...] }
       Reorders edits and re-validates the chain.
```

RBAC: editor or owner role required for all mutating routes; viewer
may GET. All mutations write to the audit log
(`resource_type="scenario_buildings"`).

The existing `POST .../scenarios/{sid}/validate` endpoint is extended
to call `validate_buildings_edits` as part of its check pass.

### 8. Out-of-scope features (deferred, not forgotten)

These are deliberately not in v1. Each is a non-trivial design
question on its own and earned its own bullet so we do not lose them:

- multi-polygon and donut (with-holes) buildings,
- per-floor / per-storey edits,
- pitched-roof geometry beyond `roof_type` enum,
- balconies, awnings, and other non-bulk facade elements,
- merging or splitting buildings,
- editing `building_type` directly (currently derived),
- bulk import of edited geometry from CAD/IFC,
- importing 3D city models (CityGML LoD2+),
- collaborative simultaneous editing (last-write-wins for v1).

### 9. Testing strategy

The validation contract is tested in isolation from the API. Every
rule in §4 gets at least one positive and one negative test.

The PALM coupling (§5) is tested with a deterministic stub
rasteriser: a fixed input snapshot + fixed edit list must produce the
exact same `building_height_2d` array, byte-for-byte. This is the
regression test that protects scientific reproducibility.

The provenance downgrade (§6) is tested by asserting the tier of a
scenario before and after each kind of edit.

## Consequences

**Positive**
- Scenarios are fully self-contained and reproducible across machines
  and time.
- Validation is centralised and total (no soft-fail paths).
- Provenance honesty: a hand-edited scenario can never be reported as
  if it were authoritative source data.
- PALM coupling lives in one function, not scattered across the code.

**Negative**
- A scenario JSON document grows linearly with the number of edits.
  We accept this. If a scenario accumulates >1000 edits it almost
  certainly should be a fresh base snapshot instead.
- Re-projecting on every validation call is CPU work. For v1 this is
  fine; if it becomes hot we cache the projected polygons inside the
  request.
- The "edits as ordered list" model means that re-ordering changes
  the result. We make this explicit by requiring an explicit reorder
  endpoint and re-validation; we do not silently re-sort.

**Migration / schema impact**
- No database table is added. The `Scenario` JSON column already
  stores arbitrary content; the new field is additive and backward
  compatible (scenarios without `buildings_edits` resolve to the base
  snapshot exactly as today).
- A PALM static-driver writer module is new code; no migration.

## Open questions for review

1. Is `min_building_area_m2 = 9` the right default, or do we want to
   lift it to match the typical municipal building cadastre (~25 m²)?
2. For the 0.5 m overlap tolerance: do we want this configurable per
   project, or is one global value enough?
3. Should `add` operations require a `wall_material_id` from the
   surface catalogue, or is "use the project default" acceptable in
   v1? Current ADR says required; this can be relaxed.
4. The provenance downgrade table in §6 — are the thresholds (30 m,
   1000 m²) the right ones, or should they come from the building
   data quality module?

These are not blockers for accepting the ADR; they are flagged for
the implementation PR review.

## 11. Resolutions at acceptance (2026-04-09)

The four open questions in §10 are resolved as follows for v1. Any
future revision must update this ADR rather than silently changing
the validator constants.

1. **`min_building_area_m2 = 9`** — kept as proposed. This is the
   smallest footprint that can be resolved on a 2 m grid without
   degenerate single-cell buildings; raising it to municipal-cadastre
   levels (~25 m²) would silently reject valid small structures
   (kiosks, gatehouses, garden buildings) that genuinely affect
   pedestrian-level wind. We accept the lower bar and rely on the
   provenance downgrade in §6 to flag heavily edited scenarios.
2. **Overlap tolerance** — single global value of `0.5 m` for v1. No
   per-project override. Rationale: the tolerance exists to absorb
   GeoJSON rounding noise, not to express a domain preference, so it
   does not belong in user-facing config.
3. **`add` requires `wall_material_id`** — kept strict. An added
   building with no declared wall material would silently inherit the
   project default and produce a result the user did not consciously
   choose. Forcing the explicit choice is the more scientifically
   honest default and matches the spirit of ADR-000.
4. **Provenance thresholds (30 m, 1000 m²)** — kept as proposed for
   v1. These are the thresholds at which an added building stops
   being a "small infill edit" and starts being a structure that
   dominates its block's microclimate. If the building data quality
   module later publishes its own thresholds, this ADR will be
   superseded on this point only.

## References

- ADR-000: Project principles (scientific honesty, reproducibility)
- ADR-001: PALM environment
- ADR-002: PALM-CSD reuse
- PALM static driver documentation:
  https://palm.muk.uni-hannover.de/trac/wiki/doc/app/iofiles/pids/static
- OpenStreetMap building tagging:
  https://wiki.openstreetmap.org/wiki/Key:building
- GeoJSON RFC 7946: https://datatracker.ietf.org/doc/html/rfc7946
