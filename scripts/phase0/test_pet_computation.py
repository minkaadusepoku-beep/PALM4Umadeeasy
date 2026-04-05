"""
Phase 0 proof: Can we compute PET from PALM-like variables using pythermalcomfort?

Tests PET computation against published reference values.
Reference: Hoeppe (1999), VDI 3787 Blatt 2, Walther & Goestchel (2018).

Standard assumptions for outdoor pedestrian:
- met = 1.4 met (walking at ~4 km/h), equivalent to ~80 W/m2
- clo = 0.5 clo (light summer clothing)
- position = standing
- age = 35, weight = 75 kg, height = 1.80 m
"""

import sys
import os
import time
import numpy as np

# Force UTF-8 output on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from pythermalcomfort.models import pet_steady
    print("pythermalcomfort imported successfully")
except ImportError:
    print("ERROR: pythermalcomfort not installed")
    sys.exit(1)

# --- Standard outdoor pedestrian parameters ---
MET = 1.4    # metabolic rate [met] -- walking slowly
CLO = 0.5    # clothing insulation [clo] -- light summer
POSITION = "standing"
AGE = 35
WEIGHT = 75
HEIGHT = 1.80

def compute_pet(ta, tmrt, v, rh):
    """Compute PET for standard outdoor pedestrian."""
    result = pet_steady(
        tdb=ta, tr=tmrt, v=v, rh=rh,
        met=MET, clo=CLO, position=POSITION,
        age=AGE, weight=WEIGHT, height=HEIGHT,
    )
    return result.pet

# --- Test cases ---
# Tolerance is generous because different PET implementations
# (RayMan, MEMI, Walther correction) produce slightly different values.

test_cases = [
    # (Ta, Tmrt, wind, RH, expected_PET, tolerance, label)
    # Indoor neutral: when Tmrt=Ta, low wind, moderate RH -> PET near Ta
    (20.0, 20.0, 0.1, 50.0, 20.0, 3.0, "Indoor neutral (PET near Ta)"),
    # Moderate outdoor summer
    (25.0, 40.0, 1.0, 50.0, 32.0, 5.0, "Moderate summer outdoor"),
    # Hot conditions
    (30.0, 60.0, 1.0, 40.0, 43.0, 6.0, "Hot outdoor (strong stress)"),
    # Extreme heat
    (35.0, 70.0, 0.5, 30.0, 53.0, 7.0, "Extreme heat outdoor"),
    # Cool conditions
    (10.0, 10.0, 2.0, 60.0, 8.0, 5.0, "Cool outdoor"),
]

wind_cases = [
    (30.0, 50.0, 0.5, 40.0, "Low wind"),
    (30.0, 50.0, 3.0, 40.0, "High wind"),
]

print("\n--- PET Computation Tests ---\n")
print(f"Standard assumptions: met={MET}, clo={CLO}, {POSITION}, age={AGE}")
print()

all_pass = True
results = []

for ta, tmrt, v, rh, expected, tol, label in test_cases:
    try:
        pet_val = compute_pet(ta, tmrt, v, rh)
        diff = abs(pet_val - expected)
        status = "PASS" if diff <= tol else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {label}")
        print(f"         Ta={ta} Tmrt={tmrt} v={v} RH={rh}%")
        print(f"         PET={pet_val:.1f} (expected ~{expected} +/-{tol}, diff={diff:.1f})")
        results.append((label, pet_val))
    except Exception as e:
        print(f"  [ERROR] {label}: {e}")
        all_pass = False

# --- Wind effect sanity check ---
print("\n--- Wind Effect Sanity Check ---")
wind_pets = []
for ta, tmrt, v, rh, label in wind_cases:
    pet_val = compute_pet(ta, tmrt, v, rh)
    wind_pets.append((label, v, pet_val))
    print(f"  {label}: v={v} m/s -> PET={pet_val:.1f}")

if wind_pets[1][2] < wind_pets[0][2]:
    print(f"  [PASS] Higher wind reduces PET: {wind_pets[0][2]:.1f} -> {wind_pets[1][2]:.1f} (delta={wind_pets[0][2]-wind_pets[1][2]:.1f})")
else:
    print(f"  [FAIL] Expected lower PET with higher wind")
    all_pass = False

# --- VDI 3787 classification ---
print("\n--- VDI 3787 Classification ---")

VDI_CLASSES = [
    (float("-inf"), 4, "Very cold", "Extreme cold stress"),
    (4, 8, "Cold", "Strong cold stress"),
    (8, 13, "Cool", "Moderate cold stress"),
    (13, 18, "Slightly cool", "Slight cold stress"),
    (18, 23, "Comfortable", "No thermal stress"),
    (23, 29, "Slightly warm", "Slight heat stress"),
    (29, 35, "Warm", "Moderate heat stress"),
    (35, 41, "Hot", "Strong heat stress"),
    (41, float("inf"), "Very hot", "Extreme heat stress"),
]

def classify_pet(val):
    for lo, hi, perc, stress in VDI_CLASSES:
        if lo <= val < hi:
            return perc, stress
    return "Unknown", "Unknown"

for label, pet_val in results:
    perc, stress = classify_pet(pet_val)
    print(f"  PET={pet_val:.1f} -> {perc} ({stress})")

# --- Grid processing performance ---
print("\n--- Grid Processing Performance ---")
np.random.seed(42)
n_cells = 500  # test batch
ta_arr = np.random.uniform(25, 35, n_cells)
tmrt_arr = np.random.uniform(40, 70, n_cells)
v_arr = np.random.uniform(0.3, 5.0, n_cells)
rh_arr = np.random.uniform(20, 60, n_cells)

t0 = time.perf_counter()
pet_arr = np.array([
    compute_pet(float(ta_arr[i]), float(tmrt_arr[i]), float(v_arr[i]), float(rh_arr[i]))
    for i in range(n_cells)
])
elapsed = time.perf_counter() - t0

print(f"  Processed {n_cells} cells in {elapsed:.2f}s ({n_cells/elapsed:.0f} cells/s)")
print(f"  PET range: {pet_arr.min():.1f} to {pet_arr.max():.1f}")
print(f"  PET mean: {pet_arr.mean():.1f}")
est_full = 200000 / (n_cells / elapsed)
print(f"  Estimated for 500x400 grid (200k cells): {est_full:.0f}s ({est_full/60:.1f} min)")

# Check if vectorized call works
print("\n--- Vectorized Call Test ---")
try:
    t0 = time.perf_counter()
    result_vec = pet_steady(
        tdb=ta_arr.tolist(), tr=tmrt_arr.tolist(),
        v=v_arr.tolist(), rh=rh_arr.tolist(),
        met=[MET]*n_cells, clo=[CLO]*n_cells,
        position=[POSITION]*n_cells,
        age=[AGE]*n_cells, weight=[WEIGHT]*n_cells, height=[HEIGHT]*n_cells,
    )
    elapsed_vec = time.perf_counter() - t0
    print(f"  [PASS] Vectorized call works: {n_cells} cells in {elapsed_vec:.2f}s ({n_cells/elapsed_vec:.0f} cells/s)")
    speedup = elapsed / elapsed_vec if elapsed_vec > 0 else float("inf")
    print(f"  Speedup vs loop: {speedup:.1f}x")
except Exception as e:
    print(f"  [INFO] Vectorized call not supported or failed: {e}")
    print(f"  Loop-based computation is the fallback path.")

# --- Summary ---
if all_pass:
    print("\n=== PET computation path: PASS ===")
else:
    print("\n=== PET computation path: PARTIAL PASS (see failures above) ===")
