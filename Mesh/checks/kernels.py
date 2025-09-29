# -*- coding: utf-8 -*-
# Flowxus/mesh/check/kernels.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Lightweight 2D geometry kernels for mesh checks. Numpy-only routines that
operate in the XY plane and are safe for batch/CI use.

Main Tasks:
-----------
   - Basic primitives: signed areas, edge lengths, triangle angles.
   - Robust predicates: segment intersection, point-in-triangle/quad.
   - Consistent XY slicing for inputs shaped (..., ≥2).

Notes:
------
   - Inputs may have ≥2 coordinates; only X,Y are used (Z ignored).
   - Tolerances (`eps`) are conservative defaults; callers may override.
   - All functions return plain Python floats/bools where appropriate.
"""

from typing import Tuple
import numpy as np


# ---------------------------
# Basic vector helpers
# ---------------------------
def _xy(a: np.ndarray) -> np.ndarray:
    """
    Return the X,Y slice of `a`, ensuring shape (..., 2). Extra coords are ignored.
    """
    a = np.asarray(a)
    if a.shape[-1] > 2:
        return a[..., :2]
    return a


# ---------------------------
# Areas & angles
# ---------------------------
def signed_area_tri(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """
    Signed area of triangle ABC in XY (CCW > 0).
    """
    a = _xy(a); b = _xy(b); c = _xy(c)
    return 0.5 * float((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]))


def poly_area(coords: np.ndarray) -> float:
    """
    Signed polygon area in XY (CCW positive).
    coords: (k,2) or (k,>=2).
    """
    P = _xy(np.asarray(coords))
    x = P[:, 0]; y = P[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def angles_tri(a: np.ndarray, b: np.ndarray, c: np.ndarray, deg: bool = True) -> Tuple[float, float, float]:
    """
    Internal angles at (A,B,C) of triangle ABC.
    Uses law of cosines with safe clamping.
    """
    A = _xy(a); B = _xy(b); C = _xy(c)
    vAB = B - A; vAC = C - A
    vBA = A - B; vBC = C - B
    vCA = A - C; vCB = B - C

    la = np.linalg.norm(vBC)  # opposite A
    lb = np.linalg.norm(vCA)  # opposite B
    lc = np.linalg.norm(vAB)  # opposite C

    # avoid division by zero with tiny epsilon
    eps = 1e-30
    cosA = (lb*lb + lc*lc - la*la) / max(2.0*lb*lc, eps)
    cosB = (lc*lc + la*la - lb*lb) / max(2.0*lc*la, eps)
    cosC = (la*la + lb*lb - lc*lc) / max(2.0*la*lb, eps)

    cosA = float(np.clip(cosA, -1.0, 1.0))
    cosB = float(np.clip(cosB, -1.0, 1.0))
    cosC = float(np.clip(cosC, -1.0, 1.0))

    Aang = np.arccos(cosA)
    Bang = np.arccos(cosB)
    Cang = np.arccos(cosC)
    if deg:
        Aang = np.degrees(Aang); Bang = np.degrees(Bang); Cang = np.degrees(Cang)
    return (float(Aang), float(Bang), float(Cang))


def edge_length(p: np.ndarray, q: np.ndarray) -> float:
    """
    Euclidean length |PQ| in XY.
    """
    P = _xy(p); Q = _xy(q)
    return float(np.linalg.norm(Q - P))


# ---------------------------
# Segment intersection & point tests
# ---------------------------
def segments_intersect(p: np.ndarray, q: np.ndarray, r: np.ndarray, s: np.ndarray, eps: float = 1e-12) -> bool:
    """
    Robust 2D segment intersection including collinear-overlap cases.

    Returns True if [p,q] intersects [r,s] (touching counts as intersection).
    """
    p = _xy(p); q = _xy(q); r = _xy(r); s = _xy(s)

    def orient(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])

    o1 = orient(p, q, r)
    o2 = orient(p, q, s)
    o3 = orient(r, s, p)
    o4 = orient(r, s, q)

    # Proper straddle on both segments
    if (o1 * o2 < -eps) and (o3 * o4 < -eps):
        return True

    # Collinear checks: projection overlap along both axes
    def on_segment(u, v, w):
        """w on segment uv (inclusive) assuming collinearity."""
        return (min(u[0], v[0]) - eps <= w[0] <= max(u[0], v[0]) + eps) and \
               (min(u[1], v[1]) - eps <= w[1] <= max(u[1], v[1]) + eps)

    if abs(o1) <= eps and on_segment(p, q, r): return True
    if abs(o2) <= eps and on_segment(p, q, s): return True
    if abs(o3) <= eps and on_segment(r, s, p): return True
    if abs(o4) <= eps and on_segment(r, s, q): return True
    return False


def point_in_triangle(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray, eps: float = 1e-14) -> bool:
    """
    Barycentric point-in-triangle test (boundary inclusive).
    """
    P = _xy(p); A = _xy(a); B = _xy(b); C = _xy(c)
    v0 = C - A; v1 = B - A; v2 = P - A
    den = v0[0]*v1[1] - v0[1]*v1[0]
    if abs(den) < eps:
        return False
    u = (v2[0]*v1[1] - v2[1]*v1[0]) / den
    v = (v2[0]*v0[1] - v2[1]*v0[0]) / -den
    w = 1.0 - u - v
    return (u >= -eps) and (v >= -eps) and (w >= -eps)


def point_in_quad(p: np.ndarray, quad4: np.ndarray, eps: float = 1e-14) -> bool:
    """
    Point-in-quad via split into two triangles: (0,1,2) ∪ (0,2,3).
    quad4: array-like shape (4,2) or (4,>=2).
    """
    Q = _xy(np.asarray(quad4))
    return point_in_triangle(p, Q[0], Q[1], Q[2], eps) or point_in_triangle(p, Q[0], Q[2], Q[3], eps)
