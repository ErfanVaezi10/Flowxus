# -*- coding: utf-8 -*-
# Flowxus/geometry/loaders/iges_loader.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/5/2025 (Updated: 8/14/2025)

Purpose:
--------
Load 2D airfoil/curve geometry from an IGES (.igs/.iges) CAD file using the Gmsh Python API,
then *sample* the imported curves into a NumPy array of planar (x, y) points.

Main Tasks:
-----------
   1) Import IGES geometry with Gmsh (OCC kernel).
   2) Collect curve entities (prefer boundaries of surfaces; fall back to all curves).
   3) Sample each curve by parameter (uniform in param space) and evaluate xyz.
   4) Drop z (assumes planar geometry) and return concatenated (x, y) points.
   5) Ensure the polyline is closed (first point appended if needed).

Notes:
------
   - Designed to be robust and minimal. It does **not** sort/reorder multiple wires
     into a single loop.
   - If your IGES contains multiple disjoint curves or non‑planar geometry, user may
     need more sophisticated stitching phases upstream.
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


def load_iges(
    filename: str,
    *,
    samples_per_curve: int = 200,
    close_tol: float = 1e-9
) -> np.ndarray:
    """
    Load an IGES file and sample its curves into a planar (N, 2) array.

    Parameters
    ----------
    filename : str
        Path to the .igs/.iges file.
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
        If the IGES file cannot be loaded or no curves are found.
    """
    if gmsh is None:
        raise RuntimeError(
            "[iges_loader] The 'gmsh' Python module is required to load IGES files. "
            "Original import error: {}".format(_GMESH_IMPORT_ERROR)
        )

    # Initialize a private Gmsh session (avoid interfering with other parts of the app)
    already_initialized = gmsh.isInitialized()
    if not already_initialized:
        gmsh.initialize()
    try:
        gmsh.model.add("flowxus_iges_loader")

        # OCC import handles IGES/STEP
        gmsh.model.occ.importShapes(filename)
        gmsh.model.occ.synchronize()

        # Prefer boundaries of surfaces; otherwise, collect all curves
        surfaces = gmsh.model.getEntities(2)
        if surfaces:
            curves = _unique_entities(
                gmsh.model.getBoundary(surfaces, oriented=False, recursive=False)
            )
        else:
            curves = gmsh.model.getEntities(1)

        if not curves:
            raise RuntimeError("No curve entities found in IGES file.")

        # Sample each curve and concatenate results
        xy_parts: List[np.ndarray] = []
        for (dim, tag) in curves:
            if dim != 1:
                continue

            # Parametric domain of curve (robust to gmsh version/stub differences)
            rng = None

            get_range = getattr(gmsh.model, "getParametrizationRange", None)
            if callable(get_range):
                try:
                    out = get_range(dim, tag)
                    if isinstance(out, (list, tuple)) and len(out) >= 2:
                        rng = (float(out[0]), float(out[1]))
                    else:
                        # Some builds may return two scalars; unpack if so
                        t0, t1 = out  # may raise if not iterable
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
                # Last-resort default (common OCC curves are often parameterized on [0,1])
                tmin, tmax = 0.0, 1.0
            else:
                tmin, tmax = rng


            if not np.isfinite([tmin, tmax]).all() or tmax <= tmin:
                continue  # skip degenerate curves

            # Avoid double-counting the end point
            ts = np.linspace(tmin, tmax, max(2, samples_per_curve), endpoint=False)

            # Evaluate curve in 3D, then drop z
            xyz = _eval_curve(dim, tag, ts)
            if xyz.size == 0:
                continue
            xy = xyz[:, :2]
            xy_parts.append(xy)

        if not xy_parts:
            raise RuntimeError("Sampling produced no points (check IGES contents).")

        pts = np.vstack(xy_parts).astype(np.float64, copy=False)

        # Ensure closed loop if endpoints differ (within tolerance)
        if pts.shape[0] >= 2:
            p0, pN = pts[0], pts[-1]
            if not np.allclose(p0, pN, atol=close_tol, rtol=0.0):
                pts = np.vstack([pts, p0])

        return pts

    except Exception as e:
        raise RuntimeError("[iges_loader] Failed to load IGES geometry from {}: {}".format(filename, e))
    finally:
        if not already_initialized:
            try:
                gmsh.finalize()
            except Exception:
                pass

