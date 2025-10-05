# FLOWXUS Studio

> Mesh → Solve → Verify — a reproducible, scriptable CFD workflow built around SU2.

**FLOWXUS Studio** turns a 2D Gmsh mesh into a validated SU2 run with deterministic configs, clear failure modes, and compact post-run summaries.

---

## Status

- Latest tag: **v0.0.2**
- Maturity: **alpha** (APIs may change; see Security & Support below)
- License: **PolyForm Noncommercial 1.0.0** (free for non-commercial use; contact us for commercial licensing)

---

## What it does (today)

- **SU2 config builder (v7+)**  
  Sectioned defaults → normalized user params → schema & cross-key validation → stable `KEY= VALUE` output.
- **Marker handling**  
  Accepts labels or Physical IDs; groups by SU2 keys; canonical tuple formatting.
- **Mesh conversion**  
  `.msh` → `.su2` via `meshio` (forces 2D; exports Physical name→ID map).
- **Runner**  
  Serial or MPI (`mpirun`) with a dry-run mode; returns (rc, stdout, stderr); robust “not found” errors.
- **Post**  
  Reads SU2 history (`history.csv` or `.dat`), normalizes keys, extracts last residuals and aero coefficients.

> Note: Post-processing currently **reads SU2 `.dat`/`.csv` history**; surface/volume fields are out of scope in v0.0.2.


---

## Quickstart

### 0) Dependencies

- Python ≥ 3.9
- [`meshio`](https://pypi.org/project/meshio/) (for mesh conversion)
- **SU2** (v7+ recommended) available on your `PATH`
- Optional: `mpirun` (OpenMPI/MPICH) for parallel runs

```bash
pip install meshio
# install SU2 separately (system package/source/conda), ensure `SU2_CFD` resolves

