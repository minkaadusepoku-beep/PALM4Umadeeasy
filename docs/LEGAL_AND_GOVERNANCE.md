# PALM4Umadeeasy — Legal and Governance Framework

**Version:** 1.0  
**Date:** 2026-04-09  
**Author:** Minka Aduse-Poku  
**Status:** Working assumptions — formal legal review required before commercial deployment

**Important:** Every statement in this document is a working assumption or a question, not a legal conclusion. Commercial deployment requires formal legal review of all items marked **[LEGAL REVIEW REQUIRED]**.

---

## 1. PALM License (GPL-3.0)

### 1.1 License Terms

PALM source code is licensed under GPL-3.0.

### 1.2 Our Integration Pattern

Our product does not modify PALM source code. We compile the unmodified PALM binary and execute it as a separate process. Our wrapper code (API, frontend, translation layer, post-processing) communicates with PALM exclusively through file I/O (writing input files, reading output files).

**Working assumption:** Under this integration pattern, our code is a "separate work" and is not required to be GPL-licensed. This is a standard pattern (similar to a web application calling an external command-line tool), but it must be confirmed.

### 1.3 SaaS Consideration

GPL-3.0 (unlike AGPL-3.0) does not require source distribution for software accessed over a network. If we run PALM as a backend service and users interact via browser, we are likely not distributing the PALM binary to users.

### 1.4 Docker Distribution

**[LEGAL REVIEW REQUIRED]** If we distribute Docker images containing the compiled PALM binary (e.g., for self-hosted deployment), GPL-3.0 requires making the corresponding PALM source available to recipients. This is already satisfied by PALM's public source repository, but the mechanism (written offer, source link, etc.) needs to comply formally.

### 1.5 Open Question

**[LEGAL REVIEW REQUIRED]** Confirm that the "separate work" interpretation holds for our specific integration pattern (file I/O, subprocess execution). This is a standard pattern but should be confirmed by a lawyer experienced in GPL.

---

## 2. PALM-4U GUI Code

### 2.1 Decision: No Code Reuse

The PALM-4U web GUI was developed under BMBF funding (UC² programme). We do not reuse any PALM-4U GUI source code. We build our frontend and backend independently.

### 2.2 Rationale

- **Legal:** BMBF-funded code may have specific terms regarding open-access publication, derivative works, or commercial reuse. We must not use code whose license has not been explicitly reviewed and cleared.
- **Design:** The GUI serves a different user (researcher vs. planner) with a different interaction model. Reusing components would import the wrong UX.

### 2.3 What Is Acceptable

Studying published papers, public documentation, and public API descriptions about the PALM-4U GUI is acceptable (these are published works, not code).

### 2.4 Open Question

**[LEGAL REVIEW REQUIRED]** Before reading PALM-4U GUI source code (even for reference), verify its license. Do not assume it is freely available simply because it was publicly funded.

---

## 3. palm_csd License

### 3.1 Status

palm_csd is part of the PALM model system and is presumably GPL-3.0. Per ADR-002, we do not use palm_csd — we build our own static driver generator targeting the PIDS specification directly.

### 3.2 Reference Data Reuse

We reference palm_csd's tree species parameter database (87 species with LAD/BAD profiles) as factual data, not copyrightable code. PALM parameter mappings (vegetation types, pavement types, building types) are PALM-defined constants.

### 3.3 Open Question

**[LEGAL REVIEW REQUIRED]** Confirm palm_csd's exact license terms. Our non-use of palm_csd as a dependency makes this lower priority, but the reference data reuse should be confirmed as acceptable.

---

## 4. Data Licensing

| Source | License | Commercial Use | Attribution Required | Review Status |
|---|---|---|---|---|
| OpenStreetMap | ODbL 1.0 | Yes | Yes: "© OpenStreetMap contributors" | Established — no review needed |
| Copernicus DEM | Copernicus licence (free, open) | Yes | Yes: "Contains Copernicus data" | Established — no review needed |
| German state CityGML LoD2 | Varies by state | Depends on state | Verify per state | **[LEGAL REVIEW REQUIRED]** per-state before enabling auto-fetch |
| DWD meteorological data | GeoNutzV (free since 2017) | Yes | Attribution for DWD-derived data | **[LEGAL REVIEW REQUIRED]** Can we redistribute pre-processed forcing templates derived from DWD TRY data? |
| pythermalcomfort | MIT licence | Yes | No specific attribution required | No review needed |

### 4.1 German State CityGML Data

NRW uses dl-de/zero-2-0 (essentially public domain). Berlin and Hamburg have open data policies. Other states vary. Each state must be verified individually before the platform enables auto-fetch for that state.

### 4.2 DWD Data

DWD data has been free for commercial use since 2017 under GeoNutzV. The open question is whether our pre-processed forcing templates (derived from DWD TRY data) constitute redistribution requiring specific attribution or terms compliance.

---

## 5. Privacy and GDPR

### 5.1 Personal Data Collected

User accounts store:
- Name, email address
- Hashed password (bcrypt/argon2)
- Project associations
- Usage logs (audit trail)

No sensitive personal data appears in simulation inputs or outputs.

### 5.2 GDPR Requirements

Operating in the EU requires:
- Privacy policy
- Data processing agreement (DPA) template for B2B clients
- Right to access and deletion
- Data export on request

### 5.3 Data Residency

**[LEGAL REVIEW REQUIRED]** If deployed on cloud infrastructure, confirm EU data residency. If self-hosted by client, GDPR responsibility shifts to them (but we should provide a DPA template).

---

## 6. Disclaimer Policy

### 6.1 Standard Disclaimer

Every report, every result screen, and the product's terms of service includes:

> "This analysis is based on numerical simulation using the PALM model system. Results are model-based estimates that depend on input data quality, model parameterisation, and spatial resolution. They do not constitute measurements or guarantees. This tool is intended as a decision-support aid and does not replace professional judgement or site-specific assessment. The operators accept no liability for decisions made based on simulation results."

### 6.2 Enforcement

- Non-removable by users and non-suppressible by any UI setting
- Appears in every PDF report footer (page-level)
- Appears on every result screen in the web application
- Included in the product's terms of service
- The non-PALM advisory layer (facade greening) carries an additional advisory banner

### 6.3 Open Question

**[LEGAL REVIEW REQUIRED]** Disclaimer wording should be reviewed by a lawyer for the target jurisdiction (Germany: Haftungsausschluss). Standard product liability and professional negligence considerations apply.

---

## 7. Audit Trail

### 7.1 What Is Logged

**[IMPLEMENTED]**

| Action | Data Recorded |
|---|---|
| Scenario edits | Who, when, JSON diff of change |
| Building geometry edits | Who, when, edit type, resource_type="scenario_buildings" |
| Run submissions | Who, when, scenario version, validation result |
| Report generation | Who, when, which run, which format |
| Expert overrides (Phase 4) | Parameter name, old value, new value, user, timestamp |
| Authentication events | Login, failed login, registration |

### 7.2 Properties

- **Append-only.** Audit log entries cannot be modified or deleted by any user role.
- **Retained for project lifetime.** No automatic expiry.
- **Queryable.** Admin endpoints support filtering by action type, user, and date range.

---

## 8. Release Standards

### 8.1 Pre-Release Checklist

No release without:

- [ ] All test suites passing (unit, integration, end-to-end)
- [ ] PALM reference case validated against expected output (when Linux environment available)
- [ ] PDF report regression clear
- [ ] At least one full end-to-end scenario on the release build
- [ ] CHANGELOG updated
- [ ] Version number incremented (semver)
- [ ] PALM version compatibility noted

### 8.2 Documentation Requirements

| Document | Audience | Standard |
|---|---|---|
| User guide | Planners, consultants | Task-oriented, screenshots, no jargon |
| Methodology document | Peer reviewers, clients | Citable, describes all computation methods |
| Admin guide | IT staff | Deployment, backup, monitoring, troubleshooting |
| API documentation | Developers | Auto-generated from FastAPI OpenAPI spec |
| ADRs | Internal | One per significant decision |

---

## 9. Pre-Commercialisation Legal Checklist

Before any commercial deployment (paid access, client deliverables, or public SaaS):

- [ ] GPL interpretation for PALM integration reviewed by lawyer
- [ ] palm_csd license confirmed and reference data reuse reviewed
- [ ] PALM-4U GUI code confirmed as not used (build-from-scratch documentation)
- [ ] Per-state data licensing reviewed for all supported German states
- [ ] DWD data redistribution rights confirmed for forcing templates
- [ ] GDPR compliance reviewed (privacy policy, DPA template, data residency)
- [ ] Liability disclaimer reviewed for German law (Haftungsausschluss)
- [ ] Terms of service drafted and reviewed
- [ ] Impressum requirements met (if web-facing)

---

## 10. Governance Principles

These principles (from ADR-000) govern all decisions:

1. **Not a generic PALM wrapper** — intervention-centric decision support only
2. **Comparison is first-class** — every architectural decision evaluated against comparison quality
3. **Confidence propagation is mandatory** — non-suppressible, non-removable
4. **palm_csd bypassed** — custom PIDS generation (per ADR-002)
5. **No PALM-4U GUI code reuse** — legal and design separation
6. **Expert overrides are later-layer** — core constrained workflow must prove itself first
7. **Scientific defensibility is a product requirement** — every method traceable to published source

These principles are reviewed at each phase exit. Changes require explicit, documented reasoning via new ADR.

---

*End of Legal and Governance Framework v1.0*
