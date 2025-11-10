# -*- coding: utf-8 -*-
# Flowxus/geometry/topology/indices.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 9/1/2025

Purpose:
--------
Deterministic indexers for key vertices on a CLOSED 2D loop. Owned responsibilities:
   - Find LE/TE indices on a closed polyline (first==last).
   - Make tie-breaking explicit and stable under tiny numeric noise.

Conventions:
------------
   - Indices are 0-based over the CLOSED array (0..N-1), but the duplicate
     last point (equal to the first) is IGNORED for extremum search.
   - "LE" = minimum x; "TE" = maximum x, both measured on the geometry itself.

Important precondition:
-----------------------
   - Results are *physically* meaningful when the loop is in a chord-aligned frame
     (LE→TE along +x). If callers may pass rotated shapes, normalize/align earlier.
"""


from __future__ import division
from typing import Tuple
import numpy as np
from ._validation import _assert_xy, _require_closed


def _arg_extreme_with_ties(x: np.ndarray, y: np.ndarray, *, mode: str, tol: float) -> int:
    """
    Stable index for min/max(x) with explicit tie-breaking:
      1) Primary: extremum of x (min for LE, max for TE).
      2) Secondary: minimal |y| (closest to midline) among tied candidates.
      3) Tertiary: smallest original index (full determinism).
    """
    if mode == "min":
        x0 = float(np.min(x))
        cand = np.where(x <= x0 + tol)[0]
    elif mode == "max":
        x0 = float(np.max(x))
        cand = np.where(x >= x0 - tol)[0]
    else:
        raise ValueError("mode must be 'min' or 'max'")

    if cand.size == 1:
        return int(cand[0])

    # Secondary: prefer the candidate closest to midline (|y| minimal).
    y_abs = np.abs(y[cand])
    y_min = float(np.min(y_abs))
    cand2 = cand[np.where(y_abs <= y_min + tol)[0]]

    # Tertiary: pick the smallest index (determinism).
    return int(np.min(cand2))


def le_te_indices(points_closed: np.ndarray, tol: float = 1e-12) -> Tuple[int, int]:
    """
    Find (LE_idx, TE_idx) on a CLOSED polyline.

    Parameters
    ----------
    points_closed : np.ndarray
        Closed (N,2) polyline; first row equals last row within tolerance.
    tol : float
        Absolute tolerance for equality tests and tie-breaking.

    Returns
    -------
    (int, int)
        (LE_idx, TE_idx) as 0-based indices over 0..N-1 (the last duplicate
        row is ignored internally for the search).

    Notes
    -----
    - LE = argmin_x with tie-breakers: minimal |y|, then smallest index.
    - TE = argmax_x with the same tie-breakers.
    - This is purely geometric along the current x-axis (see precondition above).

    Raises
    ------
    ValueError
        If the loop is not closed, has too few unique points, or the chord is degenerate
        (min(x) == max(x) within tol), making LE/TE undefined.
    """
    _assert_xy(points_closed)
    _require_closed(points_closed, tol=tol)

    # Ignore the duplicate last row for the search; require at least 3 unique vertices.
    P = points_closed[:-1]
    if P.shape[0] < 3:
        raise ValueError("Need at least 3 unique vertices to locate LE/TE.")

    x = P[:, 0]
    y = P[:, 1]

    # Degenerate chord check: all x within tol -> can't define distinct LE/TE.
    x_min = float(np.min(x))
    x_max = float(np.max(x))
    if x_max - x_min <= tol:
        raise ValueError("Degenerate chord (min(x)≈max(x)); LE/TE undefined in this frame.")

    le = _arg_extreme_with_ties(x, y, mode="min", tol=tol)
    te = _arg_extreme_with_ties(x, y, mode="max", tol=tol)

    # Defensive: ensure distinct indices (should always hold if x_max - x_min > tol).
    if le == te:
        raise ValueError("Failed to distinguish LE and TE; check geometry or tolerance.")
    return int(le), int(te)
