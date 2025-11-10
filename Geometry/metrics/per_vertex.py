# -*- coding: utf-8 -*-
# Flowxus/geometry/metrics/per_vertex.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/22/2025

Purpose:
--------
Compute per-vertex scalars for ML-driven meshing and CSV export. Generates fine-grained
geometric attributes to support adaptive meshing strategies. Captures local geometric
behavior essential for optimal mesh density predictions.

Main Tasks:
-----------
    1. Validate closed polyline input.
    2. Compute normalized arclength s and smoothed curvature κ.
    3. Assign side mask (0=pressure, 1=suction) from index ranges.
    4. Compute along-curve distances to LE and TE.
    5. Return per-vertex records and provide CSV writer.

Notes:
------
- Input curve must be CLOSED (first point equals last).
- Geometry is assumed to be in chord units (after your normalization pipeline).
- Indices in `ranges` and LE/TE are expected to be **1-based** on the CLOSED array.
"""

from __future__ import division
from typing import Dict, List
import csv
import numpy as np
from ._num import assert_closed_xy, cumulative_arclength, curvature_polyline


def compute_per_vertex_scalars(
    points_closed: np.ndarray,
    ranges: Dict[str, List[int]],
    le_idx_1based: int,
    te_idx_1based: int,
) -> List[Dict[str, float]]:
    """
    Compute minimal per-vertex payload for meshing/ML.

    Parameters
    ----------
    points_closed : np.ndarray
        Closed (N,2) array of 2D points; first and last points must be identical.
    ranges : Dict[str, List[int]]
        1-based inclusive index ranges on the CLOSED array defining sides:
        - ranges["pressure"] = [i0, i1]
        - ranges["suction"]  = [i0, i1]
        Ranges may wrap around the end of the array; this function handles wrapping.
    le_idx_1based : int
        Leading-edge index (1-based) on the CLOSED array.
    te_idx_1based : int
        Trailing-edge index (1-based) on the CLOSED array.

    Returns
    -------
    List[Dict[str, float]]
        A list (length N-1) of row dicts (1 row per unique vertex, excluding the
        duplicate last point) with the following keys:
          - "id":              1..N-1 (float; stable CSV dtype)
          - "x", "y":          vertex coordinates
          - "s":               cumulative arclength normalized to [0, 1]
          - "kappa_smooth":    smoothed signed curvature κ at the vertex
          - "side":            0 for pressure, 1 for suction
          - "dist_LE_curve":   shortest along-curve distance to LE (in chord units)
          - "dist_TE_curve":   shortest along-curve distance to TE (in chord units)

    Notes
    -----
    - Distances are computed along the **ring** (closed loop) and the shorter of the
      forward/backward traverse is taken. Because geometry is normalized to chord,
      these distances are effectively in chord units.
    - The "s" coordinate is normalized by the **total loop arclength**.
    """
    assert_closed_xy(points_closed)

    # Exclude the duplicated last point from per-vertex output
    N = points_closed.shape[0] - 1
    P = points_closed[:-1]

    # Cumulative arclength and normalized arclength parameter
    S = cumulative_arclength(points_closed)
    S_total = float(S[-1])
    S_norm = S[:-1] / S_total if S_total > 0 else S[:-1]

    # Smoothed signed curvature per vertex (length N)
    kappa = curvature_polyline(points_closed, window=7)

    # Initialize side mask (0=pressure, 1=suction)
    side = np.zeros(N, dtype=int)

    # Fill side mask from 1-based inclusive ranges, handling wrap-around
    pr = ranges.get("pressure", None)
    su = ranges.get("suction", None)
    if pr is not None:
        i0, i1 = int(pr[0]) - 1, int(pr[1]) - 1
        idx = list(range(i0, i1 + 1)) if i0 <= i1 else list(range(i0, N)) + list(range(0, i1 + 1))
        side[np.array(idx, dtype=int)] = 0
    if su is not None:
        i0, i1 = int(su[0]) - 1, int(su[1]) - 1
        idx = list(range(i0, i1 + 1)) if i0 <= i1 else list(range(i0, N)) + list(range(0, i1 + 1))
        side[np.array(idx, dtype=int)] = 1

    # Along-loop shortest distances from LE/TE to each vertex
    le_i = int(le_idx_1based - 1)
    te_i = int(te_idx_1based - 1)

    def dist_from(i_ref: int) -> np.ndarray:
        """
        Shortest along-curve distance from reference vertex `i_ref` to all vertices.

        Uses cumulative arclength on the closed ring and returns min(forward, backward).
        """
        if i_ref < 0 or i_ref >= N:
            raise ValueError("ref index out of range")
        d = S[:-1] - S[i_ref]      # forward distance (may be negative)
        d[d < 0] += S_total        # wrap forward negatives
        return np.minimum(d, S_total - d)

    d_le = dist_from(le_i)
    d_te = dist_from(te_i)

    # Assemble per-vertex rows in a stable column order
    rows: List[Dict[str, float]] = []
    for i in range(N):
        rows.append({
            "id": float(i + 1),
            "x": float(P[i, 0]),
            "y": float(P[i, 1]),
            "s": float(S_norm[i]),
            "kappa_smooth": float(kappa[i]),
            "side": float(side[i]),
            "dist_LE_curve": float(d_le[i]),
            "dist_TE_curve": float(d_te[i]),
        })
    return rows


def write_scalars_csv(rows: List[Dict[str, float]], path: str) -> str:
    """
    Write per-vertex rows to CSV in a stable column order.

    Parameters
    ----------
    rows : List[Dict[str, float]]
        Output of `compute_per_vertex_scalars`.
    path : str
        Destination file path.

    Returns
    -------
    str
        The same `path` for convenience (chainable).
    """
    fieldnames = ["id", "x", "y", "s", "kappa_smooth", "side", "dist_LE_curve", "dist_TE_curve"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fieldnames})
    return path
