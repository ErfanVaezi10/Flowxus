# -*- coding: utf-8 -*-
# Flowxus/geometry/metrics/_num.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/21/2025

Purpose:
--------
Private numerical utilities used by metrics modules.

Main Tasks:
-----------
    1. Basic geometry guards (assertions, orientation, LE/TE indices).
    2. Differential geometry:
       - Cumulative arclength,
       - Unit tangents,
       - Curvature estimation with smoothing.
    3. Side segmentation and interpolation (pressure/suction split, common-x grid).
    4. Small vector helpers (angle, normalization).
"""

from __future__ import division
from typing import List, Tuple
import math
import numpy as np
from geometry.topology.indices import le_te_indices as _le_te_topo
from geometry.topology.split import split_sides as _split_sides_topo


# ---------- guards / basics ----------

def assert_closed_xy(pts: np.ndarray) -> None:
    """
    Validate that `pts` is a closed 2D polyline.

    Requirements
    ------------
    - Shape is (N, 2), N >= 4,
    - First and last points are identical within a tight tolerance.

    Raises
    ------
    ValueError
        If the array is not 2D, has wrong width, is too short, or is not closed.
    """
    if pts is None or pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError("Expected (N,2) array for points.")
    if pts.shape[0] < 4:
        raise ValueError("Need at least 4 points for a closed polyline.")
    if not np.allclose(pts[0], pts[-1], atol=1e-12, rtol=0.0):
        raise ValueError("points_closed must be closed (first point equals last).")


def cumulative_arclength(pts: np.ndarray) -> np.ndarray:
    """
    Return cumulative arclength along a polyline (including the final duplicate point).

    Returns
    -------
    np.ndarray
        Array `s` of length N where s[0]=0 and s[i] is the arclength to vertex i.
    """
    if pts is None or pts.ndim != 2 or pts.shape[1] != 2 or pts.shape[0] < 2:
        raise ValueError("Expected (N,2) with N>=2.")
    seg = np.linalg.norm(pts[1:] - pts[:-1], axis=1)
    return np.concatenate(([0.0], np.cumsum(seg)))


def signed_area(pts: np.ndarray) -> float:
    """
    Compute the signed area of a closed polygon via the shoelace formula.

    Notes
    -----
    Positive sign corresponds to counter-clockwise (CCW) orientation.
    """
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(y[:-1], x[1:]))


def orientation(pts: np.ndarray) -> str:
    """
    Return 'CCW' or 'CW' based on the polygon signed area.
    """
    return "CCW" if signed_area(pts) > 0.0 else "CW"


def le_te_indices(pts: np.ndarray) -> Tuple[int, int]:
    """Delegates to geometry.topology.loop.le_te_indices."""
    return _le_te_topo(pts)


# ---------- differential geometry ----------

def _central_tangent(pts: np.ndarray) -> np.ndarray:
    """
    Compute unit tangents per vertex on the closed ring (excluding duplicate last point).

    Method
    ------
    Central difference on the ring: t_i ≈ ( (p_{i+1} - p_i) + (p_i - p_{i-1}) ) / 2,
    then normalize; zero norms are safely handled.
    """
    P = pts[:-1]
    N = P.shape[0]
    fwd = P[(np.arange(N) + 1) % N] - P
    bwd = P - P[(np.arange(N) - 1) % N]
    t = 0.5 * (fwd + bwd)
    nrm = np.linalg.norm(t, axis=1)
    nrm[nrm == 0] = 1.0
    return t / nrm[:, None]


def curvature_polyline(pts: np.ndarray, window: int = 7) -> np.ndarray:
    """
    Estimate signed curvature κ ≈ |dt/ds| with sign from local rotation; returns length N-1.

    Parameters
    ----------
    pts : np.ndarray
        Closed polyline (first equals last).
    window : int
        Odd window size for moving-average smoothing (minimum 3).

    Returns
    -------
    np.ndarray
        Smoothed signed curvature per vertex (excluding the duplicate last point).
    """
    t = _central_tangent(pts)
    s = cumulative_arclength(pts)[:-1]
    dt_x = np.gradient(t[:, 0], s)
    dt_y = np.gradient(t[:, 1], s)
    k = np.hypot(dt_x, dt_y)
    sign = np.sign(t[:, 0] * dt_y - t[:, 1] * dt_x)
    k_signed = k * sign
    # moving average smoothing
    N = k_signed.shape[0]
    w = max(3, int(window) | 1)  # odd
    half = w // 2
    out = np.empty_like(k_signed)
    for i in range(N):
        j0 = max(0, i - half)
        j1 = min(N, i + half + 1)
        out[i] = np.mean(k_signed[j0:j1])
    return out


# ---------- segmentation / analysis ----------
def split_sides(
    pts: np.ndarray, idx_le: int, idx_te: int, orient: str
) -> Tuple[np.ndarray, np.ndarray, List[int], List[int]]:
    # Keep legacy signature; 'orient' is unused (topology handles rotation internally).
    pressure, suction, pr_1b, su_1b = _split_sides_topo(
        pts, idx_le, idx_te, mode="mean-y", align_to_chord=True
    )
    return pressure, suction, pr_1b, su_1b


def interp_on_common_x(upper: np.ndarray, lower: np.ndarray, n: int = 400):
    """
    Interpolate two polylines onto a common, monotone x-grid.

    Parameters
    ----------
    upper, lower : np.ndarray
        Polylines sampled along each side; will be sorted by x inside this function.
    n : int
        Number of grid points for the common x-grid.

    Returns
    -------
    (xg, yu, yl)
        xg: common x-grid, yu: upper y-values, yl: lower y-values.
    """
    u = upper[np.argsort(upper[:, 0])]
    l = lower[np.argsort(lower[:, 0])]
    xmin = max(np.min(u[:, 0]), np.min(l[:, 0]))
    xmax = min(np.max(u[:, 0]), np.max(l[:, 0]))
    if xmax <= xmin + 1e-12:
        xmin, xmax = np.min(u[:, 0]), np.max(u[:, 0])
    xg = np.linspace(xmin, xmax, n)
    yu = np.interp(xg, u[:, 0], u[:, 1])
    yl = np.interp(xg, l[:, 0], l[:, 1])
    return xg, yu, yl


# ---------- tiny helpers ----------

def angle_deg(v: np.ndarray) -> float:
    """
    Return the angle of vector `v` in degrees (atan2(y, x)).
    """
    return math.degrees(math.atan2(float(v[1]), float(v[0])))


def unit(v: np.ndarray) -> np.ndarray:
    """
    Return the unit vector in the direction of `v`. If ||v||=0, return `v` unchanged.
    """
    n = float(np.linalg.norm(v))
    if n == 0.0:
        return v
    return v / n
