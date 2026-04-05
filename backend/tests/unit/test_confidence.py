"""Unit tests for the confidence propagation engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.confidence.engine import (
    assess_confidence, format_confidence_paragraph,
    ConfidenceLevel,
)
from src.models.scenario import DataQualityTier, DataSource, DomainData
from tests.fixtures.scenarios import make_valid_baseline


class TestConfidenceAssessment:
    def test_screening_tier(self):
        scenario = make_valid_baseline()
        # Default data sources are screening
        conf = assess_confidence(scenario)
        assert conf.level == ConfidenceLevel.INDICATIVE
        assert conf.tier == DataQualityTier.SCREENING
        assert "screening" in conf.headline.lower()

    def test_project_tier(self):
        scenario = make_valid_baseline()
        scenario.data_sources = DomainData(
            buildings=DataSource(
                source_type="citygml_lod2",
                quality_tier=DataQualityTier.PROJECT,
            ),
            terrain=DataSource(
                source_type="lidar_dem",
                quality_tier=DataQualityTier.PROJECT,
            ),
        )
        conf = assess_confidence(scenario)
        assert conf.level == ConfidenceLevel.QUANTITATIVE

    def test_weakest_link_applies(self):
        scenario = make_valid_baseline()
        scenario.data_sources = DomainData(
            buildings=DataSource(
                source_type="citygml_lod2",
                quality_tier=DataQualityTier.RESEARCH,
            ),
            terrain=DataSource(
                source_type="osm",
                quality_tier=DataQualityTier.SCREENING,
            ),
        )
        conf = assess_confidence(scenario)
        # Screening terrain drags everything down
        assert conf.level == ConfidenceLevel.INDICATIVE

    def test_format_paragraph_contains_key_info(self):
        scenario = make_valid_baseline()
        conf = assess_confidence(scenario)
        text = format_confidence_paragraph(conf)
        assert "Suitable for" in text
        assert "Not suitable for" in text
        assert len(conf.caveats) > 0

    def test_caveats_include_stub_warning(self):
        scenario = make_valid_baseline()
        conf = assess_confidence(scenario)
        assert any("stub" in c.lower() for c in conf.caveats)
