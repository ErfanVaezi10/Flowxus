# -*- coding: utf-8 -*-
# Flowxus/mesh/stats/data/sizefield.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Compute element size metrics for meshes, including per-cell "h" estimates (sqrt(area)),
grading across shared edges, and distribution of h vs. distance to a wall boundary.

Main Tasks:
-----------
    1) Compute element areas in 2D (triangles/quads) and derive equivalent size h.
    2) Build neighbor edge map and evaluate size-jump grading statistics.
    3) Bin element sizes by distance to a named wall boundary.
    4) Provide helper utilities for centroids and wall point extraction.

Notes:
------
- Geometry is assumed planar in XY (z ignored).
- Works with `MeshData` containers as produced by `reader.py`.
- Grading ratios are symmetric (max(s0/s1, s1/s0)).
"""

import numpy as np
from typing import Dict, Tuple, Optional
from .reader import MeshData


# -----------------------
# Area / size utilities
# -----------------------
def _tri_area_xy(p0, p1, p2):
    """Signed area of a triangle in XY plane."""
    return 0.5 * abs((p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1]))


def _quad_area_xy(p0, p1, p2, p3):
    """Area of a quad (split into two triangles)."""
    return _tri_area_xy(p0, p1, p2) + _tri_area_xy(p0, p2, p3)


def _cell_sizes(
    points: np.ndarray,
    tris: Optional[np.ndarray],
    quads: Optional[np.ndarray],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute per-cell size h = sqrt(area) for tris and quads.

    Parameters
    ----------
    points : np.ndarray
        (N,3) node coordinates (z ignored).
    tris : np.ndarray or None
        (T,3) connectivity or None.
    quads : np.ndarray or None
        (Q,4) connectivity or None.

    Returns
    -------
    (np.ndarray, np.ndarray)
        sizes : (M,) array of cell size estimates.
        idx   : (M,2) array of [cell_index, cell_type] with cell_type=0 for tri, 1 for quad.
    """
    sizes = []
    idx = []

    if tris is not None and tris.shape[0] > 0:
        p0 = points[tris[:, 0], :2]
        p1 = points[tris[:, 1], :2]
        p2 = points[tris[:, 2], :2]
        area = 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (p2[:, 0] - p0[:, 0]) * (p1[:, 1] - p0[:, 1]))
        h = np.sqrt(np.maximum(area, 0.0))
        sizes.append(h)
        idx.append(np.stack([np.arange(tris.shape[0], dtype=int), np.zeros(tris.shape[0], dtype=int)], axis=1))

    if quads is not None and quads.shape[0] > 0:
        p0 = points[quads[:, 0], :2]
        p1 = points[quads[:, 1], :2]
        p2 = points[quads[:, 2], :2]
        p3 = points[quads[:, 3], :2]
        area = (
            0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (p2[:, 0] - p0[:, 0]) * (p1[:, 1] - p0[:, 1]))
            + 0.5 * np.abs((p2[:, 0] - p0[:, 0]) * (p3[:, 1] - p0[:, 1]) - (p3[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]))
        )
        h = np.sqrt(np.maximum(area, 0.0))
        sizes.append(h)
        idx.append(np.stack([np.arange(quads.shape[0], dtype=int), np.ones(quads.shape[0], dtype=int)], axis=1))

    if not sizes:
        return np.zeros((0,), dtype=float), np.zeros((0, 2), dtype=int)

    return np.concatenate(sizes), np.concatenate(idx)


# -----------------------
# Sizefield metrics
# -----------------------
def grading(m: MeshData) -> Dict:
    """
    Compute size-jump grading across interior edges.

    Method
    ------
    - For each triangle/quad, compute size h = sqrt(area).
    - Build edge→neighbor map of cells (store [index, type]).
    - For edges shared by 2 cells, compute ratio = max(s0/s1, s1/s0).
    - Collect ratios and return statistics.

    Parameters
    ----------
    m : MeshData
        Mesh container.

    Returns
    -------
    dict
        If no valid pairs: {"pairs": 0}
        Otherwise:
        {
          "pairs": int,
          "median","p90","p95","max","mean","std": float
        }
    """
    sizes_tri = np.zeros((0,), dtype=float)
    sizes_quad = np.zeros((0,), dtype=float)

    if m.tris is not None and m.tris.shape[0] > 0:
        P0 = m.points[m.tris[:, 0], :2]
        P1 = m.points[m.tris[:, 1], :2]
        P2 = m.points[m.tris[:, 2], :2]
        area_t = 0.5 * np.abs((P1[:, 0] - P0[:, 0]) * (P2[:, 1] - P0[:, 1]) - (P2[:, 0] - P0[:, 0]) * (P1[:, 1] - P0[:, 1]))
        sizes_tri = np.sqrt(np.maximum(area_t, 0.0))

    if m.quads is not None and m.quads.shape[0] > 0:
        Q0 = m.points[m.quads[:, 0], :2]
        Q1 = m.points[m.quads[:, 1], :2]
        Q2 = m.points[m.quads[:, 2], :2]
        Q3 = m.points[m.quads[:, 3], :2]
        area_q = (
            0.5 * np.abs((Q1[:, 0] - Q0[:, 0]) * (Q2[:, 1] - Q0[:, 1]) - (Q2[:, 0] - Q0[:, 0]) * (Q1[:, 1] - Q0[:, 1]))
            + 0.5 * np.abs((Q2[:, 0] - Q0[:, 0]) * (Q3[:, 1] - Q0[:, 1]) - (Q3[:, 0] - Q0[:, 0]) * (Q2[:, 1] - Q0[:, 1]))
        )
        sizes_quad = np.sqrt(np.maximum(area_q, 0.0))

    # Build edge→cells map
    edge_map = {}
    if m.tris is not None and m.tris.shape[0] > 0:
        for i, tri in enumerate(m.tris):
            for a, b in [(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])]:
                key = (a, b) if a < b else (b, a)
                edge_map.setdefault(key, []).append((i, 0))

    if m.quads is not None and m.quads.shape[0] > 0:
        for i, q in enumerate(m.quads):
            for a, b in [(q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], q[0])]:
                key = (a, b) if a < b else (b, a)
                edge_map.setdefault(key, []).append((i, 1))

    # Ratios across interior edges
    ratios = []
    for cells in edge_map.values():
        if len(cells) != 2:
            continue
        (i0, t0), (i1, t1) = cells

        s0 = sizes_tri[i0] if t0 == 0 and i0 < sizes_tri.size else (
            sizes_quad[i0] if t0 == 1 and i0 < sizes_quad.size else None
        )
        s1 = sizes_tri[i1] if t1 == 0 and i1 < sizes_tri.size else (
            sizes_quad[i1] if t1 == 1 and i1 < sizes_quad.size else None
        )
        if s0 is None or s1 is None:
            continue

        if s0 > 0 and s1 > 0:
            r = s0 / s1 if s0 >= s1 else s1 / s0
            ratios.append(r)

    if not ratios:
        return {"pairs": 0}

    r = np.array(ratios, dtype=float)
    return {
        "pairs": int(r.size),
        "median": float(np.median(r)),
        "p90": float(np.percentile(r, 90)),
        "p95": float(np.percentile(r, 95)),
        "max": float(np.max(r)),
        "mean": float(np.mean(r)),
        "std": float(np.std(r)),
    }


# -----------------------
# Distance-to-wall stats
# -----------------------
def _centroids(
    points: np.ndarray,
    tris: Optional[np.ndarray],
    quads: Optional[np.ndarray],
) -> np.ndarray:
    """
    Compute centroids of tris and quads.

    Returns
    -------
    np.ndarray
        (M,2) array of centroids (XY only).
    """
    cs = []
    if tris is not None and tris.shape[0] > 0:
        P = points[tris, :2]
        cs.append(np.mean(P, axis=1))
    if quads is not None and quads.shape[0] > 0:
        P = points[quads, :2]
        cs.append(np.mean(P, axis=1))
    if not cs:
        return np.zeros((0, 2), dtype=float)
    return np.vstack(cs)


def _wall_points_from_meshdata(m: MeshData, wall_name: str) -> Optional[np.ndarray]:
    """
    Extract wall node coordinates for a named boundary.

    Parameters
    ----------
    m : MeshData
        Mesh container.
    wall_name : str
        Boundary name.

    Returns
    -------
    np.ndarray or None
        (K,2) XY wall points, or None if unavailable.
    """
    if wall_name not in m.line_tags:
        return None
    if hasattr(m, "lines") and isinstance(m.lines, np.ndarray) and m.lines.ndim == 2 and m.lines.shape[1] == 2:
        idx = m.line_tags[wall_name]
        lines = m.lines[idx]
        nodes = np.unique(lines.reshape(-1))
        return m.points[nodes, :2]
    if hasattr(m, "lines_conn"):
        idx = m.line_tags[wall_name]
        lines = m.lines_conn[idx]
        nodes = np.unique(lines.reshape(-1))
        return m.points[nodes, :2]
    return None


def h_vs_distance(m: MeshData, wall_name: str = "airfoil", nbins: int = 30) -> Dict:
    """
    Bin element size h vs. distance to a wall boundary.

    Steps
    -----
    - Compute per-cell sizes.
    - Compute centroid distances to wall points.
    - Bin distances into `nbins` intervals.
    - Aggregate element size stats per bin.

    Parameters
    ----------
    m : MeshData
        Mesh container.
    wall_name : str, optional
        Boundary name (default "airfoil").
    nbins : int, optional
        Number of distance bins (default 30).

    Returns
    -------
    dict
        {
          "bin_edges": [list of floats],
          "stats": [
             {"count": int, "mean": float, "p50": float, "p90": float, "p95": float},
             ...
          ]
        }
        Empty dict if no data available.
    """
    sizes, _ = _cell_sizes(m.points, m.tris, m.quads)
    if sizes.size == 0:
        return {}

    cent = _centroids(m.points, m.tris, m.quads)
    wall_pts = _wall_points_from_meshdata(m, wall_name)
    if wall_pts is None or wall_pts.shape[0] == 0:
        return {}

    # Distances from centroids to nearest wall point
    d = []
    for c in cent:
        dd = np.min(np.linalg.norm(wall_pts - c[None, :], axis=1))
        d.append(dd)
    d = np.array(d, dtype=float)
    if d.size == 0:
        return {}

    bins = np.linspace(np.min(d), np.max(d), nbins + 1) if nbins > 0 else np.array([np.min(d), np.max(d)])
    inds = np.digitize(d, bins, right=True) - 1
    inds = np.clip(inds, 0, len(bins) - 2)

    stats = []
    for b in range(len(bins) - 1):
        mask = inds == b
        if np.any(mask):
            hs = sizes[mask]
            stats.append({
                "count": int(hs.size),
                "mean": float(np.mean(hs)),
                "p50": float(np.percentile(hs, 50)),
                "p90": float(np.percentile(hs, 90)),
                "p95": float(np.percentile(hs, 95)),
            })
        else:
            stats.append({"count": 0})

    return {"bin_edges": bins.tolist(), "stats": stats}
