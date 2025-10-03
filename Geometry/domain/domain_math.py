# -*- coding: utf-8 -*-
# Flowxus/geometry/domain/domain_math.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/13/2025 (Updated: 9/27/2025)

Purpose:
--------
Pure math/validation helpers for constructing a rectangular far-field box around a 2D airfoil.
This module is *NumPy-only*:
    - No plotting and file I/O.
    - No logging side effects.
    - Intentionally lightweight and safe for import in any environment.

Main Tasks:
-----------
    1. Validate user-provided far-field box extents.
    2. Compute bounding-box coordinates from the leading edge reference.
    3. Provide default boundary names (physical tags).
    4. Supply a simple utility to find the leading edge.
"""


from typing import Dict
import numpy as np

# Required user-provided keys for farfield box extents
REQUIRED_KEYS = ("up", "down", "front", "back")
__all__ = [
    "REQUIRED_KEYS",
    "validate_box_dims",
    "leading_edge_from_points",
    "compute_box_bounds",
    "default_physical_tags",
]


def validate_box_dims(box_dims: Dict[str, float]) -> Dict[str, float]:
    """
    Type- and range-check the required farfield extents.

    Parameters
    ----------
    box_dims : dict
        Dictionary with keys {"up","down","front","back"} and float values.

    Returns
    -------
    dict
        A new dictionary with the same keys and float-cast values.

    Raises
    ------
    ValueError
        If a required key is missing, cannot be cast to float, or <= 0.
    """
    out = {}
    for k in REQUIRED_KEYS:
        if k not in box_dims:
            raise ValueError("box_dims missing required key '{}'".format(k))
        try:
            v = float(box_dims[k])
        except Exception:
            raise ValueError("box_dims['{}'] must be a number".format(k))
        if v <= 0.0:
            raise ValueError("box_dims['{}'] must be > 0 (got {})".format(k, v))
        out[k] = v
    return out


def leading_edge_from_points(points: np.ndarray) -> np.ndarray:
    """
    Return the leading edge (LE) point defined as the minimum-x coordinate.

    Parameters
    ----------
    points : np.ndarray
        Array of shape (N,2) containing 2D coordinates.

    Returns
    -------
    np.ndarray
        Array of shape (2,) containing [x,y] of the leading edge.

    Raises
    ------
    ValueError
        If `points` is not a valid (N,2) array.
    """
    if points is None or points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected (N,2) array of points.")
    if points.shape[0] == 0:
        raise ValueError("Empty array provided; no points to evaluate leading edge.")
    if not np.isfinite(points).all():
        raise ValueError("Non-finite values in points.")
    idx = int(np.argmin(points[:, 0]))
    return points[idx]


def compute_box_bounds(le_xy: np.ndarray, box_dims: Dict[str, float]) -> Dict[str, float]:
    """
    Compute the axis-aligned far-field bounding box anchored at the leading edge (LE).

    Parameters
    ----------
    le_xy : np.ndarray
        LE coordinate as a 1D array-like of length 2: (x0, y0).
    box_dims : Dict[str, float]
        Positive extents from the LE in each direction with keys:
        {"up", "down", "front", "back"}.

    Returns
    -------
    Dict[str, float]
        {"xmin", "xmax", "ymin", "ymax"}.

    Raises
    ------
    ValueError
        If `le_xy` is malformed, any required key is missing, any value is non-positive,
        or the resulting spans are non-positive.
    """
    le_xy = np.asarray(le_xy, dtype=float)
    if le_xy.shape != (2,) or not np.isfinite(le_xy).all():
        raise ValueError("le_xy must be shape (2,) and finite.")

    # Ensure required keys exist and are > 0 (also casts to float)
    dims = validate_box_dims(dict(box_dims))

    x0, y0 = float(le_xy[0]), float(le_xy[1])
    bbox = {
        "xmin": x0 - dims["front"],
        "xmax": x0 + dims["back"],
        "ymin": y0 - dims["down"],
        "ymax": y0 + dims["up"],
    }
    if not (bbox["xmin"] < bbox["xmax"] and bbox["ymin"] < bbox["ymax"]):
        raise ValueError("Invalid box bounds (non-positive span).")
    return bbox


def default_physical_tags() -> Dict[str, str]:
    """
    Provide a consistent set of physical group names.

    Used for Gmsh boundaries and carried into solver configs (e.g., SU2).
    This ensures alignment across geometry, meshing, and solver.

    Returns
    -------
    dict
        {"inlet","outlet","top","bottom","airfoil"}
    """
    return {
        "inlet": "inlet",
        "outlet": "outlet",
        "top": "top",
        "bottom": "bottom",
        "airfoil": "airfoil",
    }
