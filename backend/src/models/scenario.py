"""
Deterministic scenario schema for PALM4Umadeeasy.

This is the contract between the frontend and the entire backend pipeline.
Given the same scenario JSON + catalogue version, the translation layer
must produce identical PALM inputs.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from ..config import SCHEMA_VERSION


class DataQualityTier(str, Enum):
    SCREENING = "screening"
    PROJECT = "project"
    RESEARCH = "research"


class ForcingArchetype(str, Enum):
    TYPICAL_HOT_DAY = "typical_hot_day"
    HEAT_WAVE_DAY = "heat_wave_day"
    MODERATE_SUMMER_DAY = "moderate_summer_day"
    WARM_NIGHT = "warm_night"


class ScenarioType(str, Enum):
    BASELINE = "baseline"
    SINGLE_INTERVENTION = "single_intervention"
    CONCEPT_COMPARISON = "concept_comparison"


# --- Domain ---

class BoundingBox(BaseModel):
    west: float = Field(..., description="Western longitude or UTM easting [m]")
    south: float = Field(..., description="Southern latitude or UTM northing [m]")
    east: float = Field(..., description="Eastern longitude or UTM easting [m]")
    north: float = Field(..., description="Northern latitude or UTM northing [m]")

    @model_validator(mode="after")
    def check_bounds(self):
        if self.east <= self.west:
            raise ValueError("east must be greater than west")
        if self.north <= self.south:
            raise ValueError("north must be greater than south")
        return self


class DomainConfig(BaseModel):
    bbox: BoundingBox
    resolution_m: float = Field(10.0, ge=1.0, le=50.0)
    epsg: int = Field(25832, description="CRS EPSG code (UTM)")
    nz: int = Field(40, ge=10, le=200)
    dz: float = Field(2.0, ge=0.5, le=10.0)

    @property
    def nx(self) -> int:
        return max(1, round((self.bbox.east - self.bbox.west) / self.resolution_m))

    @property
    def ny(self) -> int:
        return max(1, round((self.bbox.north - self.bbox.south) / self.resolution_m))


# --- Data sources ---

class DataSource(BaseModel):
    source_type: str = Field(..., description="e.g. 'osm', 'citygml_lod2', 'lidar_dem', 'manual'")
    quality_tier: DataQualityTier
    description: str = ""


class DomainData(BaseModel):
    buildings: DataSource = Field(
        default_factory=lambda: DataSource(
            source_type="osm", quality_tier=DataQualityTier.SCREENING,
            description="OpenStreetMap building footprints"
        )
    )
    terrain: DataSource = Field(
        default_factory=lambda: DataSource(
            source_type="copernicus_dem_30m", quality_tier=DataQualityTier.SCREENING,
            description="Copernicus GLO-30 DEM"
        )
    )
    vegetation: DataSource = Field(
        default_factory=lambda: DataSource(
            source_type="manual", quality_tier=DataQualityTier.PROJECT,
            description="User-placed elements"
        )
    )

    @property
    def effective_tier(self) -> DataQualityTier:
        tiers = [self.buildings.quality_tier, self.terrain.quality_tier,
                 self.vegetation.quality_tier]
        priority = [DataQualityTier.SCREENING, DataQualityTier.PROJECT, DataQualityTier.RESEARCH]
        for t in priority:
            if t in tiers:
                return t
        return DataQualityTier.SCREENING


# --- Intervention elements ---

class TreePlacement(BaseModel):
    species_id: str = Field(..., description="Key into species catalogue")
    x: float = Field(..., description="UTM easting [m]")
    y: float = Field(..., description="UTM northing [m]")
    height_m: Optional[float] = Field(None, ge=1.0, le=40.0,
                                       description="Override species default if set")
    crown_diameter_m: Optional[float] = Field(None, ge=1.0, le=25.0)


class SurfaceChange(BaseModel):
    surface_type_id: str = Field(..., description="Key into surface catalogue")
    vertices: list[tuple[float, float]] = Field(..., min_length=3,
                                                 description="Polygon vertices [(x,y), ...] in UTM [m]")


class GreenRoof(BaseModel):
    building_id: str = Field(..., description="Identifier of the target building")
    substrate_depth_m: float = Field(0.10, ge=0.05, le=0.50)
    vegetation_type: str = Field("sedum", description="extensive or intensive type")


# --- Simulation settings ---

class SimulationSettings(BaseModel):
    forcing: ForcingArchetype = ForcingArchetype.TYPICAL_HOT_DAY
    simulation_hours: float = Field(6.0, ge=1.0, le=24.0)
    output_interval_s: float = Field(1800.0, ge=300.0, le=7200.0)


# --- Top-level scenario ---

class Scenario(BaseModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    scenario_type: ScenarioType = ScenarioType.BASELINE

    domain: DomainConfig
    data_sources: DomainData = Field(default_factory=DomainData)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)

    trees: list[TreePlacement] = Field(default_factory=list)
    surface_changes: list[SurfaceChange] = Field(default_factory=list)
    green_roofs: list[GreenRoof] = Field(default_factory=list)

    def fingerprint(self) -> str:
        """Deterministic hash of the scenario for reproducibility tracking."""
        serialised = self.model_dump_json(indent=None)
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]

    @property
    def effective_data_tier(self) -> DataQualityTier:
        return self.data_sources.effective_tier

    def to_deterministic_json(self) -> str:
        """Serialise with sorted keys for deterministic output."""
        data = self.model_dump(mode="json")
        return json.dumps(data, sort_keys=True, ensure_ascii=False)


class ComparisonRequest(BaseModel):
    baseline: Scenario
    intervention: Scenario
    name: str = Field(..., min_length=1)
    description: str = ""
