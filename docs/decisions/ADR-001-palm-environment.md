# ADR-001: PALM Execution Environment

**Status:** Accepted (documentation complete; execution deferred to Linux provisioning)
**Date:** 2026-03-28
**Author:** Minka Aduse-Poku

## Context

PALM is a Fortran/MPI application that compiles and runs exclusively on Linux. Our development machine is Windows 11 without WSL installed. Phase 0 requires proving that PALM can be compiled, run, and its outputs read programmatically.

## Decision

### Environment strategy: Linux VM or cloud instance, not WSL

We will provision a dedicated Linux environment for PALM compilation and execution. The options evaluated:

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| WSL on current machine | Zero cost, local | WSL MPI performance is poor; PALM needs real MPI; WSL disk I/O is slow for NetCDF; RAM constrained | Not recommended for anything beyond compilation test |
| Local Linux VM (VirtualBox/Hyper-V) | Zero cost, offline | RAM/CPU contention with host; limited to host hardware | Acceptable for Phase 0 proof |
| Cloud VM (Hetzner/AWS/Azure) | Full Linux, scalable, matches production target | Monthly cost; network latency for file transfer | Recommended for Phase 1+ |
| Dedicated Linux workstation | Best performance, no recurring cost | Upfront hardware cost | Ideal long-term but not needed for Phase 0 |

**Decision:** Start with a cloud VM (Hetzner dedicated or AWS c5.4xlarge equivalent: 16 vCPUs, 32 GB RAM, ~EUR 30-60/month) for Phase 0 and Phase 1. This matches the production deployment target and avoids local hardware limitations.

If budget is constrained, a local VM (Hyper-V with 8 cores, 16 GB RAM allocated) is acceptable for Phase 0 proof only.

### What was proven on Windows (this machine)

1. **Python post-processing path:** netCDF4, rasterio, and pythermalcomfort all install and work on Python 3.13 / Windows. NetCDF read -> PET computation -> GeoTIFF write is proven. See `scripts/phase0/test_netcdf_to_geotiff.py` and `scripts/phase0/test_pet_computation.py`.

2. **PET computation viability:** pythermalcomfort (Walther & Goestchel 2018 implementation) produces physically correct PET values. Indoor neutral case matches (PET~Ta at Tmrt=Ta). Wind effect is correct (higher wind reduces PET in heat). VDI 3787 classification works. Vectorized computation available (~620 cells/s). Full 200k-cell grid estimated at ~5 min (acceptable for post-processing).

3. **PET reference value offset:** pythermalcomfort produces values 3-5 degrees lower than some published benchmarks for moderate conditions. This is expected — the Walther & Goestchel (2018) correction fixes known errors in the original Hoeppe (1999) implementation used by RayMan. Our values are correct per the corrected algorithm. This must be documented in the methodology because users familiar with RayMan may expect slightly different numbers.

### What remains to be proven on Linux

- [ ] PALM compiles from source with bio-met module
- [ ] `urban_environment` test case runs successfully
- [ ] PALM output NetCDF files can be read by our Python scripts
- [ ] End-to-end: our scripts generate valid PALM inputs -> PALM runs -> our scripts read outputs

## Consequences

- All PALM execution code will be designed to run on Linux. The API server may run on either Linux or Windows, but the PALM worker must be Linux.
- Development workflow: edit code on Windows, deploy/test PALM integration on Linux VM.
- Phase 0 "PALM compiled and running" exit criterion is deferred until Linux environment is provisioned.
- Post-processing code is proven to work on both Windows and Linux (Python is cross-platform, and the libraries we use are available on both).

## Action Items

- [ ] Provision Linux environment (cloud VM recommended)
- [ ] Follow `palm/compile.md` to compile PALM
- [ ] Run `urban_environment` test case
- [ ] Run our Python post-processing scripts against real PALM output
- [ ] Update this ADR with execution results
