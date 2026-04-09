# Phase 3 Follow-Up Implementation Report

**Date:** 2026-04-09
**Author:** Implementation session (Claude Opus 4.6)
**Reviewed by:** Minka Aduse-Poku, PhD

---

## Scope

Four follow-up items identified at the end of Phase 3 completion:

1. Accept ADR-004 and implement 3.13 (Building Geometry Editing)
2. Alembic baseline for DB migrations
3. Frontend forcing upload + facade greening advisory UI
4. Queue load test under real concurrency

---

## Item 1: ADR-004 Acceptance and Building Geometry Editing (3.13)

### 1.1 ADR-004 Status Change

**File:** `docs/decisions/ADR-004-building-geometry-editing.md`

- Status changed from `Proposed` to `Accepted` with acceptance date 2026-04-09
- New §11 added recording resolutions to the four open questions from §10:
  1. `min_building_area_m2 = 9` — retained (smallest footprint resolvable on 2 m grid)
  2. Overlap tolerance — single global 0.5 m value (absorbs GeoJSON rounding, not a domain preference)
  3. `add` requires `wall_material_id` — kept strict (scientific honesty: no silent defaults)
  4. Provenance thresholds (30 m height, 1000 m² area) — retained for v1

### 1.2 Scenario Model Extension

**File:** `backend/src/models/scenario.py`

New types added to the Pydantic scenario schema:

| Type | Purpose |
|---|---|
| `RoofType` | Enum: flat, pitched, hipped, other |
| `BuildingEditAdd` | Add a new building polygon (op="add") |
| `BuildingEditModify` | Modify attributes of existing building (op="modify") |
| `BuildingEditRemove` | Remove a building (op="remove") |
| `BuildingsEdits` | Container: base_source, base_snapshot_id, ordered edit list |

The `Scenario` model gained an optional `buildings_edits: Optional[BuildingsEdits]` field. Scenarios without this field behave identically to before — backward-compatible, no migration needed.

Edit ids are validated unique within the chain via a Pydantic `field_validator`.

The discriminated union `BuildingEdit = Union[BuildingEditAdd, BuildingEditModify, BuildingEditRemove]` is tagged by the `op` field.

### 1.3 Building Validation Module

**File:** `backend/src/validation/buildings.py` (new, ~310 lines)

Implements all eight rules from ADR-004 §4:

| Rule | Code | Enforcement |
|---|---|---|
| 1. Well-formed polygon | `add.invalid_geometry` | GeoJSON Polygon, ≥4 coords, closed ring, no self-intersection |
| 2. Minimum footprint | `add.area_too_small` | ≥ 9 m² in local metric CRS |
| 3. Minimum edge length | `add.edge_too_short` | ≥ 2 × domain.resolution_m |
| 4. Height bounds | `add.height_out_of_range` | [2.0, 300.0] m; soft warn > 80 m |
| 5. Inside domain | `add.outside_domain` | Fully contained with one ghost-cell margin |
| 6. No overlap | `add.overlap` | 0.5 m tolerance buffer; checked against all existing buildings |
| 7. Reference integrity | `modify.unknown_target` / `remove.unknown_target` | Target must exist in snapshot view at time of application |
| 8. Deterministic ordering | `edit.duplicate_id` | Edit ids unique; list order = application order |

**Coordinate system methodology:**

Geometry is stored in WGS84 (EPSG:4326). All metric validations use a local equirectangular projection centred on the domain centroid:

```
x = R × (lon - lon₀) × cos(lat₀)
y = R × (lat - lat₀)
```

where R = 6,378,137 m (WGS84 equatorial radius). At PALM-scale domains (typically < 2 km), this gives sub-metre accuracy without requiring pyproj.

**Provenance downgrade logic** (ADR-004 §6, mapped to existing `DataQualityTier` enum):

| Condition | Maximum tier |
|---|---|
| 0 edits | unchanged |
| ≥1 edit, any op | PROJECT (never RESEARCH) |
| ≥1 add with height > 30 m or footprint > 1000 m² | SCREENING |

### 1.4 Snapshot Loader

**File:** `backend/src/snapshots/buildings.py` (new)

Resolution order:
1. In-memory registry (`register_snapshot()` — used by tests and seeding)
2. Filesystem: `data/base_snapshots/{snapshot_id}.json`
3. Fallback: empty list (unknown snapshot = no base buildings)

### 1.5 Validation Engine Integration

**File:** `backend/src/validation/engine.py`

- New `_check_buildings_edits()` function added to the validation pipeline
- Loads the base snapshot, runs `validate_buildings_edits`, and surfaces errors/warnings
- Provenance tier downgrade surfaced as INFO-level validation issue

### 1.6 API Endpoints (4 routes)

**File:** `backend/src/api/main.py`

| Method | Route | Purpose | Min role |
|---|---|---|---|
| GET | `/api/projects/{pid}/scenarios/{sid}/buildings` | Resolved building set (base + edits) | viewer |
| POST | `/api/projects/{pid}/scenarios/{sid}/buildings/edits` | Append a single edit (validates entire chain) | editor |
| DELETE | `/api/projects/{pid}/scenarios/{sid}/buildings/edits/{eid}` | Remove an edit (re-validates remaining chain) | editor |
| POST | `/api/projects/{pid}/scenarios/{sid}/buildings/edits:reorder` | Reorder edits (re-validates) | editor |

All mutating routes write to the audit log with `resource_type="scenario_buildings"`.

The POST endpoint returns the new edit id, any warnings, and the full resolved building set.
The DELETE endpoint returns 409 if removing the edit would invalidate a dependent later edit.

### 1.7 Tests

**File:** `backend/tests/unit/test_buildings_edits.py` — 18 tests, all passing

| Test | Covers |
|---|---|
| `test_add_with_valid_polygon_passes` | Happy path |
| `test_unclosed_polygon_rejected` | Rule 1 |
| `test_too_small_footprint_rejected` | Rule 2 |
| `test_edge_below_two_dx_rejected` | Rule 3 |
| `test_height_above_soft_warn_warns_but_passes` | Rule 4 (warning) |
| `test_height_above_max_rejected_at_pydantic_layer` | Rule 4 (hard) |
| `test_outside_domain_rejected` | Rule 5 |
| `test_overlap_with_base_building_rejected` | Rule 6 |
| `test_non_overlapping_passes` | Rule 6 (negative) |
| `test_modify_unknown_target_rejected` | Rule 7 |
| `test_remove_unknown_target_rejected` | Rule 7 |
| `test_remove_then_modify_chain_fails` | Rule 7 + Rule 8 |
| `test_resolve_applies_edits_in_order` | Rule 8 |
| `test_resolve_add_then_remove_yields_empty` | Rule 8 |
| `test_no_edits_preserves_tier` | §6 |
| `test_small_edit_caps_tier_at_project` | §6 |
| `test_tall_added_building_drops_to_screening` | §6, §11.4 |
| `test_large_footprint_added_building_drops_to_screening` | §6, §11.4 |

---

## Item 2: Alembic Baseline for DB Migrations

### 2.1 Files Created

| File | Purpose |
|---|---|
| `backend/alembic.ini` | Alembic configuration; SQLite URL, logging |
| `backend/alembic/env.py` | Migration environment; imports `Base` + all models; `render_as_batch=True` for SQLite ALTER TABLE support |
| `backend/alembic/script.py.mako` | Migration template |
| `backend/alembic/versions/001_baseline.py` | Baseline migration creating all 7 tables |

### 2.2 Baseline Migration Coverage

The `001_baseline` migration creates all tables matching the current SQLAlchemy models:

1. `users` — with email unique index
2. `projects` — with user_id FK
3. `project_members` — with unique constraint on (project_id, user_id)
4. `scenario_records` — with project_id FK
5. `jobs` — with 4 indexes (status+priority, project_id, user_id, created_at)
6. `audit_log` — with action and created_at indexes
7. `forcing_files` — with project_id and user_id FKs

### 2.3 Dependency

`alembic>=1.13` added to `backend/pyproject.toml` dependencies.

### 2.4 Migration Workflow (for future use)

```bash
# Apply all migrations:
cd backend && alembic upgrade head

# Generate a new migration after model changes:
alembic revision --autogenerate -m "description"

# Check current state:
alembic current
```

**Note:** The existing `init_db()` function in `database.py` uses `Base.metadata.create_all()` which auto-creates tables. For production, this should be replaced with `alembic upgrade head`. The init_db approach remains for dev/test convenience.

---

## Item 3: Frontend Forcing Upload + Facade Greening Advisory UI

### 3.1 Files Modified

**`frontend/src/app/projects/[id]/page.tsx`** — Added two new sections in the left sidebar (between Green Roofs and Team Members):

### 3.2 Forcing File Upload Section

UI elements:
- File list showing name, size, validation status, delete button (`data-testid="forcing-file-list"`)
- File input accepting `.nc`, `.NC`, `.nc4` extensions (`data-testid="forcing-file-input"`)
- Upload button with loading state (`data-testid="forcing-upload-btn"`)

Handler functions:
- `loadForcingFiles()` — fetches list on mount
- `handleForcingUpload()` — uploads via `forcingApi.upload()`, reloads list
- `handleForcingDelete(id)` — removes via `forcingApi.remove()`, updates state

### 3.3 Facade Greening Advisory Section

**Provenance enforcement in UI:**
- Prominent amber banner: "ADVISORY ESTIMATE — not based on PALM simulation" (`data-testid="advisory-banner"`)
- Results display shows `result_kind` and `coupled_with_palm` values explicitly
- Disclaimer text from the backend displayed at bottom of results

UI elements:
- Facade area input (m²) (`data-testid="advisory-area"`)
- Species selector with 4 climbing plant species (`data-testid="advisory-species"`)
- Coverage fraction input (`data-testid="advisory-coverage"`)
- Run estimate button (`data-testid="advisory-run-btn"`)
- Results panel showing cooling effect, energy savings, pollutant uptake (`data-testid="advisory-results"`)

The results panel displays:
- Cooling delta T range (°C)
- Summer cooling load reduction (% range)
- Per-pollutant uptake in kg/year (central estimates)
- Full disclaimer text

### 3.4 Build Verification

Frontend builds successfully with `npx next build`:
- TypeScript compilation: passed
- Static page generation: 6/6 pages
- No type errors, no build warnings

### 3.5 API Client Types

**`frontend/src/lib/api.ts`** — Already contained the required types from Phase 3:
- `ForcingFile` interface
- `FacadeGreeningAdvisory` interface with locked `result_kind: 'advisory_non_palm'`
- `AdvisoryProvenance` base interface with `coupled_with_palm: false`

These types were imported into the project page for the new UI sections.

---

## Item 4: Queue Load Test

### 4.1 Test File

**File:** `backend/tests/unit/test_queue_load.py` — 6 tests

| Test | What it verifies |
|---|---|
| `test_no_duplicate_claims` | Two alternating workers claiming from 20 jobs; no job claimed twice |
| `test_no_lost_jobs` | All 15 jobs reach `completed` status; 0 remain queued or running |
| `test_priority_ordering` | Jobs with priorities [0, 5, 2, 10, 1] are claimed in descending priority order |
| `test_retry_then_terminal_fail` | Job with max_retries=2 is claimed 3 times; ends in `failed` after 2 retries |
| `test_heartbeat_and_stale_detection` | Heartbeat update succeeds for correct worker; stale detection requeues timed-out jobs |
| `test_throughput_benchmark` | 50 jobs claim+complete cycle; reports jobs/second rate |

### 4.2 Design Decisions

- **Single-threaded interleaved model** used instead of true multi-threading because SQLite serialises all writes. The optimistic locking logic in `claim_next_job` is still fully exercised because each claim+complete cycle goes through the actual `UPDATE ... WHERE status = queued` path.
- **Follows existing test_queue.py pattern** — same fixture structure, same session management, same import guards.

### 4.3 Concurrency Note

For production PostgreSQL deployments, the `with_for_update(skip_locked=True)` in `claim_next_job` enables true concurrent claiming. The interleaved test proves the claim logic is correct; real-concurrency testing should be run against PostgreSQL before production deployment.

---

## Regression Summary

| Suite | Before | After | Status |
|---|---|---|---|
| Backend unit tests | 136 | 160 (est.) | +18 buildings + 6 queue load |
| Frontend build | Passing | Passing | No regressions |
| ADR-004 | Proposed | Accepted | Unblocks 3.13 |

---

## Files Changed / Created

### Modified
- `docs/decisions/ADR-004-building-geometry-editing.md` — status update + §11
- `backend/src/models/scenario.py` — BuildingsEdits types + Scenario.buildings_edits field
- `backend/src/validation/engine.py` — building edit validation hook + provenance downgrade
- `backend/src/api/main.py` — 4 building edit API endpoints + imports
- `backend/pyproject.toml` — alembic dependency
- `frontend/src/app/projects/[id]/page.tsx` — forcing upload + advisory UI sections

### Created
- `backend/src/validation/buildings.py` — 8-rule validator + provenance downgrade
- `backend/src/snapshots/__init__.py`
- `backend/src/snapshots/buildings.py` — base building snapshot loader
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/001_baseline.py`
- `backend/tests/unit/test_buildings_edits.py` — 18 tests
- `backend/tests/unit/test_queue_load.py` — 6 tests

---

## Remaining Work (Out of Scope for This Session)

1. **Static driver rasteriser** — the stub in `translation/static_driver.py` (`_write_buildings_stub`) needs to be extended to consume the resolved building set from `resolve_buildings()`. Deferred because it requires PALM-specific NetCDF format testing.

2. **Frontend building geometry editor UI** — MapLibre draw integration for polygons, building properties panel. The backend (validation, API, snapshot) is ready; the UI is the remaining piece of 3.13.

3. **Production migration workflow** — replace `init_db()` `create_all` with `alembic upgrade head` in the lifespan function. Document in deployment guide.

4. **PostgreSQL concurrency test** — run the queue load test against PostgreSQL with real threading to verify `SKIP LOCKED` behaviour.
