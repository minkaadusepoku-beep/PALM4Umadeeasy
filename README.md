# PALM4Umadeeasy

Consultant-grade decision-support platform for urban microclimate intervention testing, built around PALM/PALM-4U.

## What This Is

A browser-based tool that lets urban planners, landscape architects, and climate adaptation consultants test green/blue infrastructure interventions (street trees, surface changes, green roofs, later façade greening) and receive confidence-aware comparison reports — without touching Linux, PALM namelists, or raw NetCDF output.

## What This Is Not

- Not a generic browser wrapper for PALM
- Not a research simulation configuration tool
- Not "PALM with a nicer face"

## Status

**Pre-build.** Planning and documentation scaffold only. No product code yet.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the full master plan.

## Repository Structure

```
PALM4Umadeeasy/
├── docs/                  Documentation and architecture decisions
│   ├── architecture.md    System architecture reference
│   └── decisions/         Architecture Decision Records (ADRs)
├── frontend/              Next.js application (not yet started)
├── backend/               FastAPI application (not yet started)
├── palm/                  PALM compilation docs, reference cases, forcing templates
├── catalogues/            Species, surfaces, vegetation, comfort thresholds (JSON)
└── deploy/                Docker, nginx, systemd, terraform configs
```

## Key Documents

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Production master plan (v3.0, approved)
- [docs/decisions/ADR-000-project-principles.md](docs/decisions/ADR-000-project-principles.md) — Governing design principles
- [docs/architecture.md](docs/architecture.md) — System architecture reference

## Next Step

Phase 0: Prove PALM compiles, runs, and that palm_csd can serve as our preprocessing backbone. See IMPLEMENTATION_PLAN.md §Phase 0 for exit criteria.
