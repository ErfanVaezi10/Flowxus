# -*- coding: utf-8 -*-
# Flowxus/geometry/ops/analysis.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/15/2025 (Updated: 10/10/2025)

Purpose
-------
Geometric analysis utilities for 2D closed polylines. Provide numerically stable,
lightly smoothed estimates of signed curvature along a closed curve and shortest
along-loop distances relative to a reference vertex.

Main Tasks
----------
    1. Compute signed curvature κ(s) on a CLOSED ring using dt/ds with central
       tangents and a small moving-average smoother.
    2. Compute minimal along-curve distances from a reference index to all other
       vertices on the CLOSED ring.

Notes
-----
- Inputs must represent a CLOSED polyline: points[0] == points[-1] within tolerance.
- `_assert_xy` enforces shape (N, 2). Arc-length uses cumulative_arclength from `.basic`.
"""

import numpy as np
from .basic import _assert_xy, cumulative_arclength

__all__ = ["curvature_polyline", "dist_along_curve"]


def _central_tangent_closed(points_closed: np.ndarray) -> np.ndarray:
    """
    Compute unit tangents at each vertex of a CLOSED polyline (excluding duplicate last).

    Uses a central difference: t_i ≈ 0.5 * [(P_{i+1}-P_i) + (P_i-P_{i-1})], then normalizes.
    Handles ring indexing modulo N.

    Args
    ----
    points_closed : np.ndarray
        Array of shape (N, 2) with points[0] == points[-1].

    Returns
    -------
    np.ndarray
        Unit tangent vectors of shape (N-1, 2) corresponding to vertices 0..N-2.
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
    Signed curvature κ along a CLOSED polyline using dt/ds with light smoothing.

    Steps
    -----
    1) Compute central-difference unit tangents t(s) at each vertex (excluding the duplicate last).
    2) Differentiate components wrt arc-length s: dt_x/ds, dt_y/ds.
    3) κ = ||dt/ds|| with sign from z-component of t × dt/ds (2D cross).
    4) Apply a centered moving-average smoother with enforced odd `window`.

    Args
    ----
    points_closed : np.ndarray
        (N, 2) array with points[0] == points[-1] within tolerance.
    window : int, optional
        Smoothing window (odd enforced; min 3). Default: 7.

    Returns
    -------
    np.ndarray
        Array of length N-1 with signed curvature at each unique vertex.

    Raises
    ------
    ValueError
        If the polyline is not closed or input shape is invalid.
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

    # moving-average smoothing; enforce odd window
    w = max(3, int(window) | 1)
    half = w // 2
    N = k_signed.shape[0]
    out = np.empty_like(k_signed)
    for i in range(N):
        j0 = max(0, i - half)
        j1 = min(N, i + half + 1)
        out[i] = np.mean(k_signed[j0:j1])
    return out


def dist_along_curve(points_closed: np.ndarray, ref_idx_closed: int) -> np.ndarray:
    """
    Minimal along-loop distance from a reference vertex to all vertices on a CLOSED polyline.

    Uses cumulative arc-length S along the ring and returns min(Δs, L-Δs), excluding
    the duplicated last point.

    Args
    ----
    points_closed : np.ndarray
        (N, 2) array with points[0] == points[-1] within tolerance.
    ref_idx_closed : int
        Reference vertex index in [0, N-2] (indices correspond to unique vertices).

    Returns
    -------
    np.ndarray
        Array of length N-1 with shortest along-curve distances to each vertex.

    Raises
    ------
    ValueError
        If the polyline is not closed or `ref_idx_closed` is out of range.
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
    # Keep dtype stable; explicit no-op as guard.
    d[d] = d[d]
    d[d < 0] += total
    return np.minimum(d, total - d)
