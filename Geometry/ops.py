# -*- coding: utf-8 -*-
# Flowxus/geometry/ops.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/10/2025 (Updated: 8/24/2025)

Purpose:
--------
Pure geometry utilities for 2D airfoil-like curves. NumPy-based, with no plot or file I/O.
These helpers are import-safe and lightweight, intended to be used by higher-level modules
(e.g., GeometryLoader, DomainBuilder) without side effects.

Main Tasks:
-----------
    1. Robust shape checks for point clouds (Nx2).
    2. Basic geometric queries (LE/TE/chord).
    3. Transformations (normalization, ensure closed).
    4. Data hygiene (drop consecutive duplicates).
    5. Additional pure helpers used by metrics/meshing:
       - cumulative_arclength(points)
       - signed_area(points) and orientation(points)
       - curvature_polyline(points, window)
       - le_te_indices(points)
       - dist_along_curve(points, ref_idx)
"""

import numpy as np
from typing import Optional, Tuple
from geometry.topology.indices import le_te_indices as _le_te_topo
from geometry.topology.loop import signed_area as _signed_area_topo
from geometry.topology.loop import orientation as _orientation_topo


def drop_consecutive_duplicates(pts: np.ndarray, tol: float = 0.0) -> np.ndarray:
    """
    Remove exact (or tol-close) **consecutive** duplicates to avoid zero-length segments.
    """
    if pts is None or pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError("Expected (N,2) float array for points.")
    if pts.shape[0] <= 1:
        return pts
    keep = [0]
    for i in range(1, pts.shape[0]):
        if not np.allclose(pts[i], pts[i - 1], atol=tol, rtol=0.0):
            keep.append(i)
    return pts[np.array(keep, dtype=int)]


def leading_edge(points: np.ndarray) -> np.ndarray:
    """
    Return the leading-edge (LE) point as the vertex with minimum x.

    Raises
    ------
    ValueError
        If `points` is not (N,2) or is empty.
    """
    if points is None or points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected (N,2) array of points.")
    if points.shape[0] == 0:
        raise ValueError("Empty array provided; no points to evaluate leading edge.")
    idx = int(np.argmin(points[:, 0]))
    return points[idx]


def trailing_edge(points: np.ndarray) -> np.ndarray:
    """
    Return the trailing-edge (TE) point as the vertex with maximum x.

    Raises
    ------
    ValueError
        If `points` is not (N,2) or is empty.
    """
    if points is None or points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected (N,2) array of points.")
    if points.shape[0] == 0:
        raise ValueError("Empty array provided; no points to evaluate trailing edge.")
    idx = int(np.argmax(points[:, 0]))
    return points[idx]


def chord_length(points: np.ndarray) -> float:
    """
    Compute chord length as TE.x − LE.x.

    Notes
    -----
    With LE defined as min-x and TE as max-x, this is guaranteed ≥ 0 for valid airfoils.

    Raises
    ------
    ValueError
        If `points` is not (N,2).
    """
    _assert_xy(points)
    le = leading_edge(points)
    te = trailing_edge(points)
    return float(te[0] - le[0])


def normalize(points: np.ndarray,
              translate_to_le: bool = True,
              scale_to_chord1: bool = True) -> np.ndarray:
    """
    Normalize a 2D airfoil polyline in place.

    Steps
    -----
    1) If `translate_to_le`, shift so LE→(0,0).
    2) If `scale_to_chord1`, scale so chord length becomes 1.0.

    Raises
    ------
    ValueError
        If input is not (N,2) or computed chord length ≤ 0.
    """
    _assert_xy(points)
    out = points.copy()
    if translate_to_le:
        le = leading_edge(out)
        out = out - le
    if scale_to_chord1:
        chord = chord_length(out)
        if chord <= 0:
            raise ValueError("Invalid chord length (<=0). Check geometry alignment.")
        out = out / chord
    return out


def ensure_closed(points: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """
    Ensure the polyline is closed: if last point ≠ first (within `tol`), append the first.

    Parameters
    ----------
    tol : float
        Absolute tolerance for closure check on x and y.

    Returns
    -------
    np.ndarray
        Either the original array (already closed) or a new array with the first
        point appended to the end.

    Raises
    ------
    ValueError
        If input is not (N,2).
    """
    _assert_xy(points)
    p0, pN = points[0], points[-1]
    if not np.allclose(p0, pN, atol=tol, rtol=0.0):
        return np.vstack([points, p0])
    return points


def _assert_xy(points: Optional[np.ndarray]) -> None:
    """
    Guard that `points` is a real 2D array with exactly two columns.

    Raises
    ------
    ValueError
        If `points` is None, not 2D, or does not have width 2.
    """
    if points is None:
        raise ValueError("No geometry provided (points is None).")
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Expected (N,2) float array for points, got shape {}.".format(points.shape))

# -----------------
# New helpers (metrics support)
# -----------------

def cumulative_arclength(points: np.ndarray) -> np.ndarray:
    """
    Return cumulative arclength along a **closed** or **open** polyline.
    If closed, the last point may equal the first; function works for both.
    Returns an array S of shape (N,) with S[0]=0 and S[-1]=total length.
    """
    _assert_xy(points)
    seg = np.linalg.norm(points[1:] - points[:-1], axis=1)
    return np.concatenate(([0.0], np.cumsum(seg)))


def signed_area(points: np.ndarray) -> float:
    """
    Delegates to geometry.topology.loop.signed_area.
    """
    return _signed_area_topo(points)

def orientation(points: np.ndarray) -> str:
    """
    Delegates to geometry.topology.loop.orientation.
    """
    return _orientation_topo(points)


def le_te_indices(points_closed: np.ndarray) -> Tuple[int, int]:
    """
    Delegates to geometry.topology.loop.le_te_indices.
    """
    return _le_te_topo(points_closed)

def _central_tangent_closed(points_closed: np.ndarray) -> np.ndarray:
    """
    Unit tangent at each vertex on a closed ring (excluding last duplicate)
    """
    P = points_closed[:-1]
    N = P.shape[0]
    fwd = P[(np.arange(N) + 1) % N] - P
    bwd = P - P[(np.arange(N) - 1) % N]
    t = 0.5 * (fwd + bwd)
    nrm = np.linalg.norm(t, axis=1)
    nrm[nrm == 0] = 1.0
    return t / nrm[:, None]


def curvature_polyline(points_closed: np.ndarray, window: int = 7) -> np.ndarray:
    """
    Signed curvature along a **closed** polyline using dt/ds with light smoothing.
    Returns an array of length N-1 (excluding duplicated last point).
    """
    _assert_xy(points_closed)
    if not np.allclose(points_closed[0], points_closed[-1], atol=1e-12, rtol=0.0):
        raise ValueError("Expected a CLOSED polyline (first==last).")
    t = _central_tangent_closed(points_closed)
    s = cumulative_arclength(points_closed)[:-1]
    dt_x = np.gradient(t[:, 0], s)
    dt_y = np.gradient(t[:, 1], s)
    k = np.hypot(dt_x, dt_y)
    sign = np.sign(t[:, 0] * dt_y - t[:, 1] * dt_x)
    k_signed = k * sign
    # moving-average smoothing over index window
    N = k_signed.shape[0]
    w = max(3, int(window) | 1)
    half = w // 2
    out = np.empty_like(k_signed)
    for i in range(N):
        j0 = max(0, i - half)
        j1 = min(N, i + half + 1)
        out[i] = np.mean(k_signed[j0:j1])
    return out


def dist_along_curve(points_closed: np.ndarray, ref_idx_closed: int) -> np.ndarray:
    """
    Shortest along-loop distance from reference index to all vertices on a **closed** polyline.
    Returns an array d of length N-1 (excluding duplicate last point). Distances are in the
    same units as the input coordinates.
    """
    _assert_xy(points_closed)
    if not np.allclose(points_closed[0], points_closed[-1], atol=1e-12, rtol=0.0):
        raise ValueError("Expected a CLOSED polyline (first==last).")
    S = cumulative_arclength(points_closed)
    N = points_closed.shape[0] - 1
    if ref_idx_closed < 0 or ref_idx_closed >= N:
        raise ValueError("ref_idx_closed out of range")
    total = float(S[-1])
    d = S[:-1] - S[ref_idx_closed]
    d[d < 0] += total
    return np.minimum(d, total - d)
