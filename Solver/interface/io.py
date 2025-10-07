# -*- coding: utf-8 -*-
# Flowxus/solver/interface/io.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/23/2025 (Updated: 10/07/2025)

Purpose
-------
Convert Gmsh meshes (.msh v2/v4, ASCII/binary) into SU2 surface/2D meshes (.su2) using
`meshio`, enforcing a strictly 2D representation and preserving boundary/physical tags
when available. Emits a name→ID map derived from Gmsh `Physical` groups for downstream
boundary-condition assignment in SU2.

Main Tasks
----------
    1. Read a Gmsh `.msh` via `meshio.read`, with robust error reporting.
    2. Verify planarity in Z and truncate coordinates to 2D (x,y) if needed.
    3. Retain only 2D-relevant cell types (line/triangle/quad), warning on drops.
    4. Extract `field_data` to build a PhysicalName→ID mapping for boundary markers.
    5. Write a `.su2` file and sanity-check its existence and minimal size.

Notes
-----
- Intended for 2D workflows; 3D volume elements are discarded.
- `id_map` is taken from Gmsh `field_data`. If the input mesh lacks Physical names, 
  the map will be empty and SU2 BC assignment should rely on other conventions.
- Requires `meshio` (and implicitly `numpy`). Errors are surfaced with actionable messages.
"""

import os
import warnings


def msh_to_su2(msh_path, su2_path):
    """
    Convert a Gmsh mesh (.msh v2/v4; ASCII or binary) to an SU2 mesh (.su2), enforcing 2D.

    Args
    ----
    msh_path : str
        Path to the input Gmsh `.msh` file (v2 or v4, ASCII or binary).
    su2_path : str
        Destination path for the output `.su2` file.

    Returns
    -------
    (str, dict)
        Tuple of:
        - su2_path (str): Absolute or provided path to the written SU2 mesh.
        - id_map (dict[str, int]): Mapping from Gmsh Physical names to integer IDs
          (useful for SU2 boundary condition assignment).

    Raises
    ------
    ImportError
        If `meshio` is not installed or cannot be imported.
    RuntimeError
        - If the Gmsh file cannot be read.
        - If no supported 2D cells remain after filtering.
        - If writing the `.su2` file fails or produces an implausibly small file.

    Warnings
    --------
    RuntimeWarning
        - If non-zero Z components are detected (the mesh is truncated to 2D).
        - If non-2D or unsupported cell types are dropped during conversion.

    Notes
    -----
    - Supported 2D cell types include: "line", "triangle", "quad"/"quadrilateral".
    - `id_map` uses `mesh.field_data` as exposed by `meshio`:
        name -> (id, dim, ...)
      Only the first value (id) is used here.
    """
    # `meshio` is the only hard dependency; import lazily to avoid global import costs.
    try:
        import meshio
    except Exception:
        # Keep message precise for faster user resolution.
        raise ImportError("meshio is required to convert .msh to .su2")

    # Read the Gmsh mesh with actionable error context.
    try:
        mesh = meshio.read(msh_path)
    except Exception as e:
        raise RuntimeError("Failed to read Gmsh file '{}': {}".format(msh_path, e))

    # If the mesh has a Z dimension, check planarity and inform the user before truncation.
    try:
        import numpy as np  # meshio depends on numpy; this should usually succeed.
        if getattr(mesh, "points", None) is not None and mesh.points.shape[1] > 2:
            z = mesh.points[:, 2]
            # Emit a warning if Z deviates beyond a small tolerance.
            if np.nanmax(np.abs(z)) > 1e-8:
                warnings.warn(
                    "Input mesh has non-zero Z coordinates (max |z| ≈ {:.3e}); truncating to 2D.".format(
                        float(np.nanmax(np.abs(z)))
                    ),
                    RuntimeWarning,
                )
    except Exception:
        # If numpy import fails (unlikely), proceed without planarity diagnostics.
        pass

    # Enforce a strict 2D coordinate set to prevent SU2 from interpreting as 3D.
    if getattr(mesh, "points", None) is not None and mesh.points.shape[1] > 2:
        mesh.points = mesh.points[:, :2].copy()

    # Retain only 2D-relevant cells. Preserve order; warn about discarded types for transparency.
    keep_types = {"line", "triangle", "quad", "quadrilateral"}
    orig = list(getattr(mesh, "cells", []) or [])
    mesh.cells = [c for c in orig if c.type in keep_types]
    dropped = [c.type for c in orig if c.type not in keep_types]
    if dropped:
        # Present unique, stable-sorted list of dropped types.
        unk = sorted(set(dropped))
        warnings.warn(
            "Dropped non-2D/unsupported cell types during conversion: {}".format(", ".join(unk)),
            RuntimeWarning,
        )

    # Fail fast if nothing usable remains (prevents silent empty outputs).
    if not mesh.cells:
        raise RuntimeError("No supported 2D cells found (expected line/triangle/quad).")

    # Build a PhysicalName→ID map from Gmsh metadata if present.
    id_map = {}
    fd = getattr(mesh, "field_data", {}) or {}
    for name, val in fd.items():
        # meshio typically stores: name -> (id, dim, [optional extras])
        try:
            pid = int(val[0])
            id_map[name] = pid
        except Exception:
            # Ignore malformed entries rather than failing the whole conversion.
            pass

    # Write the SU2 mesh. `meshio` performs the format translation internally.
    meshio.write(su2_path, mesh, file_format="su2")

    # Minimal sanity check: existence and non-trivial size (guards against empty writes).
    if not os.path.exists(su2_path) or os.path.getsize(su2_path) < 100:
        raise RuntimeError("Failed to write a valid .su2 file: {}".format(su2_path))

    return su2_path, id_map
