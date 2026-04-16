# PALM4Umadeeasy — Master Plan

**Version:** 4.0  
**Date:** 2026-04-09  
**Author:** Minka Aduse-Poku / Claude  
**Status:** Active — build in progress  

**Companion documents:**
- `SCIENTIFIC_METHODOLOGY.md` — modelling scope, input handling, translation, simulation, post-processing, confidence propagation
- `LEGAL_AND_GOVERNANCE.md` — licensing, data rights, GDPR, disclaimers, audit trail, release standards

---

## 0. Governing Product Statement

PALM4Umadeeasy is a consultant-grade decision-support platform for urban microclimate intervention testing.

It is not a generic browser wrapper for PALM. It is not a research configuration tool. It is not "PALM with a nicer face."

It is a specialized platform that answers one class of question with scientific defensibility:

> **"What happens to outdoor thermal comfort and wind conditions in this neighbourhood if we implement these specific green/blue infrastructure interventions — and how confident should we be in that answer?"**

The product is built around five capabilities that do not exist in PALM or any current PALM tooling:

1. **Intervention-centric workflow.** The user defines a planning question and edits interventions (trees, surfaces, green roofs, later facade greening, water features). The simulation is a means, not the point.
2. **First-class comparison engine.** Every result exists in relation to a baseline or alternative. Delta maps, ranked zone improvements, threshold impact analysis. Comparison is the default output, not an afterthought.
3. **Confidence-aware outputs.** Input data quality is tagged, propagated through the pipeline, and surfaced in every result and report. The user always knows how much to trust the answer.
4. **Consultant-grade reporting.** PDF reports with professional maps, defensible methodology notes, comparison tables, plain-language summaries, and honest limitations — ready for a municipal committee or funding application without manual rework.
5. **Interpretation and constraint layer.** The product guides users toward valid configurations, blocks physically impossible ones, and translates results into planning-relevant language. It does not expose raw PALM complexity.

The finished product covers thermal comfort (PET, UTCI), wind comfort (Lawson criteria), shading, surface temperature, and — in later phases — pollutant dispersion and energy balance. The core domain is green and blue infrastructure planning in urban areas: street trees, park design, green roofs, facade greening, surface de-sealing, water features, and shade structures.

---

## 1. Positioning Against Existing PALM-4U Tooling

### 1.1 What PALM-4U GUI Already Provides

The PALM-4U ecosystem, developed primarily through the BMBF-funded UC2 programme, already includes:

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

> **Quantified before/after comparison of tree planting and surface de-sealing measures for municipal heat adaptation plans and Bebauungsplan climate assessments.**

This is the sharpest entry because:

1. **Regulatory demand exists now.** German municipalities increasingly require climate impact assessments for new developments (Klimaanpassungsgesetz, Bebauungsplan environmental reports).
2. **The comparison workflow is the core differentiator.** "Baseline vs. proposed development vs. mitigated development" is exactly the three-scenario comparison this product is built for.
3. **Tree planting is the simplest intervention to model correctly.** PALM's plant canopy model is mature.
4. **Surface de-sealing is the second-simplest.** Changing pavement type requires only surface parameter changes.
5. **The output maps directly to what the client needs.** "PET in the proposed courtyard exceeds the strong heat stress threshold for X hours. Adding the proposed 12 trees reduces this to Y hours."

### 2.2 First Paying Use Case

A consulting firm receives a commission to assess microclimate impact of a proposed residential development. The deliverable is a report with baseline, development, and mitigated thermal comfort assessments with comparison. Today this requires a PALM expert spending days on manual configuration. PALM4Umadeeasy reduces this to hours.

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
- Tree placement/removal with species catalogue (20+ species with validated LAD profiles)
- Vegetation patch creation (hedges, shrubs, ground cover)
- Surface material editing (paved, gravel, grass, water, bare soil, permeable paving)
- Green roof configuration (substrate depth, vegetation type)
- Green wall / facade greening configuration (climbing species, coverage, height)
- Building geometry editing: add/remove/modify buildings within the study area
- Street-level shade structures: pergolas, shade sails (simplified geometry)
- Water features: fountains, shallow pools, channels (simplified)

**Simulation Management**
- Scenario templates: "baseline," "single intervention," "multi-intervention," "concept comparison"
- Forcing selection: pre-validated meteorological archetypes plus custom forcing upload
- Domain configuration with validated defaults
- Resource estimation before run
- Job queue with priority, cancellation, restart
- Progress monitoring with meaningful status

**Validation & Guardrails**
- Real-time element conflict detection
- Domain physics validation
- Forcing consistency checks
- Data quality impact warnings
- Resource limit enforcement

**Post-Processing, Results & Reporting**
- See `SCIENTIFIC_METHODOLOGY.md` for full output variable pipeline, classification methods, and comparison methodology

**AI Assistant (Phase 4)**
- Scenario guidance, parameter explanation, result interpretation, report prose refinement
- Constrained via Claude tool-use with strict boundaries

**Expert Overrides (Phase 4)**
- Namelist inspection and selective parameter editing
- Custom forcing upload
- Extended output variable selection
- Raw output access
- These are controlled features added after the core product is stable.

**Administration**
- User accounts with role-based access
- Project sharing and permissions
- Backend monitoring dashboard
- Usage tracking

### 3.2 Capabilities by Phase

| Capability | Phase | Status |
|---|---|---|
| Scenario schema, validation, translation, post-processing, comparison, confidence | 1 | Implemented |
| Frontend + API (map editing, results, reports) | 2 | Implemented |
| Facade greening advisory (non-PALM) | 3 | Implemented |
| Building geometry editing (full rasteriser) | 3 | Implemented |
| Custom forcing upload + validation | 3 | Implemented |
| Wind comfort (Lawson criteria) | 3 | Implemented |
| Multi-user RBAC + project sharing | 3 | Implemented |
| Job queue with priority + monitoring | 3 | Implemented |
| Alembic DB migrations | 3 | Implemented |
| PALM execution on Linux (compile + run) | 0 | Deferred (Linux env needed) |
| Expert overrides (namelist editing, raw output) | 4 | Planned |
| AI assistant (Claude tool-use) | 4 | Planned |
| Vegetation patches (hedges, shrubs) | 4 | Planned |
| Shade structures | 5+ | Planned |
| Water features | 5+ | Planned |
| Pollutant dispersion | 5+ | Planned |
| Nested domains | 5+ | Planned |

---

## 4. Foundation Spine

This is the non-negotiable backbone. Every advanced feature attaches to it. If any element is unreliable, nothing built on top can be trusted.

### 4.1 Spine Components

```
+-------------------------------------------------------------+
|                     FOUNDATION SPINE                         |
|                                                              |
|  1. Scenario Schema    — Deterministic JSON. Pydantic.       |
|  2. Translation Layer  — Scenario -> PIDS static driver +    |
|                          namelist + dynamic driver            |
|  3. PALM Runner        — Deterministic job execution          |
|  4. Post-Processing    — Comfort indices -> classification    |
|                          -> statistics -> map tiles           |
|  5. Comparison Engine  — Delta grids, threshold impact,       |
|                          ranked improvements                  |
|  6. Report Engine      — PDF with maps, summaries,            |
|                          methodology, confidence              |
|  7. Confidence         — Data quality tier -> every result,   |
|     Propagation          every map, every report              |
+-------------------------------------------------------------+
```

### 4.2 Spine Properties

1. **Deterministic.** Same scenario JSON + catalogue version + PALM version = identical outputs.
2. **Testable end-to-end.** CI can submit scenario JSON and verify output values match baselines.
3. **Versioned.** Every component versioned. A result can always be traced to exact configuration.
4. **Modular.** Advanced features attach to spine interfaces without modifying internals.

### 4.3 Current Implementation Status

The spine is implemented end-to-end in stub mode (Windows development environment). The translation layer generates valid PIDS-compliant static drivers (custom, per ADR-002 — palm_csd not used). Post-processing, comparison, and confidence engines are fully implemented. The PALM runner dispatches to one of three backends (`stub`/`remote`/`local`, per ADR-005); the `remote` path and the Linux worker skeleton are wired in and tested against a mocked worker, but real PALM execution still requires Linux provisioning and PALM compilation (ADR-001, ADR-005 Phase B).

---

## 5. Architecture

### 5.1 System Diagram

```
+- BROWSER ------------------------------------------------------+
|  MapLibre GL JS - Scenario Editor - Results Viewer              |
|  Next.js / TypeScript / TailwindCSS                             |
+--------------------------+-------------------------------------+
                           | HTTPS + WebSocket
+- API SERVER -------------+-------------------------------------+
|  FastAPI - Pydantic - JWT - Rate Limiting - Audit Log           |
|  Validation - Translation - Post-Processing - Reporting         |
+----------+---------------+------------------+------------------+
           |               |                  |
     PostgreSQL      S3/MinIO           PALM Workers
     + PostGIS       (files)           (Linux, Celery)
```

### 5.2 Technology Choices

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Next.js 16 (App Router), TypeScript strict, TailwindCSS 4, MapLibre GL JS | React ecosystem, vector maps, strong typing |
| Backend | FastAPI, Pydantic v2, SQLAlchemy async | Python for PALM ecosystem proximity |
| Database | PostgreSQL + PostGIS (SQLite for dev) | Spatial queries; SQLite with WAL for development |
| Job queue | Celery + Redis (SQLite-backed queue for dev) | Long-running PALM jobs |
| Object storage | S3-compatible (MinIO or AWS S3) | PALM I/O files, tiles, reports |
| PDF generation | WeasyPrint | Template-driven, handles maps and tables |
| Monitoring | Prometheus + Grafana | Metrics, alerting |
| Auth | JWT + refresh tokens | Stateless, standard |

### 5.3 Scaling Path

| Stage | Architecture | Capacity |
|---|---|---|
| Single-server | API + DB + PALM on one Linux machine | 1 concurrent run |
| Separated | API on VM, PALM on dedicated compute | Multiple workers |
| Cloud-burst | API on containers, PALM on on-demand HPC | Elastic |
| Multi-tenant | DB-level isolation, per-tenant quotas | Production SaaS |

### 5.4 Deployment Pattern: Windows Prep + Linux PALM Worker (ADR-005)

The consultant-grade solo workflow uses a **split deployment**: everything except the PALM executable itself runs on Windows. PALM execution is delegated to a thin remote Linux worker via HTTP.

```
+- WINDOWS WORKSTATION -------------------------------+
|  Next.js UI                                         |
|  FastAPI backend (validation, translation,          |
|    post-processing, comparison, reporting)          |
|  SQLAlchemy job queue + worker thread               |
|  run_palm() dispatcher                              |
+--------------------+--------------------------------+
                     | HTTP + bearer token
                     | (tar.gz inputs -> tar.gz outputs)
+- LINUX WORKER -----+--------------------------------+
|  FastAPI (linux_worker/)                            |
|  3 endpoints: POST /runs, GET /runs/{id},           |
|    GET /runs/{id}/output                            |
|  mpirun palm <case>  (stubbed until PALM compiled)  |
+-----------------------------------------------------+
```

**Runner modes** (selected by `PALM_RUNNER_MODE`):

| Mode | Behaviour | When to use |
|---|---|---|
| `stub` | Synthetic NetCDF generator (default) | Windows-only dev, CI |
| `remote` | POST to Linux worker, poll, download | Production on Windows |
| `local` | Run `mpirun palm` in-process | Linux-only dev, single-box deployment |

**Why split at `run_palm()`:** every other stage of the spine is pure Python and runs identically on both OSes. Only PALM itself is Linux-bound. Keeping translation, validation, post-processing and reporting on Windows means consultants get a complete offline-capable prep environment and the Linux box can be a small, stateless, multi-tenant execution service.

See `docs/decisions/ADR-005-windows-prep-linux-worker.md` for the full decision record (auth model, bundle format, implementation phases).

---

## 6. Build vs. Reuse Strategy

| Component | Decision | Rationale |
|---|---|---|
| PALM binary | Use as-is | Compile from source, pin to release, no modifications |
| palm_csd | Do not use (ADR-002) | Hard blockers found; build custom PIDS generator |
| palmpy | Evaluate selectively | Useful for I/O utilities; not core dependency |
| PALM-4U GUI | No code reuse | Legal + design separation (ADR-000 S5) |
| pythermalcomfort | Use as library | Established, MIT-licensed, validated |
| Translation layer | Build custom | Core IP — maps interventions to PALM inputs |
| Comparison engine | Build custom | Does not exist in any PALM tooling |
| Confidence propagation | Build custom | Does not exist |
| Report generator | Build custom | Does not exist |

---

## 7. User Interaction Model

### 7.1 Normal-User Path (Planner / Landscape Architect)

1. Create project — name, location, planning question
2. Define study area — draw on map, auto-fetch public geodata, tag quality tier
3. Review base data — confirm buildings, terrain, vegetation
4. Create scenario — pick template (baseline, intervention, comparison)
5. Edit interventions on map — place trees, change surfaces, toggle green roofs, edit buildings
6. Configure simulation — forcing archetype, resolution, period (guided defaults)
7. Validate and submit — validation summary, resource estimate, submit
8. Monitor — progress with meaningful status
9. View results — comfort classification maps, time slider, comparison view
10. Generate report — one-click PDF download

### 7.2 Expert Override Path (Phase 4)

Namelist inspector, custom forcing upload, extended outputs, raw download. Logged and noted in reports.

---

## 8. Phase Structure

Phases are defined by exit criteria, not calendar dates.

### Phase 0: Prove the Spine's Foundation
**Objective:** Can we compile PALM, run it, and read outputs programmatically?
**Status:** Partially complete (Python path proven on Windows; PALM compilation deferred to Linux provisioning)

### Phase 1: Prove the Spine End-to-End
**Objective:** JSON in -> comparison report out. No frontend.
**Status:** Complete in stub mode (234 tests passing)

### Phase 2: Frontend + API (Core Workflow)
**Objective:** Planner creates scenario, runs it, views results, compares, downloads report — entirely in browser.
**Status:** Complete (Next.js + FastAPI + MapLibre)

### Phase 3: Production Hardening + Expanded Interventions
**Objective:** Production-grade for pilot deployment. Extended editing. Multi-user.
**Status:** In progress
- [x] Facade greening advisory (non-PALM)
- [x] Building geometry editing with full rasteriser
- [x] Custom forcing upload with validation
- [x] Wind comfort (Lawson classification)
- [x] Multi-user RBAC + project sharing
- [x] Job queue with priority + monitoring
- [x] Alembic DB migrations
- [ ] Linux deployment with real PALM execution
- [ ] Security hardening audit
- [ ] Pilot deployment with real users

### Phase 4: AI Assistant + Expert Layer + Advanced Outputs
**Objective:** Claude-powered assistant, expert overrides, vegetation patches, advanced exports.

### Phase 5: Scale, Polish, Publish
**Objective:** Multi-tenant SaaS, documentation suite, methodology paper, conference presentation.

### Phase 6+: Advanced Modules
Pollutant dispersion, nested domains, shade structures, water features, energy balance, ENVI-met interop.

---

## 9. Repo Structure

```
PALM4Umadeeasy/
├── docs/
│   ├── MASTER_PLAN.md                 This document
│   ├── SCIENTIFIC_METHODOLOGY.md      Modelling methodology
│   ├── LEGAL_AND_GOVERNANCE.md        Licensing, compliance, governance
│   ├── architecture.md                System architecture reference
│   └── decisions/                     Architecture Decision Records
├── frontend/                          Next.js App Router
│   └── src/{app,components,lib}/
├── backend/                           FastAPI + SQLAlchemy
│   ├── src/{api,models,translation,validation,postprocessing,confidence,reporting}/
│   ├── alembic/                       DB migrations
│   └── tests/{unit,integration}/
├── palm/                              PALM compilation + reference data
│   ├── compile.md
│   └── palm_csd_notes.md
├── catalogues/                        Species, surfaces, thresholds (JSON)
└── deploy/                            Docker, nginx, systemd, terraform
```

---

## 10. Workflow Recommendations

### 10.1 Claude Code Usage

| Activity | Model | Rationale |
|---|---|---|
| Architecture decisions, ADRs | Opus | Full context, complex tradeoffs |
| Translation layer | Opus | Highest-risk code, PALM domain knowledge |
| Post-processing | Opus | Scientific computation |
| Frontend components | Opus | Map integration complexity |
| Catalogue data entry | Sonnet | Structured data |
| Documentation | Sonnet | Text generation |
| Bug fixes, refactoring | Sonnet | Straightforward |

### 10.2 Review Process

- **Phase exit reviews:** all criteria demonstrated, not declared
- **ADRs:** written before significant decisions
- **Translation layer changes:** require PALM reference case re-validation
- **Catalogue additions:** require literature citation
- **Report template changes:** require PDF regression test

---

## 11. Success Criteria

### 11.1 Architecture
- All spine components have working implementations with clean interfaces
- Advanced features attach without modifying spine internals
- Translation layer produces valid PALM configs for all supported element types
- Validation engine catches >=95% of invalid test scenarios
- Confidence propagation correct from input to report

### 11.2 Technical Foundation
- PALM compiles and runs reproducibly
- End-to-end pipeline runs in CI
- PET/UTCI validated against reference (+/-0.5 C PET, +/-0.3 C UTCI)
- Translation layer is deterministic
- System handles PALM failures gracefully

### 11.3 Production-Readiness
- Multi-user with RBAC and project isolation
- Monitoring and alerting operational
- Audit trail complete
- 500m x 500m domain at 10m <= 45 min on target hardware
- PDF report <= 30 seconds
- Map tile loading <= 2 seconds

### 11.4 Pilot-Use
- >= 3 real planners/consultants have used it
- Mean scenario creation <= 25 min
- Reports accepted for client delivery
- No result challenged as scientifically indefensible

### 11.5 Business (Later)
- >= 5 organisations in production
- Revenue-generating
- Methodology paper published
- Pre-commercialisation legal checklist cleared (see `LEGAL_AND_GOVERNANCE.md`)

---

## 12. Competitive Positioning

| Tool | Relationship | Our Position |
|---|---|---|
| **PALM-4U web GUI** | Browser-based PALM for researchers | Different user (planner vs researcher), different product (decision-support vs simulation management) |
| **ENVI-met** | Commercial microclimate simulation (RANS) | Different physics (RANS vs LES). We offer PALM-grade LES in a decision-support wrapper |
| **Greenpass** | Green infrastructure rapid assessment | Faster but less resolved. We complement for high-fidelity cases. Minka's Greenpass certification adds cross-reference credibility |
| **CityComfort+** | PALM-based comfort (Uni Mainz) | Monitor for collaboration. Not a commercial product |
| **SimStadt** | Urban energy simulation | Different domain. Potential combined energy + microclimate integration |

---

## Appendix: Key References

- PALM model system: https://palm-model.org
- Maronga et al. (2020): "Overview of the PALM model system 6.0" — GMD
- Resler et al. (2017): "PALM-USM v1.0" — GMD
- Hoeppe (1999): "The physiological equivalent temperature" — Int J Biometeorol
- Broede et al. (2012): "UTCI operational procedure" — Int J Biometeorol
- VDI 3787 Blatt 2: Environmental meteorology — human biometeorological evaluation
- Lawson (1975): "The wind environment of buildings"
- NEN 8100: Wind comfort and wind danger in the built environment
- pythermalcomfort: https://github.com/CenterForTheBuiltEnvironment/pythermalcomfort

---

*End of Master Plan v4.0*
