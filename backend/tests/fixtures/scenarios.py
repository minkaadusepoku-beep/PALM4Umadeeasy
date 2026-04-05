"""
Test scenario fixtures for PALM4Umadeeasy.

Provides valid and invalid scenarios for unit and integration testing.
"""

from __future__ import annotations

from src.models.scenario import (
    Scenario, DomainConfig, BoundingBox, SimulationSettings,
    TreePlacement, SurfaceChange, GreenRoof,
    ForcingArchetype, ScenarioType, DataQualityTier,
    DomainData, DataSource, ComparisonRequest,
)


def make_valid_baseline(name: str = "Test Baseline") -> Scenario:
    """A minimal valid baseline scenario for Cologne city center."""
    return Scenario(
        name=name,
        scenario_type=ScenarioType.BASELINE,
        domain=DomainConfig(
            bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            resolution_m=10.0,
            epsg=25832,
            nz=40,
            dz=2.0,
        ),
        simulation=SimulationSettings(
            forcing=ForcingArchetype.TYPICAL_HOT_DAY,
            simulation_hours=6.0,
            output_interval_s=1800.0,
        ),
    )


def make_valid_intervention(name: str = "Test Intervention") -> Scenario:
    """A valid intervention scenario with trees and surface changes."""
    return Scenario(
        name=name,
        scenario_type=ScenarioType.SINGLE_INTERVENTION,
        domain=DomainConfig(
            bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            resolution_m=10.0,
            epsg=25832,
            nz=40,
            dz=2.0,
        ),
        simulation=SimulationSettings(
            forcing=ForcingArchetype.TYPICAL_HOT_DAY,
            simulation_hours=6.0,
            output_interval_s=1800.0,
        ),
        trees=[
            TreePlacement(species_id="tilia_cordata", x=356250, y=5645250),
            TreePlacement(species_id="platanus_x_acerifolia", x=356300, y=5645300,
                          height_m=18.0, crown_diameter_m=12.0),
        ],
        surface_changes=[
            SurfaceChange(
                surface_type_id="grass",
                vertices=[
                    (356100, 5645100), (356200, 5645100),
                    (356200, 5645200), (356100, 5645200),
                ],
            ),
        ],
    )


def make_comparison_request() -> ComparisonRequest:
    """A valid comparison request."""
    return ComparisonRequest(
        baseline=make_valid_baseline(),
        intervention=make_valid_intervention(),
        name="Test Comparison",
        description="Testing tree planting effect on thermal comfort",
    )


# --- Invalid scenarios for validation testing ---
# Each returns (scenario_or_kwargs, expected_error_code_substring)

INVALID_SCENARIOS = [
    # 1. Domain too narrow
    (
        "domain_too_narrow",
        lambda: Scenario(
            name="Too narrow",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356050, north=5645500),
                resolution_m=10.0,
            ),
        ),
        "domain.too_narrow",
    ),
    # 2. Domain too short
    (
        "domain_too_short",
        lambda: Scenario(
            name="Too short",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645050),
                resolution_m=10.0,
            ),
        ),
        "domain.too_short",
    ),
    # 3. Domain too large
    (
        "domain_too_large",
        lambda: Scenario(
            name="Too large",
            domain=DomainConfig(
                bbox=BoundingBox(west=0, south=0, east=10000, north=10000),
                resolution_m=1.0,
            ),
        ),
        "domain.too_large",
    ),
    # 4. Unknown tree species
    (
        "unknown_species",
        lambda: Scenario(
            name="Bad tree",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            trees=[TreePlacement(species_id="unicorn_tree", x=356250, y=5645250)],
        ),
        "unknown_species",
    ),
    # 5. Tree outside domain
    (
        "tree_outside_domain",
        lambda: Scenario(
            name="Tree outside",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            trees=[TreePlacement(species_id="tilia_cordata", x=999999, y=999999)],
        ),
        "outside_domain",
    ),
    # 6. Unknown surface type
    (
        "unknown_surface",
        lambda: Scenario(
            name="Bad surface",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            surface_changes=[
                SurfaceChange(
                    surface_type_id="lava_rock",
                    vertices=[(356100, 5645100), (356200, 5645100), (356200, 5645200)],
                ),
            ],
        ),
        "unknown_surface",
    ),
    # 7. Surface polygon outside domain
    (
        "surface_outside_domain",
        lambda: Scenario(
            name="Surface outside",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            surface_changes=[
                SurfaceChange(
                    surface_type_id="grass",
                    vertices=[(999000, 999000), (999100, 999000), (999100, 999100)],
                ),
            ],
        ),
        "outside_domain",
    ),
    # 8. Output interval exceeds runtime
    (
        "interval_exceeds_runtime",
        lambda: Scenario(
            name="Bad interval",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            simulation=SimulationSettings(
                simulation_hours=1.0,
                output_interval_s=7200.0,
            ),
        ),
        "interval_exceeds_runtime",
    ),
    # 9. Short simulation warning
    (
        "short_simulation",
        lambda: Scenario(
            name="Short sim",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            simulation=SimulationSettings(simulation_hours=1.0, output_interval_s=300.0),
        ),
        "short_runtime",
    ),
    # 10. Tree height exceeds species max
    (
        "tree_too_tall",
        lambda: Scenario(
            name="Giant tree",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            trees=[TreePlacement(species_id="tilia_cordata", x=356250, y=5645250, height_m=40.0)],
        ),
        "height_exceeds",
    ),
    # 11. Crown diameter exceeds species max
    (
        "crown_too_wide",
        lambda: Scenario(
            name="Wide crown",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            trees=[TreePlacement(species_id="tilia_cordata", x=356250, y=5645250, crown_diameter_m=25.0)],
        ),
        "crown_exceeds",
    ),
    # 12. Green roof with unknown vegetation type
    (
        "green_roof_bad_type",
        lambda: Scenario(
            name="Bad green roof",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            green_roofs=[GreenRoof(building_id="B1", vegetation_type="tropical_jungle")],
        ),
        "unknown_vegetation_type",
    ),
    # 13. Surface polygon too small for grid
    (
        "surface_too_small",
        lambda: Scenario(
            name="Tiny surface",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
                resolution_m=10.0,
            ),
            surface_changes=[
                SurfaceChange(
                    surface_type_id="grass",
                    vertices=[(356100, 5645100), (356101, 5645100), (356101, 5645101)],
                ),
            ],
        ),
        "too_small",
    ),
    # 14. Screening tier data quality info
    (
        "screening_data_quality",
        lambda: Scenario(
            name="Screening tier",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            data_sources=DomainData(
                buildings=DataSource(
                    source_type="osm",
                    quality_tier=DataQualityTier.SCREENING,
                ),
            ),
        ),
        "screening_tier",
    ),
    # 15. Odd grid dimensions
    (
        "odd_grid",
        lambda: Scenario(
            name="Odd grid",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356510, north=5645510),
                resolution_m=10.0,
            ),
        ),
        "odd_n",
    ),
    # 16. Overlapping trees
    (
        "overlapping_trees",
        lambda: Scenario(
            name="Overlapping",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
            ),
            trees=[
                TreePlacement(species_id="tilia_cordata", x=356250, y=5645250),
                TreePlacement(species_id="tilia_cordata", x=356251, y=5645250),
            ],
        ),
        "overlap",
    ),
    # 17. Low domain ceiling
    (
        "low_ceiling",
        lambda: Scenario(
            name="Low ceiling",
            domain=DomainConfig(
                bbox=BoundingBox(west=356000, south=5645000, east=356500, north=5645500),
                nz=10,
                dz=2.0,
            ),
        ),
        "low_ceiling",
    ),
]
