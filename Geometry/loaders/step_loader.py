# -*- coding: utf-8 -*-
# Flowxus/geometry/loaders/step_loader.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/7/2025 (Updated: 8/20/2025)

Purpose:
--------
Load 2D airfoil/curve geometry from a STEP (.stp/.step) CAD file using the Gmsh Python API,
then *sample* the imported curves into a NumPy array of planar (x, y) points.

Main Tasks:
-----------
   1) Import STEP geometry with Gmsh (OCC kernel).
   2) Collect curve entities (prefer boundaries of surfaces; fall back to all curves).
   3) Sample each curve by parameter (uniform in param space) and evaluate xyz.
   4) Drop z (assumes planar geometry) and return concatenated (x, y) points.
   5) Ensure the polyline is closed (first point appended if needed).

Notes:
------
   - This loader aims to be robust and minimal. It doesn't try to sort/reorder multiple
     wires into a single topological loop.
   - If your STEP contains multiple disjoint curves or non‑planar geometry, user may need
     more sophisticated stitching phases upstream.
   - Requires: `gmsh` (Python API) and `numpy`.
"""

from typing import List
import numpy as np
from ._helpers import _unique_entities, _eval_curve

try:
    import gmsh  # type: ignore
except Exception as _e:  # pragma: no cover
    gmsh = None
    _GMESH_IMPORT_ERROR = _e


def load_step(
    filename: str,
    *,
    samples_per_curve: int = 200,
    close_tol: float = 1e-9
) -> np.ndarray:
    """
    Load a STEP file and sample its curves into a planar (N, 2) array.

    Parameters
    ----------
    filename : str
        Path to the .stp/.step file.
    samples_per_curve : int, optional
        Number of parametric samples per curve entity (default: 200).
        Increase for smoother sampling of long/spline curves.
    close_tol : float, optional
        Numerical tolerance for closing the polyline (default: 1e-9).

    Returns
    -------
    np.ndarray
        (N, 2) float64 array of (x, y) points. The sequence is obtained by
        concatenating sampled points from each identified curve.

    Raises
    ------
    RuntimeError
        If the gmsh Python API is not available or import fails.
    RuntimeError
        If the STEP file cannot be loaded or no curves are found.
    """
    if gmsh is None:
        raise RuntimeError(
            "[step_loader] The 'gmsh' Python module is required to load STEP files. "
            "Original import error: {}".format(_GMESH_IMPORT_ERROR)
        )

    # Initialize a private Gmsh session (avoid interfering with other parts of the app)
    already_initialized = gmsh.isInitialized()
    if not already_initialized:
        gmsh.initialize()
    try:
        gmsh.model.add("flowxus_step_loader")

        # OCC import handles STEP/IGES
        gmsh.model.occ.importShapes(filename)
        gmsh.model.occ.synchronize()

        # Strategy: prefer boundaries of surfaces (dim=2) → curves (dim=1);
        # if no surfaces exist, fall back to all curve entities.
        surfaces = gmsh.model.getEntities(2)
        if surfaces:
            # Get curve boundaries for all surfaces; oriented=False to avoid duplicates with sign
            curves = _unique_entities(
                gmsh.model.getBoundary(surfaces, oriented=False, recursive=False)
            )
        else:
            curves = gmsh.model.getEntities(1)

        if not curves:
            raise RuntimeError("No curve entities found in STEP file.")

        # Sample each curve by parameter and evaluate 3D point coordinates.
        # We then drop z (assume planarity) and concatenate.
        xy_parts: List[np.ndarray] = []
        for (dim, tag) in curves:
            if dim != 1:
                continue

            # Get parametric domain (robust to gmsh version/stub differences)
            rng = None

            get_range = getattr(gmsh.model, "getParametrizationRange", None)
            if callable(get_range):
                try:
                    out = get_range(dim, tag)
                    if isinstance(out, (list, tuple)) and len(out) >= 2:
                        rng = (float(out[0]), float(out[1]))
                    else:
                        t0, t1 = out  # may be two scalars
                        rng = (float(t0), float(t1))
                except Exception:
                    rng = None

            if rng is None:
                get_range_occ = getattr(getattr(gmsh, "model", None), "occ", None)
                get_range_occ = getattr(get_range_occ, "getParametrizationRange", None)
                if callable(get_range_occ):
                    try:
                        out = get_range_occ(dim, tag)
                        if isinstance(out, (list, tuple)) and len(out) >= 2:
                            rng = (float(out[0]), float(out[1]))
                    except Exception:
                        rng = None

            if rng is None:
                # last-resort default (many OCC curves are parameterized on [0,1])
                tmin, tmax = 0.0, 1.0
            else:
                tmin, tmax = rng


            if not np.isfinite([tmin, tmax]).all() or tmax <= tmin:
                # Skip degenerate curves
                continue

            # Avoid double-counting the end point to minimize duplicates at joins
            ts = np.linspace(tmin, tmax, max(2, samples_per_curve), endpoint=False)

            # Evaluate 3D geometry at parameters (dim=1 for curves)
            xyz = _eval_curve(dim, tag, ts)

            if xyz.size == 0:
                continue

            # Accept only (x, y) (drop z); assume airfoil lies in a plane
            xy = xyz[:, :2]

            # Append samples for this curve
            xy_parts.append(xy)

        if not xy_parts:
            raise RuntimeError("Sampling produced no points (check STEP contents).")

        pts = np.vstack(xy_parts).astype(np.float64, copy=False)

        # Ensure closed loop if endpoints differ (use tolerance)
        if pts.shape[0] >= 2:
            p0, pN = pts[0], pts[-1]
            if not np.allclose(p0, pN, atol=close_tol, rtol=0.0):
                pts = np.vstack([pts, p0])

        return pts

    except Exception as e:
        raise RuntimeError("[step_loader] Failed to load STEP geometry from {}: {}".format(filename, e))
    finally:
        # Keep global gmsh state clean for the rest of the app
        if not already_initialized:
            try:
                gmsh.finalize()
            except Exception:
                pass
