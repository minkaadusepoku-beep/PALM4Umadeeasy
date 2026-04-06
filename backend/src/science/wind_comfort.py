"""Wind comfort classification using Lawson criteria.

Lawson LDDC (London Docklands Development Corporation) criteria classify
pedestrian wind comfort based on mean wind speed thresholds:

  Category          | Threshold (m/s) | Description
  ------------------|-----------------|---------------------------
  Sitting long      | < 2.5           | Comfortable for long sitting
  Sitting short     | < 4.0           | Comfortable for short sitting
  Standing          | < 6.0           | Comfortable for standing
  Walking           | < 8.0           | Comfortable for walking
  Uncomfortable     | < 10.0          | Uncomfortable but tolerable
  Dangerous         | >= 10.0         | Dangerous for pedestrians

Reference: Lawson, T.V. (1978). The wind content of the built environment.
"""

from dataclasses import dataclass


@dataclass
class LawsonCategory:
    name: str
    max_wind_speed: float  # upper threshold in m/s
    color: str  # hex color for mapping
    description: str


LAWSON_CATEGORIES = [
    LawsonCategory("sitting_long", 2.5, "#1a9850", "Comfortable for long outdoor sitting"),
    LawsonCategory("sitting_short", 4.0, "#91cf60", "Comfortable for short outdoor sitting"),
    LawsonCategory("standing", 6.0, "#d9ef8b", "Comfortable for standing / entrance areas"),
    LawsonCategory("walking", 8.0, "#fee08b", "Comfortable for walking / leisure strolling"),
    LawsonCategory("uncomfortable", 10.0, "#fc8d59", "Uncomfortable — not suitable for regular pedestrian use"),
    LawsonCategory("dangerous", float("inf"), "#d73027", "Dangerous for pedestrians — safety concern"),
]


def classify_wind_speed(wind_speed_ms: float) -> LawsonCategory:
    """Classify a wind speed value into a Lawson category."""
    for cat in LAWSON_CATEGORIES:
        if wind_speed_ms < cat.max_wind_speed:
            return cat
    return LAWSON_CATEGORIES[-1]


def classify_grid(wind_speeds: list[list[float]]) -> dict:
    """Classify a 2D grid of wind speeds.

    Returns category fractions, dominant category, and per-cell classification.
    """
    total = 0
    counts: dict[str, int] = {cat.name: 0 for cat in LAWSON_CATEGORIES}
    classified: list[list[str]] = []

    for row in wind_speeds:
        row_classes = []
        for speed in row:
            cat = classify_wind_speed(speed)
            counts[cat.name] += 1
            total += 1
            row_classes.append(cat.name)
        classified.append(row_classes)

    fractions = {name: count / total if total > 0 else 0.0 for name, count in counts.items()}
    dominant = max(fractions, key=lambda k: fractions[k]) if total > 0 else "unknown"

    return {
        "category_fractions": fractions,
        "dominant_category": dominant,
        "total_cells": total,
        "classified_grid": classified,
    }


def get_category_legend() -> list[dict]:
    """Return the Lawson category legend for UI display."""
    return [
        {
            "name": cat.name,
            "max_wind_speed": cat.max_wind_speed if cat.max_wind_speed != float("inf") else None,
            "color": cat.color,
            "description": cat.description,
        }
        for cat in LAWSON_CATEGORIES
    ]


def generate_stub_wind_comfort(nx: int = 50, ny: int = 50, seed: int = 42) -> dict:
    """Generate synthetic wind comfort data for stub/dev mode.

    Produces a realistic-looking wind field with spatial variation.
    """
    import random
    rng = random.Random(seed)

    wind_speeds: list[list[float]] = []
    for y in range(ny):
        row = []
        for x in range(nx):
            # Base wind + spatial variation (higher near edges = building acceleration)
            base = 3.5
            edge_factor = min(x, nx - 1 - x, y, ny - 1 - y) / (min(nx, ny) / 4)
            edge_factor = min(edge_factor, 1.0)
            speed = base + (1 - edge_factor) * 4.0 + rng.gauss(0, 0.8)
            speed = max(0.1, speed)
            row.append(round(speed, 2))
        wind_speeds.append(row)

    classification = classify_grid(wind_speeds)
    classification["wind_speeds"] = wind_speeds
    classification["legend"] = get_category_legend()
    classification["metadata"] = {
        "source": "stub",
        "nx": nx,
        "ny": ny,
        "note": "Synthetic wind field for development — not from PALM simulation",
    }
    return classification
