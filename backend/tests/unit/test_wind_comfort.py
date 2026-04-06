"""Tests for Lawson wind comfort classification."""

from src.science.wind_comfort import (
    classify_wind_speed,
    classify_grid,
    get_category_legend,
    generate_stub_wind_comfort,
)


class TestClassifyWindSpeed:
    def test_calm(self):
        cat = classify_wind_speed(1.5)
        assert cat.name == "sitting_long"

    def test_moderate(self):
        cat = classify_wind_speed(3.0)
        assert cat.name == "sitting_short"

    def test_standing(self):
        cat = classify_wind_speed(5.0)
        assert cat.name == "standing"

    def test_walking(self):
        cat = classify_wind_speed(7.0)
        assert cat.name == "walking"

    def test_uncomfortable(self):
        cat = classify_wind_speed(9.5)
        assert cat.name == "uncomfortable"

    def test_dangerous(self):
        cat = classify_wind_speed(12.0)
        assert cat.name == "dangerous"

    def test_boundary_exact(self):
        # At exactly 2.5, should be sitting_short (< 2.5 is sitting_long)
        cat = classify_wind_speed(2.5)
        assert cat.name == "sitting_short"


class TestClassifyGrid:
    def test_uniform_grid(self):
        grid = [[1.0, 1.0], [1.0, 1.0]]
        result = classify_grid(grid)
        assert result["dominant_category"] == "sitting_long"
        assert result["total_cells"] == 4
        assert result["category_fractions"]["sitting_long"] == 1.0

    def test_mixed_grid(self):
        grid = [[1.0, 5.0], [9.0, 12.0]]
        result = classify_grid(grid)
        assert result["total_cells"] == 4
        assert sum(result["category_fractions"].values()) > 0.99

    def test_classified_grid_shape(self):
        grid = [[2.0, 4.0, 6.0]]
        result = classify_grid(grid)
        assert len(result["classified_grid"]) == 1
        assert len(result["classified_grid"][0]) == 3


class TestCategoryLegend:
    def test_returns_all_categories(self):
        legend = get_category_legend()
        assert len(legend) == 6
        names = [c["name"] for c in legend]
        assert "sitting_long" in names
        assert "dangerous" in names

    def test_has_colors(self):
        legend = get_category_legend()
        for cat in legend:
            assert cat["color"].startswith("#")


class TestStubGeneration:
    def test_generates_valid_data(self):
        result = generate_stub_wind_comfort(nx=10, ny=10)
        assert "category_fractions" in result
        assert "wind_speeds" in result
        assert "legend" in result
        assert "metadata" in result
        assert result["metadata"]["source"] == "stub"
        assert len(result["wind_speeds"]) == 10
        assert len(result["wind_speeds"][0]) == 10

    def test_deterministic(self):
        r1 = generate_stub_wind_comfort(seed=1)
        r2 = generate_stub_wind_comfort(seed=1)
        assert r1["wind_speeds"] == r2["wind_speeds"]
