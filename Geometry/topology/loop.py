# -*- coding: utf-8 -*-
# Flowxus/geometry/topology/loop.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/31/2025

Purpose:
--------
This module owns *connectivity-level* concerns:
   - Closure predicates and enforcement,
   - Signed area and orientation (CW/CCW),
   - Canonical orientation (e.g., CCW) with stable, deterministic behavior.

Notes:
------------
   - Pure NumPy; no logging, plotting, or file I/O.
   - Functions are side-effect free (no in-place mutation unless documented).
   - Tolerances are explicit; defaults are conservative for geometry in chord units.
   - Works with arrays shaped (N, 2). If a "closed" loop is expected, the last row
     may equal the first; functions that accept both open/closed loops document this.
"""

from __future__ import division
import numpy as np
from ._validation import _assert_xy, _is_exactly_closed


# -----------------------
# Public API
# -----------------------
def is_closed(points: np.ndarray, tol: float = 1e-9) -> bool:
    """
    Predicate: does the polyline close on itself (first==last within tol)?

    Parameters
    ----------
    points : np.ndarray
        (N, 2) array; N>=2 recommended.
    tol : float
        Absolute tolerance for endpoint equality (rtol fixed at 0).

    Returns
    -------
    bool
        True if closed (within tol), else False.
    """
    _assert_xy(points)
    return _is_exactly_closed(points, tol)


def ensure_closed(points: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """
    Ensure the polyline is closed. If last != first (within `tol`), append the first.

    Parameters
    ----------
    points : np.ndarray
        (N, 2) array representing an open or closed polyline.
    tol : float
        Absolute tolerance for endpoint equality.

    Returns
    -------
    np.ndarray
        Closed polyline of shape (M, 2), where M is N or N+1.

    Raises
    ------
    ValueError
        If `points` is not (N, 2).

    Notes
    -----
    - If already closed within tol, the original array reference is returned (no copy).
    - When closing, a new array is allocated via vstack (copy).
    """
    _assert_xy(points)
    if _is_exactly_closed(points, tol):
        return points
    # Append the first vertex to the end (allocate new array)
    return np.vstack((points, points[0]))


def signed_area(points_closed: np.ndarray) -> float:
    """
    Shoelace signed area for a *closed* polygonal loop.

    Conventions
    -----------
    - Positive area => counter-clockwise (CCW) orientation.
    - The input may be either explicitly closed (first==last) or a simple loop
      whose first and last will be treated as connected for area computation.

    Parameters
    ----------
    points_closed : np.ndarray
        (N, 2) array. If not explicitly closed, the formula implicitly closes it.

    Returns
    -------
    float
        Signed area (units^2). Positive for CCW, negative for CW.

    Raises
    ------
    ValueError
        If input is not (N, 2) or N < 3.

    Numerical note
    --------------
    - Duplicate last==first rows contribute a zero-length edge and do not affect the sum.
    """
    _assert_xy(points_closed)
    if points_closed.shape[0] < 3:
        raise ValueError("Need at least 3 points to compute area.")
    x = points_closed[:, 0]
    y = points_closed[:, 1]
    # Roll by -1 to represent edges (i -> i+1), implicitly connects last->first
    area2 = np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))
    return 0.5 * float(area2)


def orientation(points_closed: np.ndarray) -> str:
    """
    Return "CCW" if the loop is counter-clockwise, else "CW".

    Notes
    -----
    - Uses `signed_area`. Zero area (degenerate polygons) is treated as "CW"
      by convention to avoid returning an ambiguous value.
    - If your pipeline is sensitive around near-zero areas, add a zero-tolerance
      gate here and classify |area| <= tol as CW or raise.
    """
    a = signed_area(points_closed)
    return "CCW" if a > 0.0 else "CW"


def sort_loop_ccw(points_closed: np.ndarray,
                  tol_close: float = 1e-9) -> np.ndarray:
    """
    Return a loop that is:
      1) Explicitly closed (last row equals first within tol),
      2) Counter-clockwise (CCW) oriented.

    Behavior
    --------
    - If the loop is open, it will be closed by appending the first vertex.
    - If orientation is CW (area <= 0), the order is reversed (excluding the
      duplicated last row if present) and then re-closed to ensure consistency.
    - The function is *deterministic*: no sorting by centroid angle is done
      (we assume input already represents a connected loop order).

    Parameters
    ----------
    points_closed : np.ndarray
        (N, 2) array representing a loop (open or closed).
    tol_close : float
        Tolerance for the closure predicate (rtol fixed at 0).

    Returns
    -------
    np.ndarray
        Closed, CCW-oriented loop of shape (M, 2).

    Raises
    ------
    ValueError
        If `points_closed` is not (N, 2) or N < 3.
    """
    _assert_xy(points_closed)
    if points_closed.shape[0] < 3:
        raise ValueError("Need at least 3 points to form a loop.")

    P = ensure_closed(points_closed, tol=tol_close)

    if orientation(P) == "CCW":
        return P

    # Reverse order *excluding* the duplicate last point (if present), then re-close.
    # This preserves vertex order deterministically (no angular re-sorting).
    if _is_exactly_closed(P, tol_close):  # Now from validation module
        core = P[:-1][::-1]
    else:
        core = P[::-1]
    return ensure_closed(core, tol=tol_close)


# -----------------------
# Optional: utility
# -----------------------
def close_and_orient(points: np.ndarray,
                     desired: str = "CCW",
                     tol_close: float = 1e-9) -> np.ndarray:
    """
    Convenience wrapper to:
      (1) close the loop, and
      (2) enforce desired orientation ("CCW" or "CW").

    Parameters
    ----------
    points : np.ndarray
        (N, 2) array (open or closed).
    desired : str
        "CCW" or "CW".
    tol_close : float
        Tolerance for closure check (rtol fixed at 0).

    Returns
    -------
    np.ndarray
        Closed loop with desired orientation.

    Raises
    ------
    ValueError
        If `desired` is not one of {"CCW","CW"}.

    Determinism
    -----------
    - The only reordering performed is a full reversal when needed; no re-sorting.
    """
    if desired not in ("CCW", "CW"):
        raise ValueError("desired must be 'CCW' or 'CW'.")
    P = ensure_closed(points, tol=tol_close)
    cur = orientation(P)
    if cur == desired:
        return P
    # flip orientation deterministically (exclude duplicate last row if present), then re-close
    if _is_exactly_closed(P, tol_close):  # Now from validation module
        core = P[:-1][::-1]
    else:
        core = P[::-1]
    return ensure_closed(core, tol=tol_close)
