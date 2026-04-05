"""Catalogue loader: reads species, surfaces, and comfort thresholds from JSON."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import CATALOGUE_DIR


@lru_cache(maxsize=1)
def load_species() -> dict[str, Any]:
    with open(CATALOGUE_DIR / "species.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["species"]


@lru_cache(maxsize=1)
def load_surfaces() -> dict[str, Any]:
    with open(CATALOGUE_DIR / "surfaces.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["surfaces"]


@lru_cache(maxsize=1)
def load_comfort_thresholds() -> dict[str, Any]:
    with open(CATALOGUE_DIR / "comfort_thresholds.json", encoding="utf-8") as f:
        return json.load(f)


def get_species(species_id: str) -> dict[str, Any]:
    species = load_species()
    if species_id not in species:
        raise KeyError(f"Unknown species: {species_id}. Available: {list(species.keys())}")
    return species[species_id]


def get_surface(surface_id: str) -> dict[str, Any]:
    surfaces = load_surfaces()
    if surface_id not in surfaces:
        raise KeyError(f"Unknown surface: {surface_id}. Available: {list(surfaces.keys())}")
    return surfaces[surface_id]


def classify_pet(pet_value: float) -> dict[str, str]:
    thresholds = load_comfort_thresholds()["pet_vdi3787"]
    for band in thresholds:
        lo = band["min"] if band["min"] is not None else float("-inf")
        hi = band["max"] if band["max"] is not None else float("inf")
        if lo <= pet_value < hi:
            return {"perception": band["perception"], "stress": band["stress"],
                    "color": band["color"]}
    return {"perception": "Unknown", "stress": "Unknown", "color": "#808080"}
