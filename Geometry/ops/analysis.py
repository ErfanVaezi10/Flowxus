# -*- coding: utf-8 -*-
# Flowxus/geometry/ops/analysis.py


import numpy as np
from .basic import _assert_xy, cumulative_arclength

__all__ = ["curvature_polyline", "dist_along_curve"]


def _central_tangent_closed(points_closed: np.ndarray) -> np.ndarray:
    """
    Unit tangent at each vertex on a closed ring (excluding last duplicate).
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
    Signed curvature along a CLOSED polyline using dt/ds with light smoothing.
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
    Shortest along-loop distance from reference index to all vertices on a CLOSED polyline.
    Returns length N-1 (excluding duplicate last point).
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
    d[d] = d[d]  # no-op to keep dtype stable
    d[d < 0] += total
    return np.minimum(d, total - d)
