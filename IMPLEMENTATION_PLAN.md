# PALM4Umadeeasy — Production Master Plan

**Version:** 3.0
**Date:** 2026-03-28
**Author:** Minka Aduse-Poku / Claude
**Status:** Draft for review and build authorization

---

## 0. Governing Product Statement

PALM4Umadeeasy is a consultant-grade decision-support platform for urban microclimate intervention testing.

It is not a generic browser wrapper for PALM. It is not a research configuration tool. It is not "PALM with a nicer face."

It is a specialized platform that answers one class of question with scientific defensibility:

> **"What happens to outdoor thermal comfort and wind conditions in this neighbourhood if we implement these specific green/blue infrastructure interventions — and how confident should we be in that answer?"**

The product is built around five capabilities that do not exist in PALM or any current PALM tooling:

1. **Intervention-centric workflow.** The user defines a planning question and edits interventions (trees, surfaces, green roofs, later façade greening, water features). The simulation is a means, not the point.
2. **First-class comparison engine.** Every result exists in relation to a baseline or alternative. Delta maps, ranked zone improvements, threshold impact analysis. Comparison is the default output, not an afterthought.
3. **Confidence-aware outputs.** Input data quality is tagged, propagated through the pipeline, and surfaced in every result and report. The user always knows how much to trust the answer.
4. **Consultant-grade reporting.** PDF reports with professional maps, defensible methodology notes, comparison tables, plain-language summaries, and honest limitations — ready for a municipal committee or funding application without manual rework.
5. **Interpretation and constraint layer.** The product guides users toward valid configurations, blocks physically impossible ones, and translates results into planning-relevant language. It does not expose raw PALM complexity.

The finished product covers thermal comfort (PET, UTCI), wind comfort (Lawson criteria), shading, surface temperature, and — in later phases — pollutant dispersion and energy balance. The core domain is green and blue infrastructure planning in urban areas: street trees, park design, green roofs, façade greening, surface de-sealing, water features, and shade structures.

---

## 1. Positioning Against Existing PALM-4U Tooling

### 1.1 What PALM-4U GUI Already Provides

The PALM-4U ecosystem, developed primarily through the BMBF-funded UC² programme, already includes:

- **Browser-based GUI** for domain setup, model configuration, and job submission
- **Automated simulation workflows** including cloud/HPC job handling
- **Static driver creation** from geodata (buildings, terrain, vegetation) via palm_csd
- **Result viewing** with basic map visualization of PALM outputs
- **User and data management** with project organization
- **Import/export interfaces** for geodata and configurations
- **Standard application-field workflows** for common urban climate assessments

This is functional, maintained, and used by research groups. We do not claim to be "the first browser-based PALM tool." That claim would be false.

### 1.2 Where PALM4Umadeeasy Is Superior

| Dimension | Existing PALM-4U GUI | PALM4Umadeeasy |
|---|---|---|
| **Workflow model** | Simulation-centric: "configure a run, submit it, view output." User must understand PALM concepts. | Intervention-centric: "define your planning question, test your measures, compare options." PALM concepts are hidden. |
| **Comparison** | Individual runs. User manually compares by opening outputs side-by-side. | Comparison is a first-class operation. Difference maps, delta statistics, ranked improvements generated automatically. |
| **Confidence** | No data quality tracking. All inputs treated equally. No uncertainty messaging. | Input data tagged by quality tier (screening/project/research). Confidence statements auto-generated per result. |
| **Reporting** | Scientific plots exportable. No structured reports. | Consultant-grade PDF with professional maps, legends, summaries, methodology notes, comparison tables, limitations. Ready for client delivery. |
| **Constraint** | Exposes most PALM parameters. User can create invalid or misleading configurations. | Constrained editor with validated defaults. Blocks physically impossible scenarios. Exposes only planning-relevant parameters. |
| **Interpretation** | Raw variable names and units. User interprets. | Comfort classifications (VDI 3787, Lawson), threshold exceedance analysis, plain-language summary text. |
| **Target user** | Atmospheric modellers, trained PALM users. | Urban planners, landscape architects, climate adaptation consultants. |

### 1.3 What We Do Not Claim

- We do not claim better physics. PALM is the physics engine in both cases.
- We do not claim broader model capability. The PALM-4U GUI exposes more PALM features. We deliberately constrain.
- We do not claim to replace the PALM-4U GUI for research use. Researchers who need full PALM control should use the existing tools.
- We claim a different product for a different user solving a different problem.

---

## 2. Commercial Entry Point

### 2.1 Sharpest Initial Positioning

The strongest first market entry is:

> **Quantified before/after comparison of tree planting and surface de-sealing measures for municipal heat adaptation plans and Bebauungsplan climate assessments.**

This is the sharpest entry because:

1. **Regulatory demand exists now.** German municipalities increasingly require climate impact assessments for new developments (Klimaanpassungsgesetz, Bebauungsplan environmental reports). Consultants need tools to produce these assessments efficiently.
2. **The comparison workflow is the core differentiator.** "Baseline vs. proposed development vs. mitigated development" is exactly the three-scenario comparison this product is built for.
3. **Tree planting is the simplest intervention to model correctly.** PALM's plant canopy model is mature. LAD profiles are available from literature. The translation layer is tractable.
4. **Surface de-sealing is the second-simplest.** Changing pavement type to grass/gravel requires only surface parameter changes in the static driver. No complex 3D geometry.
5. **The output maps directly to what the client needs.** "PET in the proposed courtyard exceeds the strong heat stress threshold for X hours. Adding the proposed 12 trees reduces this to Y hours." This is the sentence that goes into the Bebauungsplan environmental report.

### 2.2 First Paying Use Case

A consulting firm (or Minka's own Urban Climate Adaptation Studio) receives a commission to assess microclimate impact of a proposed residential development. The deliverable is a report with:

- Baseline thermal comfort assessment of the existing site
- Thermal comfort assessment of the proposed development (new buildings, changed surfaces)
- Thermal comfort assessment of the mitigated development (proposed buildings + compensatory tree planting + green roofs)
- Comparison: how much does the mitigation compensate for the development impact?
- Quantified statement suitable for the environmental report section of the Bebauungsplan

Today this requires a PALM expert spending days on manual configuration, post-processing, and report preparation. PALM4Umadeeasy reduces this to hours of guided interaction.

---

## 3. Full Capability Map

### 3.1 Finished Product Capabilities

**Domain & Data Management**
- Study area definition by map drawing (bounding box or polygon)
- Automatic geodata fetching: buildings (OSM/CityGML/LoD2), terrain (DEM), land use, existing vegetation
- Manual geodata upload: CityGML, GeoJSON, shapefiles, surveyed tree inventories
- Data quality tagging: screening-grade vs. project-grade vs. research-grade
- Project management: named projects, multiple scenarios per project, version history

**Scenario Editing**
- Tree placement/removal with species catalogue (20+ species with validated LAD profiles, height ranges, crown geometry)
- Vegetation patch creation (hedges, shrubs, ground cover) with type catalogue
- Surface material editing (paved, gravel, grass, water, bare soil, permeable paving)
- Green roof configuration (substrate depth, vegetation type)
- Green wall / façade greening configuration (climbing species, coverage, height)
- Building geometry editing: add/remove/modify buildings within the study area
- Street-level shade structures: pergolas, shade sails (simplified geometry)
- Water features: fountains, shallow pools, channels (simplified)

**Simulation Management**
- Scenario templates: "baseline," "single intervention," "multi-intervention," "concept comparison"
- Forcing selection: pre-validated meteorological archetypes plus custom forcing upload with validation
- Domain configuration with validated defaults (resolution, vertical grid)
- Resource estimation before run
- Job queue with priority, cancellation, restart
- Progress monitoring with meaningful status
- Batch runs: queue multiple scenarios for overnight execution

**Validation & Guardrails**
- Real-time element conflict detection
- Domain physics validation
- Forcing consistency checks
- Data quality impact warnings
- Resource limit enforcement

**Post-Processing & Results**
- Comfort indices: PET, UTCI (at minimum)
- Thermal comfort classification maps per VDI 3787
- Wind comfort analysis: Lawson criteria classification
- Shadow/shading maps
- Threshold exceedance maps
- Time-of-day animation
- Zonal statistics per user-defined or auto-detected zones
- Comparison engine: difference maps, delta statistics, ranked zone improvements
- Cross-section views

**Reporting & Export**
- Consultant-grade PDF report
- GeoTIFF, GeoJSON, shapefile export
- CSV/XLSX for statistics
- Presentation-quality PNG/SVG maps
- Raw NetCDF download for power users

**AI Assistant (Constrained)**
- Scenario guidance
- Parameter explanation
- Result interpretation (referencing actual computed values only)
- Report prose refinement (numbers unchanged)
- Validation error explanation

**Expert Overrides (Later Layer)**
- Namelist inspection and selective parameter editing
- Custom forcing upload
- Extended output variable selection
- Custom domain configuration
- Raw output access
- These are controlled features added after the core product is stable. They exist to serve consulting scientists who need to verify or extend the standard workflow, not to turn the product into a general PALM configurator.

**Administration**
- User accounts with role-based access
- Project sharing and permissions
- Backend monitoring dashboard
- Usage tracking

### 3.2 Phase 1 Capabilities (Foundational)

These are not a reduced scope. They are the capabilities without which the product's core value proposition cannot function:

- PALM compilation and execution automation
- Translation layer: scenario definition → valid PALM inputs via palm_csd backbone
- Post-processing pipeline: PALM output → comfort indices → classified maps → map tiles → statistics
- Validation engine: all physics and resource checks
- Comparison engine: two-scenario differencing with delta maps and statistics
- Confidence propagation: data quality tagging → result-level messaging
- Report generator: PDF with maps, summaries, methodology, confidence, limitations
- API layer: scenario CRUD, job management, result retrieval
- Map UI: study area definition, tree placement, surface editing, green roof toggle
- Result viewer: comfort maps with standard legends, time slider, comparison view

### 3.3 Capabilities Deferred by Sequencing

Every item below is part of the finished product. Deferral is due to implementation dependency, not reduced ambition.

| Capability | Depends on | Target phase |
|---|---|---|
| Green wall / façade greening | Translation layer + species catalogue infrastructure | Phase 3 |
| Building geometry editing | Static driver generation + 3D conflict detection | Phase 3 |
| Custom forcing upload | Forcing validation pipeline | Phase 3 |
| Wind comfort (Lawson criteria) | Wind field extraction from post-processing | Phase 3 |
| Expert overrides (namelist editing, raw output) | Stable core workflow that overrides augment, not replace | Phase 4 |
| Constrained AI assistant | Stable comparison + reporting that AI interprets, not generates | Phase 4 |
| Batch/overnight runs | Job queue + notification system | Phase 3 |
| Multi-user workspace | Auth + permissions + project sharing | Phase 3 |
| Vegetation patches (hedges, shrubs) | Extended catalogue + translation layer | Phase 4 |
| Shade structures (pergolas, sails) | 3D geometry in static driver | Phase 5+ |
| Water features | PALM water body parameterisation | Phase 5+ |
| Pollutant dispersion | PALM chemistry module integration | Phase 5+ |
| Nested domains | Multi-resolution PALM configuration + result stitching | Phase 5+ |

---

## 4. Foundation Spine

This is the non-negotiable backbone of the product. Every advanced feature attaches to it. If any element of the spine is unreliable, nothing built on top can be trusted.

### 4.1 Spine Components

```
┌─────────────────────────────────────────────────────────────┐
│                     FOUNDATION SPINE                         │
│                                                              │
│  ┌───────────────┐                                          │
│  │ 1. Scenario   │  Deterministic JSON schema.              │
│  │    Schema     │  Given same inputs → same document.       │
│  │               │  Versioned. Pydantic-validated.           │
│  └───────┬───────┘                                          │
│          ▼                                                   │
│  ┌───────────────┐                                          │
│  │ 2. Preprocess │  palm_csd backbone (default) +            │
│  │    / Static   │  our extensions for intervention          │
│  │    Driver     │  elements. Scenario → valid PALM inputs.  │
│  └───────┬───────┘                                          │
│          ▼                                                   │
│  ┌───────────────┐                                          │
│  │ 3. PALM       │  Deterministic job execution.             │
│  │    Runner     │  Submit, monitor, detect success/failure. │
│  │               │  No user-visible Linux interaction.       │
│  └───────┬───────┘                                          │
│          ▼                                                   │
│  ┌───────────────┐                                          │
│  │ 4. Post-      │  Variable extraction, comfort index       │
│  │    Processing │  computation, classification, map tiles.  │
│  │               │  Validated against reference outputs.     │
│  └───────┬───────┘                                          │
│          ▼                                                   │
│  ┌───────────────┐                                          │
│  │ 5. Comparison │  Scenario A vs B: difference grids,       │
│  │    Engine     │  delta statistics, ranked improvements,   │
│  │               │  threshold impact analysis.               │
│  └───────┬───────┘                                          │
│          ▼                                                   │
│  ┌───────────────┐                                          │
│  │ 6. Report     │  PDF generation with professional maps,   │
│  │    Engine     │  legends, summaries, comparison tables,   │
│  │               │  methodology, confidence, limitations.    │
│  └───────┬───────┘                                          │
│          ▼                                                   │
│  ┌───────────────┐                                          │
│  │ 7. Confidence │  Data quality tier → propagated through   │
│  │    Propagation│  every result, every map, every report.   │
│  │               │  Non-removable. Not user-suppressible.    │
│  └───────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Spine Properties

1. **Deterministic.** Given the same scenario JSON, catalogue version, and PALM version, the spine produces identical PALM inputs, identical post-processed outputs, and identical reports. No randomness. No ambient state.
2. **Testable end-to-end.** A CI pipeline can submit a scenario JSON and verify that the output GeoTIFF values, statistics, and report text match expected baselines.
3. **Versioned.** Every component of the spine (scenario schema, catalogues, namelist templates, post-processing rules, report templates, classification thresholds) is versioned. A result can always be traced to the exact configuration that produced it.
4. **Modular.** Advanced features (façade greening, wind comfort, AI assistant, expert overrides) attach to spine interfaces. They do not modify spine internals.

### 4.3 Spine Proof Requirement

The spine must be proven working — end-to-end, headless, without any frontend — before any advanced feature development begins. Phase 1 exists solely to prove the spine.

---

## 5. Build vs. Reuse Strategy

### 5.1 PALM Binary

**Decision: use as-is.** Compile from source. Do not modify PALM Fortran code. Pin to a specific release. Document exact compilation flags, dependencies, and versions.

### 5.2 palm_csd (Static Driver Creation)

**Default assumption: reuse and wrap palm_csd as the preprocessing backbone.**

palm_csd is the PALM project's own tool for generating static driver files (NetCDF) from geodata inputs (buildings, terrain, vegetation, surfaces). It handles:
- Rasterisation of building footprints and heights onto the PALM grid
- Terrain interpolation to grid
- Vegetation type mapping
- Pavement type mapping
- Basic tree representation

Our translation layer wraps palm_csd and extends it with:
- Our species catalogue (LAD profiles, crown geometry) mapped to palm_csd's vegetation parameters
- Our surface type catalogue mapped to palm_csd's pavement/land-use classification
- Our intervention-element logic (user-placed trees, surface changes, green roofs) merged into the geodata that palm_csd processes
- Our validation layer that checks inputs before palm_csd runs and outputs after

**Custom static driver generation from scratch is justified only if Phase 0 evaluation reveals a hard blocker:**
- palm_csd cannot handle our intervention-element workflow (e.g., cannot accept tree placements as point data merged with existing vegetation)
- palm_csd's output format is incompatible with our required PALM configuration
- palm_csd is unmaintained and has critical bugs with no fix path
- palm_csd's license is incompatible with our use

If a blocker is found, document it in an Architecture Decision Record (ADR) before proceeding with custom implementation. Even then, use palm_csd's logic as reference — do not start from zero.

### 5.3 palmpy

**Decision: evaluate in Phase 0, use selectively.** palmpy provides Python utilities for PALM I/O. Use where it saves time (e.g., NetCDF reading/writing). Do not depend on it for core translation logic. If unmaintained, our netCDF4/xarray code replaces it trivially.

### 5.4 PALM-4U GUI Code

**Decision: do not reuse any PALM-4U GUI code.** This is both a legal and a design decision.

- Legal: the PALM-4U GUI was developed under BMBF funding. License terms for code developed under public research funding in Germany vary. We must not use code whose license has not been explicitly reviewed and cleared.
- Design: the GUI has different UX goals (research simulation configuration vs. intervention-centric decision support). Reusing its components would import its interaction model.
- We may study published documentation, papers, and public API descriptions to understand data structures that have already been designed. We do not read, copy, or adapt source code.

### 5.5 Comfort Index Computation

**Decision: use established library.** pythermalcomfort (Center for the Built Environment) for PET, UTCI, SET*. Validate against reference computations (RayMan for PET, UTCI operational procedure spreadsheet). Do not reimplement from scratch.

### 5.6 Summary: Build from Scratch

| Component | Why custom |
|---|---|
| **Translation layer orchestrator** | Core IP. Maps intervention-oriented scenario to palm_csd inputs + namelist. Nothing like this exists. |
| **Scenario schema** | Novel: defines planning interventions, not PALM parameters. |
| **Validation engine** | Novel: physics-aware + planning-context-aware validation at the scenario level. |
| **Comparison engine** | Does not exist in any PALM tooling. Core differentiator. |
| **Report generator** | Does not exist. Consultant-grade, confidence-aware. |
| **Confidence propagation layer** | Does not exist. Data quality tier → result-level messaging. |
| **Frontend** | Must be built for decision-support UX. Cannot reuse research GUI. |
| **Species/surface catalogues** | Must be curated with validated PALM parameters and literature citations. |

---

## 6. Production Architecture

### 6.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    BROWSER (any OS)                               │
│                                                                   │
│  ┌───────────┐ ┌────────────┐ ┌───────────┐ ┌───────────────┐  │
│  │ Map Engine │ │ Scenario   │ │ Results   │ │ AI Assistant  │  │
│  │ (MapLibre  │ │ Editor     │ │ Viewer &  │ │ (constrained  │  │
│  │  GL JS)    │ │ (guided    │ │ Comparison│ │  chat, Ph.4)  │  │
│  │            │ │  forms +   │ │ Engine    │ │               │  │
│  │            │ │  map tools)│ │           │ │               │  │
│  └───────────┘ └────────────┘ └───────────┘ └───────────────┘  │
│                                                                   │
│                      Next.js / TypeScript                         │
│                      Zustand · Zod · MapLibre GL JS               │
└──────────────────────────┬────────────────────────────────────────┘
                           │ HTTPS + WebSocket (TLS)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                        API LAYER (FastAPI, Python)                │
│                                                                   │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ │
│  │ Auth    │ │ Scenario │ │ Job      │ │ Result │ │ AI Proxy │ │
│  │ (JWT)   │ │ CRUD +   │ │ Submit / │ │ Maps / │ │ (Claude  │ │
│  │         │ │ version  │ │ status / │ │ stats /│ │  tool-   │ │
│  │         │ │          │ │ cancel   │ │ export │ │  use)    │ │
│  └─────────┘ └──────────┘ └──────────┘ └────────┘ └──────────┘ │
│                                                                   │
│  Pydantic validation · rate limiting · audit logging              │
└──────────────────────────┬────────────────────────────────────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     ▼                     ▼                     ▼
┌──────────────┐  ┌───────────────┐  ┌───────────────────┐
│ Translation  │  │ Execution     │  │ Post-Processing   │
│ Layer        │  │ Layer         │  │ Layer             │
│              │  │               │  │                   │
│ Scenario →   │  │ Celery+Redis  │  │ NetCDF → comfort  │
│ palm_csd     │  │ job queue     │  │ indices → tiles   │
│ inputs →     │  │ PALM runner   │  │ → classification  │
│ namelist     │  │ (mpirun on    │  │ → statistics      │
│              │  │  Linux)       │  │ → comparison      │
│ Validation   │  │ Progress      │  │ → report          │
│ engine       │  │ monitor       │  │ → confidence      │
└──────────────┘  └───────────────┘  └───────────────────┘
```

### 6.2 Technology Choices

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend framework** | Next.js (App Router) + TypeScript | SSR for initial load, React ecosystem, strong typing |
| **Map** | MapLibre GL JS | Open-source, vector tiles, performant, good drawing tool ecosystem |
| **State management** | Zustand | Lightweight, no boilerplate, good for complex map state |
| **Validation (client)** | Zod | Shared schemas with backend (via code generation from Pydantic) |
| **Backend framework** | FastAPI (Python) | Async, Pydantic-native, auto OpenAPI docs. Python chosen because PALM ecosystem (palm_csd, palmpy, netCDF4, xarray, rasterio, pythermalcomfort) is Python. |
| **Database** | PostgreSQL + PostGIS | Spatial queries on project/scenario data. Mature. |
| **Job queue** | Celery + Redis | Proven for long-running scientific computation jobs. |
| **Object storage** | S3-compatible (MinIO self-hosted, S3 for cloud) | PALM input/output files, generated tiles, reports. |
| **PDF generation** | WeasyPrint (HTML/CSS → PDF) | Handles complex layouts, maps, tables. Template-driven. |
| **Map rendering (print)** | matplotlib + cartopy for static maps, or custom renderer | High-DPI publication-quality maps for PDF reports. |
| **Monitoring** | Prometheus + Grafana | Metrics, alerting, dashboards. |
| **Logging** | Structured JSON → Loki or ELK | Searchable, correlatable. |
| **Auth** | JWT with refresh tokens. OAuth2 for SSO later. | Standard, stateless. |

### 6.3 Data Storage Design

| Data type | Storage | Access pattern |
|---|---|---|
| Projects, scenarios (JSON), user accounts, job records, audit logs | PostgreSQL + PostGIS | CRUD, spatial queries, audit queries |
| PALM input files (namelists, static/dynamic drivers) | S3 object store | Write once per run, read for reproduction |
| PALM output files (NetCDF) | S3 object store | Write once, read by post-processing, download by power users |
| Generated map tiles | S3 or filesystem with CDN | Read-heavy, served to browser |
| Generated reports (PDF) | S3 object store | Read on demand |
| Species/surface catalogues | JSON files in repo, loaded at startup | Read-only at runtime, versioned in git |

### 6.4 Observability

- Application metrics: Prometheus. Request latency, error rates, job queue depth, active PALM runs, post-processing duration, storage usage.
- Alerting: Grafana alerts on job failure rate spike, queue backup, disk usage thresholds, PALM crash patterns.
- Health endpoints: `/health` (API), PALM server heartbeat, storage capacity check.
- Audit trail: every scenario edit, run submission, report generation, and data export logged with user, timestamp, action, and (for edits) JSON diff. Append-only. Retained for project lifetime.

### 6.5 Security

- JWT auth with refresh tokens. Passwords hashed with bcrypt/argon2.
- Role-based access: viewer, editor, admin. Project-level permissions.
- Input sanitisation: all user input through Pydantic models. No string interpolation into namelists or shell commands.
- File upload validation: CityGML/GeoJSON/shapefile parsed and validated before acceptance.
- PALM execution sandboxed: job runner accesses only the job directory. No user-controlled paths in shell commands.
- HTTPS everywhere. WebSocket over TLS.

### 6.6 Scaling Path

| Stage | Architecture | Capacity |
|---|---|---|
| **Single-server** | API + DB + PALM on one Linux machine. Docker Compose. | 1 concurrent PALM run. Suitable for solo consultant. |
| **Separated** | API on VM/container. PALM on dedicated compute server(s). Shared filesystem or S3. | Multiple PALM workers. Suitable for small team. |
| **Cloud-burst** | API on container service. PALM on on-demand HPC instances (AWS HPC6a, Azure HBv3). | Elastic. Suitable for SaaS. |
| **Multi-tenant** | Database-level project isolation. Per-tenant job quotas. | Production SaaS. |

---

## 7. Data Strategy

### 7.1 Data Quality Tiers

| Tier | Label | Sources | Typical accuracy |
|---|---|---|---|
| **Screening** | "Screening-grade (public data)" | OSM buildings (footprint + estimated height), SRTM/Copernicus DEM (30m), Corine/OSM land use, estimated tree canopy from remote sensing | Buildings: ±2m height, ±1m position. Terrain: ±5m. Vegetation: approximate. |
| **Project** | "Project-grade (verified data)" | Municipal CityGML LoD2, surveyed tree cadaster, official land-use plans, LiDAR DEM (1m) | Buildings: ±0.5m. Terrain: ±0.5m. Trees: individual positions and species known. |
| **Research** | "Research-grade (curated data)" | LiDAR point clouds with manual QA, measured tree LAD profiles, in-situ meteorological forcing, calibrated soil parameters | Highest available. Per-element validation against field data. |

### 7.2 How Data Quality Propagates

1. **Input tagging.** Every data source in a scenario is tagged with its quality tier. The scenario inherits the tier of its weakest major input (buildings, terrain, vegetation each assessed separately).
2. **Result-level messaging.** Every map, every statistic, every summary card, and every report page carries a data quality indicator.
3. **Tier-specific wording:**
   - **Screening:** "Based on publicly available data (not independently verified). Suitable for initial assessment and feasibility screening. For planning decisions, verified project-grade data is recommended."
   - **Project:** "Based on verified project data. Suitable for planning decisions within stated model limitations."
   - **Research:** "Based on curated research-grade data. Suitable for scientific analysis and publication, subject to stated model assumptions."
4. **Visual indicators:** Screening-grade results carry a subtle "SCREENING" watermark on maps. Not removable. Not suppressible.
5. **Report adjustment:** Report templates contain tier-specific language blocks. The summary section adjusts hedging language based on data tier. Numbers are the same; framing is different.
6. **Workflow gates:** Certain outputs may be restricted by tier. Example: "Threshold exceedance hours" might be reported with wider uncertainty bands at screening grade, or accompanied by an explicit caveat.

### 7.3 Data Acquisition

| Source | Access method | License | Attribution required |
|---|---|---|---|
| OSM buildings + land use | Overpass API, automated on study area definition | ODbL 1.0 | Yes: "© OpenStreetMap contributors" |
| Copernicus DEM (30m) | HTTP download, automated | Free, open | Yes: "Contains Copernicus data" |
| German state LoD2 CityGML | User upload or auto-fetch from open data portals (NRW, Berlin, Hamburg: open; others: verify per state) | Varies by state | Verify per state |
| LiDAR DEM (1m) | User upload | Depends on source | User responsibility |
| Tree inventories | User upload (CSV: position, species, height, crown diameter) | User's data | N/A |
| Meteorological forcing | Pre-built templates from DWD TRY data, or user upload | DWD: GeoNutzV (free, commercial OK) | Attribution for DWD-derived data |

---

## 8. User Interaction Model

### 8.1 Normal-User Path (Planner / Landscape Architect)

This is the primary workflow. The product must be fully usable through this path alone.

1. **Create project** → name, location, brief description of planning question.
2. **Define study area** → draw bounding box or polygon on map. System auto-fetches available public geodata. User optionally uploads higher-quality data. System tags data quality tier automatically.
3. **Review base data** → map shows fetched buildings, terrain, existing vegetation. User confirms or corrects. System flags data quality issues ("OSM building heights are estimates in this area — 6 buildings have no height data and will use a default of 10m").
4. **Create scenario** → pick template:
   - "Baseline assessment" — existing conditions only
   - "Single intervention test" — baseline + one set of changes
   - "Concept comparison" — baseline + 2–3 alternative intervention packages
5. **Edit interventions on map** →
   - Click to place trees. Side panel shows species picker (common local species first, with thumbnail, mature height, crown width). Click map to position. Panel shows properties; adjust if needed.
   - Draw polygon to change surface. Panel shows material picker (asphalt → grass, gravel, permeable paving, etc.).
   - Click building to toggle green roof. Panel shows substrate depth options (extensive/intensive).
   - All edits validated in real time. Error: red highlight + message ("Tree overlaps building footprint — move or remove"). Warning: yellow highlight + message ("Tree density in this area is unusually high — results may overestimate cooling if crown overlap is significant").
6. **Configure simulation** → guided form:
   - Forcing: dropdown with 4 archetypes (typical hot day, heat wave day, moderate summer day, warm night) + brief description of each. No raw meteorological parameter entry.
   - Resolution: recommended default shown ("10m — suitable for your 400m × 350m domain"). Override available but with confirmation ("5m resolution will approximately quadruple simulation time").
   - Period: 6h default (10:00–16:00 for daytime assessment). Options for 12h, 24h.
7. **Validate and submit** → system shows validation summary. Errors block. Warnings allow override. Green → submit. User sees estimated completion time.
8. **Monitor** → progress bar with meaningful status: "Simulating 13:00 of 10:00–16:00 period (estimated 12 min remaining)".
9. **View results** → map overlays with standard comfort classification legend. Time slider. Summary cards: "62% of the study area exceeds PET 35°C (strong heat stress) between 12:00–15:00." If comparison: difference map, delta summary.
10. **Generate report** → one click. PDF downloads with all required content. No manual editing needed for standard use.

### 8.2 Expert Override Path (Consulting Scientist)

Available only after the core workflow is stable (Phase 4). Accessed via an "Expert" toggle that requires acknowledgement: "You are entering expert mode. Changes you make here bypass the standard guardrails. Expert overrides are logged and noted in reports."

- **Namelist inspector:** read-only view of the generated PALM namelist. Selective parameter editing for specific fields (e.g., turbulence closure scheme, output frequency). Each edit re-triggers validation.
- **Custom forcing upload:** upload measured meteorological data. System validates format (NetCDF structure, required variables, physical plausibility of values).
- **Extended outputs:** request additional PALM output variables beyond the standard set.
- **Raw NetCDF download:** access PALM output files directly.
- **Domain overrides:** adjust vertical grid, boundary conditions, nesting (when supported).

Expert overrides are always visible in the audit trail and in the report methodology section: "The following expert overrides were applied: [list]."

### 8.3 Constrained AI Assistant (Phase 4)

The assistant is a chat panel. It helps users understand and operate the tool. It does NOT control simulations.

**Implemented via Claude tool-use with strict boundaries:**
- `explain_parameter(param)` → plain-language explanation
- `suggest_scenario_type(question)` → recommend template based on planning question
- `interpret_result(variable, zone, value)` → explain what a result means in planning terms
- `suggest_fix(error)` → explain validation error + suggest resolution
- `rephrase_summary(text)` → improve readability of template summary (numbers and claims unchanged)
- `explain_confidence(tier, variable)` → explain confidence statement meaning

**Cannot:**
- Modify scenarios, configure simulations, or generate namelists
- Override validation
- Invent claims not directly computed
- Promise outcomes

**System prompt:** "You are a planning assistant for PALM4Umadeeasy. You help users understand the tool, choose appropriate scenarios, and interpret results. You never generate or modify simulation configurations. You never make claims not directly supported by computed results. You reference actual values from the result data when explaining outcomes. When uncertain, say so."

---

## 9. Result Strategy

### 9.1 Output Variable Pipeline

| PALM output | Derived product | Display name | Unit | Height note |
|---|---|---|---|---|
| `theta` (potential temperature) | Air temperature (converted using surface pressure) | Air Temperature | °C | PALM bio-met module computes at agent height, typically ~1.1m above ground per PALM documentation. We display as "pedestrian height (~1.1m)" unless our own post-processing interpolates to a different level, which must be documented. |
| `u`, `v`, `w` | Wind speed magnitude | Wind Speed | m/s | Same height convention as bio-met agent. |
| `bio_mrt` / `t_rad_mrt` | Mean radiant temperature | Radiant Temperature | °C | Bio-met module output at agent height (~1.1m). |
| Ta + Tmrt + wind + humidity | PET | Thermal Comfort (PET) | °C | Computed from bio-met outputs. If we choose to compute at a different reference height (e.g., 1.4m for comparability with field measurements), this must be explicitly stated in methodology. |
| Ta + Tmrt + wind + humidity | UTCI | Thermal Comfort (UTCI) | °C | Same height note as PET. |
| `t_surface` | Surface temperature | Surface Temperature | °C | Ground level. |
| `rad_sw_in`, shadow flags | Shadow pattern | Shading Map | shaded/unshaded | Ground level. |
| Wind speed at pedestrian level | Lawson classification | Wind Comfort | 5-class | Agent height. |

**Height convention decision:** To be finalised in Phase 0 after reviewing exact PALM bio-met output heights for the configuration we use. If PALM outputs at ~1.1m and we want to report at 1.4m (common in biometeorology field studies), we must either configure PALM accordingly or interpolate in post-processing. Either way, the report methodology section must state the exact height used and the reason.

### 9.2 Standard Legends and Classifications

**Thermal comfort (PET), per VDI 3787 Blatt 2:**

| PET range (°C) | Thermal perception | Stress grade | Map colour |
|---|---|---|---|
| < 4 | Very cold | Extreme cold stress | Deep blue |
| 4–8 | Cold | Strong cold stress | Blue |
| 8–13 | Cool | Moderate cold stress | Light blue |
| 13–18 | Slightly cool | Slight cold stress | Cyan |
| 18–23 | Comfortable | No thermal stress | Green |
| 23–29 | Slightly warm | Slight heat stress | Yellow |
| 29–35 | Warm | Moderate heat stress | Orange |
| 35–41 | Hot | Strong heat stress | Red |
| > 41 | Very hot | Extreme heat stress | Dark red |

Non-negotiable colour scheme. Consistent across all maps, reports, exports, and comparison views.

**Wind comfort (Lawson, as standardised in NEN 8100):**

| Mean wind (m/s) | Class | Acceptable for |
|---|---|---|
| < 2.5 | A — Sitting (long) | Outdoor dining, reading |
| 2.5–4.0 | B — Sitting (short) | Coffee, waiting |
| 4.0–6.0 | C — Standing | Bus stops, window shopping |
| 6.0–8.0 | D — Walking | Pedestrian through-routes |
| > 8.0 | E — Uncomfortable | Unacceptable for pedestrian use |

### 9.3 Comparison Engine

Comparisons are the core product output. Every comparison produces:

1. **Difference map.** Variable B minus Variable A at matched timesteps. Diverging colour scale: blue (improvement) → white (no change) → red (worsening).
2. **Delta statistics per zone.** For each user-defined or auto-detected zone: mean change, max change, area improved (m²), area worsened (m²), hours of threshold exceedance change.
3. **Threshold impact statement.** "In the baseline, 4,200 m² (42% of the study area) exceeds PET 35°C between 12:00–15:00. With the proposed tree planting, this reduces to 2,800 m² (28%). Reduction: 1,400 m² (14 percentage points)."
4. **Ranked zone summary.** Zones sorted by improvement magnitude. "Largest improvement: Zone 3 (market square), −4.2°C mean PET during 12:00–15:00."
5. **Side-by-side view.** Same timestep, same colour scale, same spatial extent. Synchronized pan/zoom.
6. **Intervention efficiency.** Where applicable: "Per-tree contribution: each tree reduces area-mean PET by approximately 0.08°C. This is a rough allocation — actual effect depends on placement."

### 9.4 Report Structure

Every generated PDF report follows this structure:

1. **Cover page** — project name, scenario names, date, data quality tier, generated-by note.
2. **Executive summary** — 3–5 sentences: what was tested, what the main finding is, what the recommendation is (if the scenario supports one). Written from template + AI rephrasing (numbers locked).
3. **Study area description** — map of the domain, data sources used, data quality tier with explanation.
4. **Scenario descriptions** — what was changed between baseline and intervention(s). Map showing edited elements. Table of changes (N trees added, X m² surface changed, etc.).
5. **Methodology** — what PALM is, what version was used, what grid resolution, what forcing conditions, what comfort indices were computed, what classification system was applied, what height convention was used. Citable.
6. **Results: Baseline** — comfort maps at key timesteps, summary statistics, threshold exceedance.
7. **Results: Intervention(s)** — same format as baseline.
8. **Comparison** — difference maps, delta statistics table, threshold impact, ranked zone summary.
9. **Confidence and limitations** — data quality tier impact, model limitations, domain edge effects, resolution caveats, specific per-scenario caveats.
10. **Appendix** — full timestep sequence (optional), zonal statistics tables, technical parameters.
11. **Footer (every page)** — "Model-based estimate. Not a measurement. See §9 for limitations."

### 9.5 Confidence and Limitations Layer

This is not a footnote. It is a structural component.

Every result display (map, chart, summary card) and every report section includes context-appropriate confidence messaging. This is auto-generated from:

- Input data quality tier
- Domain size relative to study area (edge effect risk)
- Grid resolution relative to element sizes
- Forcing archetype (typical day vs. heat wave)
- Specific scenario characteristics (e.g., very dense tree planting, buildings from OSM)

Example auto-generated limitations for a screening-grade street tree assessment:

> "This analysis uses screening-grade building data from OpenStreetMap. Building heights are estimated and may differ from actual values. Wind patterns and shadow calculations are sensitive to building geometry accuracy. The meteorological forcing represents a typical Central European hot day archetype, not a specific observed day. PALM-4U resolves turbulent mixing at the grid scale (10m); features smaller than this are parameterised. Green roof substrate moisture was set to field capacity (well-watered assumption). Results are model-based estimates suitable for initial screening. For planning decisions, a follow-up assessment with verified building data is recommended."

---

## 10. Quality and Standards

### 10.1 Scientific Defensibility

- Every comfort index computation traceable to a published method with full citation.
- PET: Höppe (1999). UTCI: Bröde et al. (2012). Classification: VDI 3787 Blatt 2. Wind: Lawson (1975) / NEN 8100.
- PALM version pinned per release of our product. Configuration defaults documented.
- Every namelist generated is traceable to a template version + catalogue version.
- Methodology document is citable and included in every report.

### 10.2 Validation and Testing Strategy

| Level | What | How | Frequency |
|---|---|---|---|
| **Translation layer unit tests** | Each scenario element type → correct PALM input fragments | pytest with reference NetCDF fragments | Every commit |
| **Round-trip integration tests** | Scenario JSON → translate → run PALM → post-process → verify result value ranges | Automated pipeline with small reference domains | Nightly CI (or weekly if PALM runs are expensive) |
| **Comfort index validation** | PET/UTCI from our code vs. reference implementations | Test matrix of Ta/Tmrt/wind/humidity combos. Tolerance: ±0.5°C for PET, ±0.3°C for UTCI | Every commit to comfort module |
| **Comparison engine tests** | Known two-scenario pair → verify delta maps match hand computation | Unit tests with synthetic grids | Every commit |
| **palm_csd integration tests** | Our generated inputs → palm_csd → valid static driver | Submit known scenario, verify NetCDF structure and values | Every commit to translation module |
| **Report regression tests** | Generated PDFs contain required sections, correct values, correct disclaimers | PDF text extraction + assertions | Every commit to report module |
| **PALM crash handling** | Deliberately submit invalid configs, verify graceful error handling | Integration tests with known-bad inputs | Weekly |
| **UI end-to-end tests** | Full workflow from study area to report download | Playwright | Before every release |

### 10.3 Reproducibility and Versioning

- Every run records: frozen scenario JSON, catalogue versions, PALM version, palm_csd version, translation layer version, post-processing version.
- Resubmitting the same scenario with the same software versions produces identical PALM inputs (deterministic translation).
- Version metadata stored in database and embedded in every report footer.
- Database migrations managed with Alembic. Schema changes are forward-only (no destructive migrations).

### 10.4 Audit Trail

- Scenario edits: who, when, JSON diff of change.
- Run submissions: who, when, scenario version, validation result.
- Report generation: who, when, which run, which export format.
- Expert overrides: logged individually with parameter name, old value, new value, user, timestamp.
- Append-only. Not deletable by users. Retained for project lifetime.

### 10.5 Documentation Standards

| Document | Audience | Standard |
|---|---|---|
| **User guide** | Planners, consultants | Task-oriented ("How do I compare two tree planting options?"). Screenshots. No jargon. |
| **Methodology document** | Peer reviewers, clients, regulators | Citable. Describes PALM version, configuration defaults, comfort computation, classification sources. Suitable for report appendix or separate publication. |
| **Admin guide** | IT staff, self-hosting consultancies | Deployment, backup, monitoring, PALM compilation, troubleshooting. |
| **API documentation** | Developers, integrators | Auto-generated from FastAPI OpenAPI spec. |
| **Architecture Decision Records** | Internal | One ADR per significant decision. Template: context, decision, consequences. |
| **Code** | Developers | Docstrings on public functions. No comments on obvious code. No generated boilerplate comments. |

### 10.6 Release Standards

No release without:
- All test suites passing (unit, integration, end-to-end)
- PALM reference case validated against expected output
- PDF report regression clear
- At least one full end-to-end scenario (scenario creation → run → comparison → report) on the release build
- CHANGELOG updated
- Version number incremented (semver)
- PALM version compatibility noted

---

## 11. Legal / Compliance Architecture

**Important: every statement below is a working assumption or a question, not a legal conclusion. Commercial deployment requires formal legal review of all items marked with [LEGAL REVIEW REQUIRED].**

### 11.1 PALM License (GPL-3.0)

- PALM source code is licensed under GPL-3.0.
- **Working assumption:** Our product does not modify PALM source code. We compile the unmodified PALM binary and execute it as a separate process. Our wrapper code (API, frontend, translation layer, post-processing) communicates with PALM exclusively through file I/O (writing input files, reading output files). Under this interpretation, our code is a separate work and is not required to be GPL-licensed.
- **Working assumption (SaaS):** GPL-3.0 (unlike AGPL) does not require source distribution for software accessed over a network. If we run PALM as a backend service and users interact via browser, we are likely not distributing the PALM binary to users.
- **[LEGAL REVIEW REQUIRED]:** If we distribute Docker images containing the compiled PALM binary (e.g., for self-hosted deployment), GPL-3.0 requires making the corresponding PALM source available to recipients. This is already satisfied by PALM's public source repository, but the mechanism (written offer, source link, etc.) needs to comply formally.
- **[LEGAL REVIEW REQUIRED]:** Confirm that the "separate work" interpretation holds for our specific integration pattern (file I/O, subprocess execution). This is a standard pattern but should be confirmed by a lawyer experienced in GPL.

### 11.2 PALM-4U GUI Code

- The PALM-4U web GUI was developed under BMBF funding (UC² programme).
- **Decision: we do not reuse any PALM-4U GUI source code.** We build our frontend independently.
- **[LEGAL REVIEW REQUIRED]:** Before reading PALM-4U GUI source code (even for reference), verify its license. BMBF-funded code may have specific terms regarding open-access publication, derivative works, or commercial reuse. Do not assume it is freely available simply because it was publicly funded.
- Studying published papers, public documentation, and public API descriptions about the PALM-4U GUI is acceptable (these are published works, not code).

### 11.3 palm_csd License

- palm_csd is part of the PALM model system and is presumably GPL-3.0.
- **Working assumption:** We execute palm_csd as a separate process (subprocess call), passing it input data and reading its output. Same separation argument as PALM itself.
- **[LEGAL REVIEW REQUIRED]:** Confirm palm_csd's license. If it is GPL-3.0 and we call it as a subprocess, the same analysis as §11.1 applies.

### 11.4 Data Licensing

| Source | License | Commercial use | [LEGAL REVIEW REQUIRED]? |
|---|---|---|---|
| OpenStreetMap | ODbL 1.0 | Yes, with attribution | No — well-established terms |
| Copernicus DEM | Free, open (Copernicus licence) | Yes, with attribution | No |
| German state CityGML LoD2 | Varies by state (NRW: dl-de/zero-2-0; others vary) | Depends on state | Yes — verify per-state terms before enabling auto-fetch for each state |
| DWD meteorological data | GeoNutzV (free since 2017) | Yes, with attribution | Verify: can we redistribute pre-processed forcing templates derived from DWD TRY data? |
| pythermalcomfort | MIT license | Yes | No |

### 11.5 Privacy / GDPR

- User accounts store: name, email, hashed password, project associations, usage logs.
- No sensitive personal data in simulation inputs or outputs.
- GDPR compliance required if operating in EU: privacy policy, data processing agreement (DPA) template for B2B clients, right to access and deletion, data export on request.
- **[LEGAL REVIEW REQUIRED]:** If deployed on cloud infrastructure, confirm EU data residency. If self-hosted by client, GDPR responsibility shifts to them (but we should provide a DPA template).

### 11.6 Liability and Disclaimer

Every report, every result screen, and the product's terms of service must include:

> "This analysis is based on numerical simulation using the PALM model system. Results are model-based estimates that depend on input data quality, model parameterisation, and spatial resolution. They do not constitute measurements or guarantees. This tool is intended as a decision-support aid and does not replace professional judgement or site-specific assessment. The operators accept no liability for decisions made based on simulation results."

- This disclaimer is non-removable by users and non-suppressible by any UI setting.
- It appears in every PDF report footer, on every result screen, and in the product's terms of service.
- **[LEGAL REVIEW REQUIRED]:** Disclaimer wording should be reviewed by a lawyer for the target jurisdiction (Germany: Haftungsausschluss). Standard product liability and professional negligence considerations apply.

### 11.7 Pre-Commercialisation Legal Checklist

Before any commercial deployment (paid access, client deliverables, or public SaaS):

- [ ] GPL interpretation for PALM integration reviewed by lawyer
- [ ] palm_csd license confirmed and integration pattern reviewed
- [ ] PALM-4U GUI code confirmed as not used (documentation of build-from-scratch approach)
- [ ] Per-state data licensing reviewed for all supported German states
- [ ] DWD data redistribution rights confirmed for forcing templates
- [ ] GDPR compliance reviewed (privacy policy, DPA template, data residency)
- [ ] Liability disclaimer reviewed for German law
- [ ] Terms of service drafted and reviewed
- [ ] Impressum requirements met (if web-facing)

---

## 12. Phase Structure

Phases are defined by exit criteria, not calendar dates. Each phase is complete when all exit criteria are met.

### Phase 0: Prove the Spine's Foundation

**Objective:** Eliminate the highest-risk unknowns. Can we compile PALM, run it, wrap palm_csd, and read outputs programmatically?

**Work:**
- Provision a Linux environment (VM, cloud instance, or dedicated machine)
- Compile PALM-4U from source with bio-met module. Document every dependency, compiler flag, and version.
- Run PALM urban reference test case. Verify output.
- Evaluate palm_csd:
  - Can it generate a valid static driver from GeoJSON building footprints + heights?
  - Can it accept tree placements as point data?
  - Can it handle surface type overrides for user-defined polygons?
  - What are its input format requirements?
  - Document: what works, what doesn't, what needs wrapping/extension.
- If palm_csd has a hard blocker: document it in an ADR. Define the minimum custom code needed to work around it.
- Evaluate palmpy: useful for I/O utilities? Document use/don't-use decision.
- Write a Python script that: reads PALM output NetCDF, extracts bio-met variables, notes exact output heights, computes PET using pythermalcomfort, writes GeoTIFF. Verify GeoTIFF correctness.
- Validate PET computation against reference (RayMan or UTCI operational procedure).
- Document exact PALM input file structure: namelist syntax, static driver variables and dimensions, dynamic driver format, bio-met configuration.
- Determine bio-met output height convention: confirm whether PALM bio-met outputs at ~1.1m or configurable. Document our height convention decision in an ADR.

**Exit criteria:**
- [ ] PALM compiled and running on our Linux environment
- [ ] Reference test case completes and outputs match PALM documentation
- [ ] palm_csd evaluation complete with documented decision (ADR) on reuse vs. extend vs. replace
- [ ] Python post-processing script produces valid PET GeoTIFF
- [ ] PET validated against reference (±0.5°C)
- [ ] Bio-met output height convention documented (ADR)
- [ ] PALM input format fully documented in our own reference doc
- [ ] All findings written to `palm/` directory as permanent reference

### Phase 1: Prove the Spine End-to-End

**Objective:** The entire foundation spine (§4) works headless. JSON in → comparison report out. No frontend. No UI. No shortcuts.

**Work:**
- Design and implement scenario JSON schema (Pydantic). Versioned. Deterministic serialisation.
- Build species catalogue (8+ species with LAD profiles from literature, with citations)
- Build surface type catalogue (10+ types with PALM parameter mappings)
- Build meteorological forcing template library (4 archetypes from DWD TRY data)
- Implement translation layer orchestrator:
  - Scenario JSON → geodata preparation → palm_csd invocation → static driver
  - Scenario JSON → namelist generation (Jinja2 templates)
  - Scenario JSON → dynamic driver selection
- Implement validation engine: spatial conflicts, physics checks, resource estimation, data quality assessment
- Implement job runner: submit PALM, parse stdout for progress, detect success/failure, handle crashes
- Implement post-processing engine: variable extraction (xarray), comfort index computation (pythermalcomfort), classification (VDI 3787), map tile generation (rasterio/rio-tiler), zonal statistics
- Implement comparison engine: difference grids, delta statistics, threshold impact, ranked zone summary
- Implement confidence propagation: data tier → result-level confidence statements
- Implement report generator: PDF from HTML template (WeasyPrint) with all 11 required sections
- Stand up PostgreSQL + PostGIS and S3-compatible object storage
- Write integration test suite: submit test scenarios, verify full pipeline
- Write comparison test: two-scenario pair, verify deltas against hand computation

**Exit criteria:**
- [ ] Submit a "baseline" scenario JSON → receive comfort maps + statistics + PDF report. No manual steps.
- [ ] Submit a "baseline + 20 street trees" scenario pair → receive comparison report with difference maps, delta statistics, threshold impact statement
- [ ] Validation engine catches all intentionally invalid test scenarios (maintain a suite of ≥15 invalid scenarios)
- [ ] PET/UTCI maps verified against manual computation for ≥3 reference points
- [ ] Comparison delta maps verified against hand computation for synthetic test case
- [ ] PDF report contains all 11 required sections with correct values
- [ ] Confidence statements correctly reflect data tier
- [ ] Species catalogue has ≥8 entries with literature citations
- [ ] Pipeline end-to-end test runs in CI
- [ ] All translation layer outputs are deterministic (same input → byte-identical output)

### Phase 2: Frontend + API (Core Workflow)

**Objective:** A planner can create a scenario, run it, view results, compare with baseline, and download a report — entirely in the browser.

**Work:**
- Implement FastAPI application: auth, scenarios, jobs, results, export endpoints
- Implement WebSocket for job progress
- Implement JWT authentication (email/password)
- Build Next.js application with MapLibre
- Implement study area definition: draw on map, auto-fetch OSM buildings + DEM, display data quality assessment
- Implement tree placement tool with species picker
- Implement surface editing tool with material picker
- Implement green roof toggle on buildings
- Implement simulation settings form with real-time validation feedback
- Implement job submission + progress monitoring
- Implement result map viewer: comfort classification overlays, standard legends, time slider, summary cards
- Implement comparison view: side-by-side, difference map, delta summary cards, threshold impact
- Implement confidence panel: data tier indicator + contextual messaging
- Implement report download: PDF, GeoTIFF
- Connect all frontend actions to API
- Write Playwright end-to-end tests for complete workflow

**Exit criteria:**
- [ ] A tester with no PALM experience creates a "baseline vs. 20 street trees" comparison entirely in the browser and downloads a PDF report
- [ ] Validation errors shown inline with clear, actionable messages
- [ ] Result maps display with standard VDI 3787 colour scale
- [ ] Comparison view shows difference map with diverging colour scale + delta statistics
- [ ] PDF report downloads with all 11 sections, correct values, correct confidence statements
- [ ] Time slider allows browsing all output timesteps
- [ ] Data quality tier badge visible on result viewer and in report
- [ ] All API endpoints tested (pytest + httpx)
- [ ] All frontend workflows tested (Playwright)
- [ ] No user interaction touches Linux or exposes PALM internals

### Phase 3: Production Hardening + Expanded Interventions

**Objective:** Production-grade for pilot deployment. Extended editing capabilities. Multi-user.

**Work:**
- Green wall / façade greening: species catalogue entries (Hedera helix, Parthenocissus, Fallopia, etc. — leveraging Minka's PhD data), translation layer extension for vertical LAD profiles on building facades, result interpretation
- Building geometry editing: add/remove buildings, modify heights. Static driver regeneration with palm_csd re-invocation.
- Custom meteorological forcing upload: format validation, physical plausibility checks, conversion to PALM dynamic driver format
- Wind comfort: extract wind field, apply Lawson classification, generate wind comfort maps
- Batch job submission: queue multiple scenarios, email/notification on completion
- User accounts with role-based access (viewer/editor/admin) and project-level permissions
- Project sharing: invite users to projects with specific roles
- Job queue with multiple Celery workers
- Monitoring: Prometheus metrics, Grafana dashboards, alerting
- Security hardening: input sanitisation audit, auth flow review, file upload validation
- Performance: tile caching, database query optimisation, lazy loading for large result sets
- Admin dashboard: job queue status, server load, storage usage, user management

**Exit criteria:**
- [ ] Façade greening scenarios produce valid PALM results. Vertical LAD profiles verified.
- [ ] Building edits correctly regenerate static driver and produce valid PALM results
- [ ] Custom forcing upload validates and produces valid dynamic driver
- [ ] Wind comfort maps generated with Lawson classification
- [ ] Multiple users can work simultaneously without interference
- [ ] System handles PALM failures gracefully (no hung jobs, no corrupt state, user sees clear error)
- [ ] Monitoring alerts fire on configurable thresholds
- [ ] Security review completed, no critical findings
- [ ] Deployed to ≥2 pilot users (real planners or consultants) for real project work
- [ ] Pilot users complete at least one real project deliverable using the tool

### Phase 4: AI Assistant + Expert Layer + Advanced Outputs

**Objective:** Constrained AI assistant for guidance and interpretation. Expert overrides for consulting scientists. Advanced result types.

**Work:**
- AI assistant (Claude API): tool-use integration with strict boundaries per §8.3
- Scenario guidance: "I need to assess whether a new parking garage will worsen wind conditions" → assistant recommends scenario type and configuration
- Result interpretation: assistant explains results using actual computed values
- Report prose improvement: AI rephrases template summaries for readability (numbers locked)
- Expert override panel: namelist inspector, selective parameter editing, custom forcing, raw output access. Per §8.2 — logged, noted in report.
- Vegetation patches: hedges, shrubs, ground cover with type catalogue
- Shadow/shading analysis as first-class output
- Threshold exceedance maps ("hours above PET 35°C")
- Time-of-day animation (frame sequence or GIF)
- Cross-section views (vertical slices)
- Extended species catalogue (20+ entries)
- User-defined zones for zonal statistics
- Export: GeoJSON, shapefile, XLSX, presentation-quality PNG/SVG

**Exit criteria:**
- [ ] AI assistant provides helpful responses for ≥10 scripted test scenarios
- [ ] AI never generates claims not supported by computed results (tested against adversarial prompts)
- [ ] Expert overrides are logged and appear in report methodology section
- [ ] All advanced output types render correctly and pass visual QA
- [ ] Species catalogue has ≥20 validated entries with citations
- [ ] User testing with ≥5 planners/consultants; structured feedback collected
- [ ] Mean scenario creation time ≤25 min for a tree-planting comparison (measured)
- [ ] Generated reports accepted by pilot users for client delivery without substantial rework

### Phase 5: Scale, Polish, Publish

**Objective:** Multi-tenant production deployment. Comprehensive documentation. Community credibility.

**Work:**
- Cloud deployment option (on-demand HPC for PALM)
- Multi-tenant isolation
- Usage metering and cost allocation
- User guide (task-oriented, with screenshots)
- Methodology document (citable, peer-reviewed if possible)
- Admin guide (deployment, backup, monitoring)
- API documentation (auto-generated)
- Conference presentation at PALM user meeting, urban climate conference, or planning conference
- Methodology paper drafted for peer-reviewed journal
- Performance benchmarks documented

**Exit criteria:**
- [ ] System handles ≥10 concurrent users with job queuing
- [ ] Cloud deployment documented and tested
- [ ] All documentation complete and reviewed
- [ ] Methodology paper submitted to journal
- [ ] Presented at ≥1 relevant conference or workshop
- [ ] ≥3 real planning projects completed using the tool (with client deliverables)
- [ ] Pre-commercialisation legal checklist (§11.7) fully cleared

### Phase 6+: Advanced Modules

- Pollutant dispersion (PALM chemistry module)
- Nested domains for multi-scale analysis
- Street furniture (pergolas, shelters, shade sails)
- Water features
- Energy balance outputs
- ENVI-met / Greenpass import-export for interoperability
- White-label deployment
- Public API for third-party integrations

---

## 13. Repo / Module Structure

```
PALM4Umadeeasy/
│
├── README.md
├── IMPLEMENTATION_PLAN.md              This document
├── CHANGELOG.md
├── LICENSE                             Product license (NOT PALM's GPL)
├── docker-compose.yml                  Development stack
├── docker-compose.prod.yml             Production deployment
├── Makefile                            Common commands
│
├── docs/
│   ├── architecture.md                 System architecture reference
│   ├── methodology.md                  Citable methodology document
│   ├── user-guide/                     Task-oriented user docs
│   ├── admin-guide/                    Deployment + operations
│   ├── api/                            Auto-generated OpenAPI docs
│   └── decisions/                      Architecture Decision Records
│       ├── ADR-001-python-backend.md
│       ├── ADR-002-palm-csd-reuse.md
│       ├── ADR-003-biomet-height.md
│       └── ...
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── src/
│   │   ├── app/                        Next.js App Router pages
│   │   │   ├── (auth)/
│   │   │   ├── projects/
│   │   │   ├── scenarios/
│   │   │   └── admin/
│   │   ├── components/
│   │   │   ├── map/                    MapLibre, draw tools, overlays
│   │   │   ├── editor/                 Scenario editing panels
│   │   │   ├── results/                Result display + comparison
│   │   │   ├── assistant/              AI chat panel (Phase 4)
│   │   │   └── common/                 Shared UI primitives
│   │   ├── lib/                        API client, WS, validation schemas
│   │   ├── stores/                     Zustand state
│   │   └── types/                      Shared TypeScript types
│   └── tests/
│       ├── e2e/                        Playwright
│       └── components/
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic/                        DB migrations
│   ├── src/
│   │   ├── main.py                     FastAPI entry
│   │   ├── config.py
│   │   ├── api/                        REST + WS endpoints
│   │   ├── models/                     DB models + Pydantic schemas
│   │   ├── translation/                Scenario → palm_csd → PALM config
│   │   │   ├── engine.py               Orchestrator
│   │   │   ├── namelist.py             Jinja2 namelist generation
│   │   │   ├── static_driver.py        palm_csd wrapper + extensions
│   │   │   ├── dynamic_driver.py       Forcing selection/conversion
│   │   │   ├── grid.py                 Grid computation
│   │   │   └── templates/              Jinja2 namelist templates
│   │   ├── catalogues/                 Species, surfaces, vegetation, forcing
│   │   ├── validation/                 Pre-run validation engine
│   │   ├── execution/                  Celery tasks, PALM runner, monitor
│   │   ├── postprocessing/             Extract, comfort, classify, compare, tiles
│   │   ├── reporting/                  PDF, maps, GeoTIFF, CSV, XLSX
│   │   ├── ai/                         Claude assistant (Phase 4)
│   │   ├── geodata/                    OSM fetch, DEM, CityGML import
│   │   └── monitoring/                 Prometheus, logging, health
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/                   Test scenarios, reference outputs
│
├── palm/                               PALM-related assets (NOT source)
│   ├── compile.sh                      Build script
│   ├── compile.md                      Compilation guide
│   ├── reference_cases/                Known-good configs + expected outputs
│   ├── forcing_templates/              Pre-built forcing files
│   ├── palm_csd_notes.md              palm_csd evaluation findings
│   └── version_compat.md              PALM version compatibility
│
├── catalogues/                         Source-of-truth catalogue data
│   ├── species.json                    Tree species (with citations)
│   ├── surfaces.json                   Surface types
│   ├── vegetation.json                 Non-tree vegetation
│   ├── comfort_thresholds.json         Classification thresholds
│   └── sources.bib                     BibTeX for catalogue entries
│
├── deploy/
│   ├── docker/
│   │   ├── Dockerfile.frontend
│   │   ├── Dockerfile.backend
│   │   └── Dockerfile.worker
│   ├── nginx/
│   ├── systemd/
│   └── terraform/                      Cloud infra (Phase 5)
│
└── .github/
    ├── workflows/
    │   ├── test.yml                    CI: lint + tests
    │   ├── build.yml                   CI: Docker images
    │   └── palm-validation.yml         PALM reference case (weekly)
    └── ISSUE_TEMPLATE/
```

---

## 14. Model / Workflow Recommendations

### 14.1 Claude Code Usage

| Activity | Model | Rationale |
|---|---|---|
| Architecture decisions, ADRs | Opus | Needs full context, complex tradeoffs |
| Translation layer implementation | Opus | Highest-risk code, PALM domain knowledge |
| Post-processing implementation | Opus | Scientific computation, validation logic |
| Frontend component implementation | Opus | Uses preview tools, map integration complexity |
| Catalogue data entry from literature | Sonnet | Structured data, lower complexity |
| Documentation drafting | Sonnet | Text generation, review manually |
| Code review | Opus | /code-review skill |
| Bug fixes, routine refactoring | Sonnet | Straightforward changes |
| PALM debugging (config issues) | Opus | Needs full domain context |

### 14.2 Review Process

- **Phase exit reviews:** full review of all exit criteria. Minka + Claude Opus. Every criterion must be demonstrated, not declared.
- **ADRs:** written before implementation of any significant decision. Template: context, options considered, decision, consequences, review status.
- **Translation layer changes:** require PALM reference case re-validation before merge.
- **Catalogue additions:** require literature citation and parameter validation against PALM documentation.
- **Report template changes:** require PDF regression test (visual QA + content assertion).

### 14.3 Token Efficiency

- IMPLEMENTATION_PLAN.md is the canonical reference. Do not re-derive architecture in conversations.
- Write PALM-specific findings to `palm/` docs once. Read from there in future sessions.
- Use memory system for implementation decisions made during build.
- Use agents for parallel research (e.g., looking up species LAD data from multiple sources). Main context for decision-making.
- Avoid reading entire large NetCDF-related source files — use targeted reads.

---

## 15. Success Criteria

### 15.1 Architecture Success

- [ ] All spine components (§4) have working implementations with clean interfaces
- [ ] Advanced features attach to spine interfaces without modifying spine internals
- [ ] Translation layer produces valid PALM configs for all supported scenario element types
- [ ] Validation engine catches ≥95% of intentionally invalid test scenarios
- [ ] Data quality tier correctly propagates from input tagging to result confidence messaging
- [ ] Comparison engine produces correct deltas (verified against hand computation)
- [ ] Report generator produces all 11 required sections with correct content

### 15.2 Technical Foundation Success

- [ ] PALM compiles and runs reproducibly from documented build script
- [ ] palm_csd integration produces valid static drivers for all supported elements
- [ ] End-to-end pipeline runs in CI (scenario → PALM → results)
- [ ] PET/UTCI validated against reference implementations (±0.5°C PET, ±0.3°C UTCI)
- [ ] Translation layer is deterministic (same input → identical output)
- [ ] System handles PALM failures gracefully
- [ ] All test suites pass: unit, integration, end-to-end

### 15.3 Production-Readiness Success

- [ ] Multi-user with role-based access and project isolation
- [ ] Monitoring and alerting operational
- [ ] Audit trail captures all significant actions
- [ ] Security review completed, no critical findings
- [ ] Backup and restore tested
- [ ] 500m × 500m domain at 10m resolution completes in ≤45 min on target hardware
- [ ] PDF report generation ≤30 seconds
- [ ] Map tile loading ≤2 seconds in browser

### 15.4 Pilot-Use Success

- [ ] ≥3 real planners/consultants have used the tool for actual project work
- [ ] Mean scenario creation time ≤25 min for a tree-planting comparison
- [ ] Generated reports accepted by clients for planning deliverables
- [ ] Confidence messaging rated as honest and helpful
- [ ] No result has been challenged as scientifically indefensible
- [ ] At least one Bebauungsplan climate assessment or comparable deliverable produced using the tool

### 15.5 Business Success (Later)

- [ ] Used by ≥5 organisations in production
- [ ] Revenue-generating
- [ ] Methodology paper published in peer-reviewed journal
- [ ] Presented at relevant conference
- [ ] Referenced in at least one municipal planning document
- [ ] Cost per simulation run known and sustainable
- [ ] Pre-commercialisation legal checklist (§11.7) fully cleared

---

## Appendix A: Key References

- PALM model system: https://palm-model.org
- Maronga et al. (2020): "Overview of the PALM model system 6.0" — Geoscientific Model Development
- Resler et al. (2017): "PALM-USM v1.0" — Geoscientific Model Development
- Höppe (1999): "The physiological equivalent temperature" — Int J Biometeorol
- Bröde et al. (2012): "Deriving the operational procedure for the UTCI" — Int J Biometeorol
- VDI 3787 Blatt 2: Environmental meteorology — human biometeorological evaluation
- Lawson (1975): "The wind environment of buildings"
- NEN 8100: Wind comfort and wind danger in the built environment
- pythermalcomfort: https://github.com/CenterForTheBuiltEnvironment/pythermalcomfort
- palm_csd: PALM static driver creation tool (part of PALM distribution)

## Appendix B: Adjacent / Competing Tools

| Tool | Relationship | Our position |
|---|---|---|
| **PALM-4U web GUI** | Browser-based PALM workflow for researchers. Covers simulation configuration, execution, basic viewing. | We do not replace it. We serve a different user (planner, not researcher) with a different product (decision-support, not simulation management). |
| **ENVI-met** | Commercial microclimate simulation. RANS physics. Established GUI. | Different physics (RANS vs. LES). Our product offers PALM-grade LES physics in a decision-support wrapper. Complementary, not competitive, for users who need LES resolution. |
| **Greenpass** | Green infrastructure rapid assessment. Simpler physics. Faster. | Faster but less resolved. We complement for cases requiring high-fidelity simulation. Minka's Greenpass certification makes cross-referencing credible. |
| **CityComfort+** | PALM-based comfort analysis (Uni Mainz). Research tool. | Monitor for collaboration potential. They may have solved shared problems. Not a commercial product. |
| **SimStadt** | Urban energy simulation. | Different domain. Potential integration for combined energy + microclimate assessments. |

---

*End of master plan v3.0. Ready for external review and build authorization.*
