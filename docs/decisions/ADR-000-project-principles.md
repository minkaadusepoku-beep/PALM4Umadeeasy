# ADR-000: Governing Project Principles

**Status:** Accepted
**Date:** 2026-03-28
**Author:** Minka Aduse-Poku

## Context

PALM4Umadeeasy is a product built around the PALM/PALM-4U urban microclimate model. Before any implementation begins, the following principles must be established to prevent scope drift, misidentification of the product, and architectural mistakes that would be expensive to reverse.

These principles govern all subsequent ADRs, implementation decisions, and feature prioritisation.

## Principles

### 1. This is not a generic PALM browser wrapper

The product is a **consultant-grade decision-support platform specialized for intervention testing** in urban green/blue infrastructure and outdoor comfort. It answers planning questions about the microclimate effects of specific interventions (trees, surfaces, green roofs, later façade greening, water features).

It is not a general-purpose PALM configuration tool. It does not aim to expose all PALM capabilities. Features are included because they serve intervention testing and comparison — not because PALM supports them.

### 2. Comparison is a first-class operation

The core product output is not a single simulation result. It is a **comparison**: baseline vs. intervention, or option A vs. option B. Difference maps, delta statistics, threshold impact analysis, and ranked zone improvements are primary outputs, not afterthoughts.

Every architectural decision must consider: does this make comparison better, worse, or irrelevant?

### 3. Confidence propagation is mandatory and non-suppressible

Input data quality is tagged (screening / project / research grade). This tag propagates through the entire pipeline to every result map, every statistic, every summary, and every report page.

Confidence messaging cannot be removed, hidden, or overridden by any user role. Screening-grade results carry visible indicators. Report language adjusts hedging based on data tier. This is a structural product requirement, not a nice-to-have.

### 4. palm_csd is the default preprocessing backbone

The PALM project's own static driver creation tool (palm_csd) is the default choice for generating PALM input files from geodata. Our translation layer wraps and extends palm_csd — it does not replace it unless Phase 0 evaluation identifies a documented hard blocker.

Rationale: palm_csd is maintained by the PALM community, handles complex rasterisation logic (buildings, terrain, vegetation), and is validated against PALM's expected input format. Rebuilding this from scratch carries significant risk and no clear advantage.

If a blocker is found, it must be documented in a separate ADR before proceeding with custom implementation.

### 5. No PALM-4U GUI code reuse

We do not reuse, adapt, or derive from any PALM-4U web GUI source code. This is both a legal precaution (BMBF-funded code may have restrictive terms) and a design decision (the GUI serves researchers, not planners — its interaction model would import the wrong UX).

We may study published papers, public documentation, and public API descriptions about the PALM-4U GUI. We do not read, copy, or adapt its source code.

This principle stands until a formal legal review explicitly clears specific components for reuse — at which point a new ADR would be written.

### 6. Expert overrides are a later-layer feature

The product's core workflow is the guided, constrained, planner-facing path: scenario templates, species/surface pickers, validated defaults, comparison reports.

Expert overrides (namelist inspection, custom forcing, raw output access, parameter editing) are a controlled addition built on top of the stable core workflow. They are targeted at Phase 4, not Phase 1 or 2.

Rationale: if expert overrides are built early, they will become the de facto product and the constrained workflow will atrophy. The product must prove it works for planners before it accommodates power users. "PALM with a nicer face" is an explicit anti-goal.

### 7. Scientific defensibility is a product requirement

Every comfort index computation must be traceable to a published method with a full citation. Every classification must reference a standard (VDI 3787, Lawson/NEN 8100). Every report must include a methodology section suitable for peer review.

The product's credibility depends on being scientifically honest — including about its limitations. Confidence messaging (Principle 3) is one expression of this. The methodology document must be citable. Results must be reproducible given the same inputs and software versions.

## Consequences

- Feature requests are evaluated against these principles before acceptance.
- Any proposed deviation requires a new ADR documenting the context, the deviation, and the justification.
- These principles are referenced in code review: changes that violate them are blocked.

## Review

These principles should be revisited at each phase exit to confirm they still serve the product's direction. They are not immutable — but changing them requires explicit, documented reasoning.
