# PALM Compilation Guide

**Status:** Documented from research. Not yet executed (requires Linux environment).
**PALM Target Version:** 23.10 or latest stable (check https://gitlab.palm-model.org/releases/palm_model_system/-/releases)
**Last checked:** 2026-03-28

---

## Prerequisites

### Compiler

| Compiler | Minimum version | Recommended | Notes |
|---|---|---|---|
| gfortran (GCC) | 9.x | 10+ | PALM uses Fortran 2003/2008 features. gfortran 9 is minimum. |
| Intel ifort (classic) | oneAPI 2021+ | Latest oneAPI | Generally produces faster PALM binaries than gfortran. |
| Intel ifx (LLVM-based) | oneAPI 2023+ | Latest oneAPI | Newer Intel compiler. Supported. |

### MPI

PALM is fundamentally MPI-parallel. **There is no serial build option.** Even single-core runs require MPI.

| Implementation | Minimum version | Notes |
|---|---|---|
| OpenMPI | 3.x | OpenMPI 4.x recommended |
| MPICH | 3.x | Works |
| Intel MPI | 2021+ | Common on HPC clusters |

### Libraries

| Library | Required | Version | Notes |
|---|---|---|---|
| NetCDF-C | Yes | 4.6+ | Must have HDF5/NetCDF-4 support |
| NetCDF-Fortran | Yes | 4.5+ | `nf-config` must be on PATH |
| HDF5 | Yes (transitive) | 1.10+ | Required by NetCDF-4 |
| FFTW3 | Yes (default) | 3.3+ | For Poisson solver. Fortran interface required. |
| CMake | Yes | 3.10+ | Build system |
| Python 3 | Yes (tooling) | 3.8+ | For palm_csd, preprocessing, configuration scripts |

**Alternative to FFTW3:** Intel MKL FFT can substitute on Intel systems. Temperton FFT is built-in but less efficient.

### Python packages (for preprocessing/postprocessing)

```
numpy scipy netCDF4 gdal pyproj
```

---

## Build System

PALM uses **CMake** (modern versions, >= 23.10). Legacy versions used a custom `palmbuild` script.

### Build steps (to be executed on Linux)

```bash
# 1. Clone PALM source
git clone https://gitlab.palm-model.org/releases/palm_model_system.git
cd palm_model_system
git checkout v23.10  # or latest tag

# 2. Create build directory
mkdir build && cd build

# 3. Configure with CMake
cmake \
  -DCMAKE_Fortran_COMPILER=mpif90 \
  -DNETCDF_C_ROOT=/path/to/netcdf-c \
  -DNETCDF_FORTRAN_ROOT=/path/to/netcdf-fortran \
  -DFFTW_ROOT=/path/to/fftw3 \
  ../packages/palm/model

# 4. Build
make -j$(nproc)

# 5. Verify binary
ls -la palm
```

### Modules to enable

The bio-meteorology module is **compiled by default** — it is part of the standard PALM source. It is **activated at runtime** via the namelist, not at compile time.

Modules needed for our workflow (all compiled by default in standard build):
- Urban Surface Model (USM)
- Land Surface Model (LSM)
- Plant Canopy Model
- Radiation Model (RRTMG, bundled in PALM source)
- Biometeorology Module
- Building Surface Model

No special compile flags needed for these modules.

---

## Verification

After compilation, run the shipped `urban_environment` test case:

```bash
# From PALM root directory
cd tests/cases/urban_environment
# Use palmrun or direct mpirun
mpirun -np 4 /path/to/palm -p urban_environment
```

Expected: completes without error, produces NetCDF output files.

---

## Hardware Requirements

### Minimum for test cases

- 4-8 CPU cores
- 8-16 GB RAM
- SSD storage (PALM I/O is disk-intensive)

### For our target domain (500m x 500m at 10m, 50x50x40 grid)

- 8-16 CPU cores
- 16 GB RAM
- ~10 GB disk per simulation (input + output)
- Estimated wall time: 15-45 min depending on physics modules active

### For production (larger domains, multiple concurrent jobs)

- 32-64+ cores per job
- 4 GB RAM per core
- Fast shared filesystem or S3-compatible storage

---

## Known Issues to Watch For

1. **NetCDF library path conflicts:** Ensure `nf-config --flibs` and `nc-config --libs` return consistent paths. Mixed installations (system + conda) cause linking failures.
2. **MPI compiler wrapper:** Must use `mpif90` (or `mpifort`) as the Fortran compiler, not bare `gfortran`/`ifort`.
3. **FFTW Fortran interface:** Some package managers install FFTW without the Fortran interface. Verify `fftw3.f03` header exists.
4. **Legacy build scripts:** If you encounter `palmbuild` or `.palm.config.*` files, those are the old build system. Use CMake.

---

## Action Items

- [ ] Provision a Linux environment (VM, cloud, or WSL)
- [ ] Install all dependencies
- [ ] Compile PALM from source following above steps
- [ ] Run `urban_environment` test case
- [ ] Document exact versions, flags, and any deviations from this guide
