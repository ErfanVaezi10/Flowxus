# -*- coding: utf-8 -*-
# Flowxus/mesh/stats/data/bl.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Boundary-layer diagnostics for 2D meshes near a named wall boundary. This module derives
near-wall presence, first-layer thickness stats, and growth/thickness estimates from cell
centroids and distances to the specified wall polyline.

Main Tasks:
-----------
    1) Extract wall points for a named boundary from mesh connectivity.
    2) Compute cell centroids (triangles and quads) and distances to the wall.
    3) BL presence check within a thin near-wall band (quad presence & wall coverage).
    4) First-layer thickness statistics from quad centroids.
    5) Growth ratio & BL thickness estimate within an expanded near-wall band.

Notes:
------
- Works with `MeshData` objects providing:
  - `points` (N,3), `tris` (T,3) or None, `quads` (Q,4) or None,
  - `bbox` = [xmin, xmax, ymin, ymax], and a `line_tags` dict mapping names to
    line indices in either `lines` or `lines_conn` (both (L,2) node indices).
- Distances are Euclidean in the XY plane (z ignored).
"""

import numpy as np
from typing import Dict, Optional, Tuple
from .reader import MeshData


# ----------------------
# Internal helper logic
# ----------------------
def _centroids(
    points: np.ndarray,
    tris: Optional[np.ndarray],
    quads: Optional[np.ndarray],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute 2D centroids for tris and quads, plus an indicator array.

    The indicator `which` uses:
        0 → triangle centroid
        1 → quadrilateral centroid

    Parameters
    ----------
    points : np.ndarray
        (N, 3) node coordinates (z is ignored).
    tris : np.ndarray or None
        (T, 3) triangle connectivity or None if absent.
    quads : np.ndarray or None
        (Q, 4) quadrilateral connectivity or None if absent.

    Returns
    -------
    (np.ndarray, np.ndarray)
        centroids : (M, 2) XY centroids stacked (tris first if present, then quads).
        which     : (M,) int array (0 for tri, 1 for quad). Empty if no cells.
    """
    cs = []
    which = []

    if tris is not None and tris.shape[0] > 0:
        P = points[tris, :2]
        cs.append(np.mean(P, axis=1))
        which.append(np.zeros((tris.shape[0],), dtype=int))

    if quads is not None and quads.shape[0] > 0:
        P = points[quads, :2]
        cs.append(np.mean(P, axis=1))
        which.append(np.ones((quads.shape[0],), dtype=int))

    if not cs:
        return np.zeros((0, 2), dtype=float), np.zeros((0,), dtype=int)

    return np.vstack(cs), np.concatenate(which)


def _wall_points(m: MeshData, wall_name: str) -> Optional[np.ndarray]:
    """
    Retrieve unique XY points belonging to a named wall line.

    Looks up `wall_name` in `m.line_tags`, then extracts node indices from either
    `m.lines` or `m.lines_conn` (whichever is present and valid), and returns the
    corresponding points in XY.

    Parameters
    ----------
    m : MeshData
        Mesh container with connectivity/geometry.
    wall_name : str
        Boundary name to extract.

    Returns
    -------
    np.ndarray or None
        (K, 2) array of XY wall points, or None if the wall is missing/unavailable.
    """
    if wall_name not in m.line_tags:
        return None

    # Prefer `lines` if present; fall back to `lines_conn`.
    lines = getattr(m, "lines", None)
    if isinstance(lines, np.ndarray) and lines.ndim == 2 and lines.shape[1] == 2:
        idx = m.line_tags[wall_name]
        sel = lines[idx]
        nodes = np.unique(sel.reshape(-1))
        return m.points[nodes, :2]

    lines_conn = getattr(m, "lines_conn", None)
    if isinstance(lines_conn, np.ndarray) and lines_conn.ndim == 2 and lines_conn.shape[1] == 2:
        idx = m.line_tags[wall_name]
        sel = lines_conn[idx]
        nodes = np.unique(sel.reshape(-1))
        return m.points[nodes, :2]

    return None


def _dist_to_wall(cent: np.ndarray, wall_pts: np.ndarray) -> np.ndarray:
    """
    Compute the minimum XY distance from each centroid to the wall point set.

    Parameters
    ----------
    cent : np.ndarray
        (M, 2) centroid coordinates.
    wall_pts : np.ndarray
        (K, 2) wall point coordinates.

    Returns
    -------
    np.ndarray
        (M,) array of minimum distances for each centroid.
    """
    d = np.empty((cent.shape[0],), dtype=float)
    for i, c in enumerate(cent):
        d[i] = np.min(np.linalg.norm(wall_pts - c[None, :], axis=1))
    return d


# ----------------------
# Public BL diagnostics
# ----------------------
def presence(m: MeshData, wall_name: str = "airfoil", band_frac: float = 0.05) -> Dict:
    """
    Detect near-wall quad presence and wall coverage within a thin band.

    Method
    ------
    - Build centroids of all cells.
    - Compute distance to the named wall polyline.
    - Define a near-wall band of width `tol = max(1e-12, band_frac * L)`, where
      `L` is the larger of domain width/height from `m.bbox`.
    - Report whether any quads lie in this band and estimate coverage fraction:
      the fraction of wall points having at least one near-band centroid within
      radius `r = tol`.

    Parameters
    ----------
    m : MeshData
        Mesh container.
    wall_name : str, optional
        Boundary name used as "wall" (default "airfoil").
    band_frac : float, optional
        Fraction of domain size used to define the near-wall band (default 0.05).

    Returns
    -------
    dict
        {
          "near_band_width": float,
          "quad_present_near_wall": bool,
          "wall_coverage_fraction": float in [0,1],
          "n_wall_points": int,
          "n_near_cells": int
        }
        Empty dict if wall or centroids are unavailable.
    """
    wall = _wall_points(m, wall_name)
    if wall is None or wall.shape[0] == 0:
        return {}

    cent, which = _centroids(m.points, m.tris, m.quads)
    if cent.shape[0] == 0:
        return {}

    d = _dist_to_wall(cent, wall)
    L = max(m.bbox[1] - m.bbox[0], m.bbox[3] - m.bbox[2])
    tol = max(1e-12, band_frac * L)

    near = d <= tol
    has_quads = np.any((which == 1) & near)

    # Coverage estimate: fraction of wall points "seen" by near-band centroids
    r = tol
    covered = 0
    for wp in wall:
        if np.any(np.linalg.norm(cent[near] - wp[None, :], axis=1) <= r):
            covered += 1
    frac = covered / float(wall.shape[0])

    return {
        "near_band_width": float(tol),
        "quad_present_near_wall": bool(has_quads),
        "wall_coverage_fraction": float(frac),
        "n_wall_points": int(wall.shape[0]),
        "n_near_cells": int(np.count_nonzero(near)),
    }


def first_layer(
    m: MeshData,
    wall_name: str = "airfoil",
    target_first_layer: Optional[float] = None,
) -> Dict:
    """
    Describe first-layer thickness statistics from quad centroids.

    The first-layer proxy is the distance from quad centroids to the wall. Returns
    basic stats and percentiles. If `target_first_layer` is provided (>0), ratios
    to target are included.

    Parameters
    ----------
    m : MeshData
        Mesh container.
    wall_name : str, optional
        Boundary name used as "wall" (default "airfoil").
    target_first_layer : float or None, optional
        Desired first-layer thickness; enables ratio metrics.

    Returns
    -------
    dict
        {
          "min","max","mean","std","p5","p50","p95","count",
          ["target","ratio_p5_to_target","ratio_mean_to_target" if target provided]
        }
        Empty dict if wall/quad centroids are unavailable.
    """
    wall = _wall_points(m, wall_name)
    if wall is None or wall.shape[0] == 0 or m.quads is None or m.quads.shape[0] == 0:
        return {}

    cent_all, which = _centroids(m.points, m.tris, m.quads)
    quads_cent = cent_all[which == 1]
    if quads_cent.shape[0] == 0:
        return {}

    d = _dist_to_wall(quads_cent, wall)
    if d.size == 0:
        return {}

    stats = {
        "min": float(np.min(d)),
        "max": float(np.max(d)),
        "mean": float(np.mean(d)),
        "std": float(np.std(d)),
        "p5": float(np.percentile(d, 5)),
        "p50": float(np.percentile(d, 50)),
        "p95": float(np.percentile(d, 95)),
        "count": int(d.size),
    }

    if target_first_layer is not None and target_first_layer > 0:
        stats["target"] = float(target_first_layer)
        stats["ratio_p5_to_target"] = float(stats["p5"] / target_first_layer)
        stats["ratio_mean_to_target"] = float(stats["mean"] / target_first_layer)

    return stats


def growth_and_thickness(
    m: MeshData,
    wall_name: str = "airfoil",
    target_ratio: Optional[float] = None,
    target_thickness: Optional[float] = None,
    band_frac: float = 0.15,
    nbins: int = 6,
) -> Dict:
    """
    Estimate BL growth ratio statistics and total BL thickness near the wall.

    Method
    ------
    - Consider quad centroid distances `d` to wall points.
    - Restrict to a near-wall band of width `band = band_frac * L` (L from bbox).
    - Bin the in-band distances into `nbins` uniform bins and compute the mean
      distance per occupied bin; derive multiplicative growth ratios between
      successive mean distances (median/p90/max reported).
    - Thickness estimate is `max(d_band) - min(d_band)` (span of in-band distances).

    Parameters
    ----------
    m : MeshData
        Mesh container.
    wall_name : str, optional
        Boundary name used as "wall" (default "airfoil").
    target_ratio : float or None, optional
        Desired growth ratio between successive layers; enables ratio-to-target.
    target_thickness : float or None, optional
        Desired BL thickness; enables thickness-to-target.
    band_frac : float, optional
        Fraction of domain size for the in-band window (default 0.15).
    nbins : int, optional
        Number of bins for averaging distances (default 6; min enforced to 3).

    Returns
    -------
    dict
        {
          "n_samples": int,
          "band_width": float,
          "thickness_est": float,
          "growth_ratio": {
              "n": int, "median": float, "p90": float, "max": float,
              ["target","median_to_target" if target_ratio]
          },
          ["thickness_to_target" if target_thickness]
        }
        For very sparse data (<3 samples in band), returns a minimal dict with a
        coarse thickness estimate and sample count.
    """
    wall = _wall_points(m, wall_name)
    if wall is None or wall.shape[0] == 0 or m.quads is None or m.quads.shape[0] == 0:
        return {}

    cent_all, which = _centroids(m.points, m.tris, m.quads)
    quads_cent = cent_all[which == 1]

    d = _dist_to_wall(quads_cent, wall)
    if d.size == 0:
        return {}

    L = max(m.bbox[1] - m.bbox[0], m.bbox[3] - m.bbox[2])
    band = band_frac * L

    mask = d <= band
    d_band = d[mask]

    # Sparse case: provide coarse thickness only
    if d_band.size < 3:
        thickness = float(np.max(d)) if d.size > 0 else 0.0
        out = {"thickness_est": thickness, "n_samples": int(d_band.size)}
        if target_thickness:
            out["thickness_to_target"] = thickness / float(target_thickness)
        return out

    # Bin in-band distances uniformly and compute mean per occupied bin
    bins = np.linspace(np.min(d_band), np.max(d_band), max(3, nbins))
    inds = np.digitize(d_band, bins, right=True) - 1
    inds = np.clip(inds, 0, len(bins) - 2)

    means = []
    for b in range(len(bins) - 1):
        sel = d_band[inds == b]
        if sel.size > 0:
            means.append(float(np.mean(sel)))

    # Use unique means in ascending order to avoid zero denominators on duplicates
    means = np.array(sorted(set(means)))

    # Compute successive growth ratios
    ratios = []
    for i in range(1, len(means)):
        if means[i - 1] > 0:
            ratios.append(means[i] / means[i - 1])

    thickness = float(np.max(d_band) - np.min(d_band)) if d_band.size > 0 else 0.0

    out = {
        "n_samples": int(d_band.size),
        "band_width": float(band),
        "thickness_est": thickness,
        "growth_ratio": {
            "n": int(len(ratios)),
            "median": float(np.median(ratios)) if ratios else 0.0,
            "p90": float(np.percentile(ratios, 90)) if ratios else 0.0,
            "max": float(np.max(ratios)) if ratios else 0.0,
        },
    }

    if target_ratio and target_ratio > 0:
        out["growth_ratio"]["target"] = float(target_ratio)
        out["growth_ratio"]["median_to_target"] = (
            out["growth_ratio"]["median"] / float(target_ratio) if ratios else 0.0
        )

    if target_thickness and target_thickness > 0:
        out["thickness_to_target"] = thickness / float(target_thickness)

    return out
