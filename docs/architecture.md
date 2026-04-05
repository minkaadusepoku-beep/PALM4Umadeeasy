# System Architecture

**Status:** Reference document. Derived from IMPLEMENTATION_PLAN.md §4 and §6. Update this document when architecture decisions change.

---

## Overview

PALM4Umadeeasy has three deployment zones connected by HTTPS/WebSocket and file I/O:

1. **Browser** — Next.js frontend. Map editing, scenario forms, result viewing, report download.
2. **API server** — FastAPI (Python). Auth, scenario management, job orchestration, post-processing, reporting.
3. **PALM execution environment** — Linux. PALM binary, palm_csd, Celery workers. No user-facing surface.

## Foundation Spine

All features attach to this backbone. The spine must work end-to-end (headless, no frontend) before any advanced feature is built.

1. **Scenario Schema** — Deterministic JSON. Pydantic-validated. Versioned.
2. **Preprocessing / Static Driver** — palm_csd backbone + our extensions for intervention elements.
3. **PALM Runner** — Deterministic job execution. Submit, monitor, detect success/failure.
4. **Post-Processing** — Variable extraction → comfort indices → classification → map tiles → statistics.
5. **Comparison Engine** — Scenario A vs B: difference grids, delta statistics, ranked improvements, threshold impact.
6. **Report Engine** — PDF with professional maps, summaries, methodology, confidence, limitations.
7. **Confidence Propagation** — Data quality tier → every result, every map, every report.

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Next.js, TypeScript, MapLibre GL JS, Zustand, Zod | React ecosystem, vector map, lightweight state |
| Backend | FastAPI (Python), Pydantic | Python for PALM ecosystem proximity (netCDF4, xarray, palm_csd) |
| Database | PostgreSQL + PostGIS | Spatial queries on projects/scenarios |
| Job queue | Celery + Redis | Long-running PALM jobs |
| Object storage | S3-compatible (MinIO or AWS S3) | PALM I/O files, tiles, reports |
| PDF generation | WeasyPrint | Template-driven, handles maps and tables |
| Monitoring | Prometheus + Grafana | Metrics, alerting |
| Auth | JWT + refresh tokens | Stateless, standard |

## Data Flow

```
User edits scenario in browser
        │
        ▼
API validates and stores scenario JSON (PostgreSQL)
        │
        ▼
Translation layer: scenario JSON → palm_csd inputs → static driver (NetCDF)
                   scenario JSON → namelist (Jinja2 template)
                   scenario JSON → dynamic driver selection
        │
        ▼
Validation engine: physics checks, resource estimation, data quality assessment
        │
        ▼
Job queue (Celery): submit PALM job to Linux worker
        │
        ▼
PALM runner: mpirun palm, parse stdout for progress, detect completion
        │
        ▼
Post-processing: xarray extraction → pythermalcomfort (PET/UTCI) → classification → tiles → statistics
        │
        ▼
Comparison engine (if multi-scenario): difference grids, deltas, threshold impact
        │
        ▼
Report engine: HTML template → WeasyPrint → PDF with all 11 sections
        │
        ▼
Results served to browser: map tiles, statistics, summary cards, PDF download
```

## Scaling Path

| Stage | Architecture | Capacity |
|---|---|---|
| Single-server | API + DB + PALM on one Linux machine | 1 concurrent run |
| Separated | API on VM, PALM on dedicated compute | Multiple workers |
| Cloud-burst | API on containers, PALM on on-demand HPC | Elastic |
| Multi-tenant | DB-level isolation, per-tenant quotas | Production SaaS |

## Key Interfaces

- **Scenario JSON ↔ Translation Layer** — The scenario schema is the contract between frontend and backend pipeline. All intervention types must be representable in this schema.
- **Translation Layer ↔ palm_csd** — Our code prepares geodata inputs, invokes palm_csd, and reads its NetCDF output. We extend (not replace) palm_csd for intervention elements it doesn't natively handle.
- **PALM Runner ↔ PALM binary** — File I/O only. Write inputs to job directory, execute via subprocess, read outputs. No dynamic linking, no library calls.
- **Post-Processing ↔ Result API** — Post-processing writes GeoTIFFs and statistics to object store. API serves tile URLs and JSON statistics to frontend.

## Detailed Module Descriptions

See IMPLEMENTATION_PLAN.md §6 for full module-by-module specification.
