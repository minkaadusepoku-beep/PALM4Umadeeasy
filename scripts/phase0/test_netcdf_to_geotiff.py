"""
Phase 0 proof: Can we read a PALM-like NetCDF and write a GeoTIFF?

This script creates a synthetic NetCDF file mimicking PALM bio-met output
(2D thermal comfort field), reads it back, and writes it as a GeoTIFF.
This proves the Python I/O path without requiring an actual PALM run.
"""

import sys
import numpy as np
import netCDF4 as nc
import rasterio
from rasterio.transform import from_bounds
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# --- Step 1: Create synthetic PALM-like NetCDF ---

NCFILE = OUTPUT_DIR / "synthetic_palm_xy.nc"
TIFFILE = OUTPUT_DIR / "pet_result.tif"

# Domain: 50x40 grid cells at 10m resolution = 500m x 400m
nx, ny = 50, 40
dx, dy = 10.0, 10.0

# Fake origin (Cologne, UTM zone 32N, EPSG:25832)
origin_x = 356000.0  # easting
origin_y = 5645000.0  # northing

# Create synthetic PET field (°C): hot in center, cooler at edges with trees
np.random.seed(42)
y_idx, x_idx = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
# Base: 35°C across domain
pet = np.full((ny, nx), 35.0, dtype=np.float32)
# Hot spot in center
cx, cy = nx // 2, ny // 2
dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
pet += 5.0 * np.exp(-dist / 10.0)
# Cooler patch (simulating tree shade effect)
tree_zone = (x_idx > 10) & (x_idx < 20) & (y_idx > 15) & (y_idx < 25)
pet[tree_zone] -= 6.0
# Add small noise
pet += np.random.normal(0, 0.3, pet.shape).astype(np.float32)

print(f"Synthetic PET field: shape={pet.shape}, min={pet.min():.1f}, max={pet.max():.1f}, mean={pet.mean():.1f}")

# Write as NetCDF mimicking PALM output structure
with nc.Dataset(str(NCFILE), "w", format="NETCDF4") as ds:
    ds.Conventions = "CF-1.7"
    ds.origin_x = origin_x
    ds.origin_y = origin_y
    ds.origin_lat = 50.94
    ds.origin_lon = 6.96
    ds.palm_version = "synthetic_test"

    ds.createDimension("x", nx)
    ds.createDimension("y", ny)
    ds.createDimension("time", None)  # unlimited

    xvar = ds.createVariable("x", "f4", ("x",))
    xvar.units = "m"
    xvar.long_name = "distance to origin in x-direction"
    xvar[:] = np.arange(nx) * dx + dx / 2

    yvar = ds.createVariable("y", "f4", ("y",))
    yvar.units = "m"
    yvar.long_name = "distance to origin in y-direction"
    yvar[:] = np.arange(ny) * dy + dy / 2

    tvar = ds.createVariable("time", "f8", ("time",))
    tvar.units = "seconds since 2025-07-19 06:00:00"
    tvar[:] = [21600.0]  # 12:00 UTC

    petvar = ds.createVariable("bio_pet", "f4", ("time", "y", "x"), fill_value=-9999.0)
    petvar.units = "degree_C"
    petvar.long_name = "Physiologically Equivalent Temperature"
    petvar[0, :, :] = pet

print(f"Wrote synthetic NetCDF: {NCFILE} ({NCFILE.stat().st_size} bytes)")

# --- Step 2: Read it back ---

with nc.Dataset(str(NCFILE), "r") as ds:
    pet_read = ds.variables["bio_pet"][0, :, :]
    x_coords = ds.variables["x"][:]
    y_coords = ds.variables["y"][:]
    ox = ds.origin_x
    oy = ds.origin_y
    print(f"Read back: shape={pet_read.shape}, origin=({ox}, {oy})")

# --- Step 3: Write as GeoTIFF ---

# Compute bounds in UTM coordinates
west = ox
south = oy
east = ox + nx * dx
north = oy + ny * dy

transform = from_bounds(west, south, east, north, nx, ny)

with rasterio.open(
    str(TIFFILE),
    "w",
    driver="GTiff",
    height=ny,
    width=nx,
    count=1,
    dtype="float32",
    crs="EPSG:25832",
    transform=transform,
    nodata=-9999.0,
) as dst:
    # Rasterio expects (bands, rows, cols) with north-up convention
    # PALM y increases northward, rasterio row 0 is north → flip y
    dst.write(np.flipud(pet_read).astype(np.float32), 1)
    dst.update_tags(
        variable="bio_pet",
        units="degree_C",
        description="PET at ~1.1m AGL (synthetic test data)",
    )

print(f"Wrote GeoTIFF: {TIFFILE} ({TIFFILE.stat().st_size} bytes)")

# --- Step 4: Verify GeoTIFF ---

with rasterio.open(str(TIFFILE)) as src:
    data = src.read(1)
    print(f"GeoTIFF verification: shape={data.shape}, crs={src.crs}, bounds={src.bounds}")
    print(f"  Value range: {data[data != -9999].min():.1f} to {data[data != -9999].max():.1f}")
    print(f"  Transform: {src.transform}")

print("\n=== NetCDF to GeoTIFF path: PASS ===")
