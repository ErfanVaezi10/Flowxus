# -*- coding: utf-8 -*-
# Flowxus/mesh/stats/data/quality.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Compute element-quality statistics for 2D meshes (triangles and quads):
For triangles, derive edge-based metrics (area, min/max angle, aspect, skewness).
For quads, derive angular skewness, orthogonality proxy, and a Jacobian sign check.

Main Tasks:
-----------
    1) `tri_quality`:
        - Edge lengths → Heron area.
        - Interior angles (via law of cosines) → min/max angle.
        - Aspect ratio (max edge / min edge).
        - Angular skewness (max deviation from 60°).
        - Aggregate stats: min/max/mean/std/p5/p95 for each metric.
    2) `quad_quality`:
        - Internal angles from consecutive edge directions.
        - Skewness (max |angle-90°|); orthogonality proxy (min |cos(angle)|).
        - Signed polygon area as a coarse Jacobian sign check.
        - Aggregate stats for skew/orthogonality; positive/negative Jacobian fractions.

Notes:
------
- All calculations are performed in the XY plane (z ignored).
- Returns empty dicts if the corresponding element set is absent.
"""

import numpy as np
from .reader import MeshData


def tri_quality(m: MeshData) -> dict:
    """
    Triangle quality metrics and summary statistics.

    Returns an object with counts and per-metric stats:
      - area
      - min_angle / max_angle (degrees)
      - aspect (max edge / min edge)
      - skewness (max |angle - 60°|)

    Parameters
    ----------
    m : MeshData
        Mesh container with `points` (N,3) and `tris` (T,3).

    Returns
    -------
    dict
        {
          "n": int,
          "area": {...},
          "min_angle": {...},
          "max_angle": {...},
          "aspect": {...},
          "skewness": {...}
        }
        Empty dict if no triangles.
    """
    if m.tris is None or m.tris.shape[0] == 0:
        return {}

    pts = m.points
    tris = m.tris
    n = tris.shape[0]

    # Edge lengths
    a = np.linalg.norm(pts[tris[:, 1]] - pts[tris[:, 0]], axis=1)
    b = np.linalg.norm(pts[tris[:, 2]] - pts[tris[:, 1]], axis=1)
    c = np.linalg.norm(pts[tris[:, 0]] - pts[tris[:, 2]], axis=1)

    # Heron's formula for area (robust to minor numeric issues)
    s = 0.5 * (a + b + c)
    area = np.sqrt(np.maximum(s * (s - a) * (s - b) * (s - c), 0.0))

    # Internal angles (degrees) via law of cosines
    angA = np.degrees(np.arccos(np.clip((b**2 + c**2 - a**2) / (2 * b * c), -1.0, 1.0)))
    angB = np.degrees(np.arccos(np.clip((a**2 + c**2 - b**2) / (2 * a * c), -1.0, 1.0)))
    angC = 180.0 - angA - angB

    min_angle = np.minimum(np.minimum(angA, angB), angC)
    max_angle = np.maximum(np.maximum(angA, angB), angC)

    # Aspect ratio: longest edge / shortest edge
    aspect = np.maximum.reduce([a, b, c]) / np.minimum.reduce([a, b, c])

    # Angular skewness: deviation from equilateral (60°)
    skew = np.maximum.reduce([np.abs(angA - 60), np.abs(angB - 60), np.abs(angC - 60)])

    def stats(arr):
        return {
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "p5": float(np.percentile(arr, 5)),
            "p95": float(np.percentile(arr, 95)),
        }

    return {
        "n": n,
        "area": stats(area),
        "min_angle": stats(min_angle),
        "max_angle": stats(max_angle),
        "aspect": stats(aspect),
        "skewness": stats(skew),
    }


def quad_quality(m: MeshData) -> dict:
    """
    Quadrilateral quality metrics and summary statistics.

    Computes:
      - `skewness`: max |internal angle − 90°| (degrees).
      - `orthogonality`: min |cos(internal angle)| (0 is ideal).
      - `jacobian` sign fractions via signed polygon area.

    Parameters
    ----------
    m : MeshData
        Mesh container with `points` (N,3) and `quads` (Q,4).

    Returns
    -------
    dict
        {
          "n": int,
          "skewness": {...},
          "orthogonality": {...},
          "jacobian": {"positive_fraction": float, "negative_fraction": float}
        }
        Empty dict if no quads.
    """
    if m.quads is None or m.quads.shape[0] == 0:
        return {}

    pts = m.points
    quads = m.quads
    n = quads.shape[0]

    skew_vals = []
    ortho_vals = []
    jacobian_signs = []

    for q in quads:
        v = pts[q, :2]  # 4x2 (XY only)

        # Edge vectors and lengths
        edges = [v[(i + 1) % 4] - v[i] for i in range(4)]
        lengths = [np.linalg.norm(e) for e in edges]  # kept for clarity; not used directly below

        # Internal angles from consecutive edges
        angles = []
        for i in range(4):
            u = edges[i - 1] / (np.linalg.norm(edges[i - 1]) + 1e-15)
            w = edges[i] / (np.linalg.norm(edges[i]) + 1e-15)
            ang = np.degrees(np.arccos(np.clip(np.dot(u, w), -1, 1)))
            angles.append(ang)

        # Skewness (90° ideal)
        skew = max([abs(a - 90) for a in angles])
        skew_vals.append(skew)

        # Orthogonality proxy: |cos(angle)| (0 ideal); take worst (max) → use min( |cos| ) across angles
        ortho = min([abs(np.cos(np.radians(a))) for a in angles])
        ortho_vals.append(ortho)

        # Signed polygon area as a simple Jacobian sign check (positive for CCW)
        area = 0.0
        for i in range(4):
            x1, y1 = v[i]
            x2, y2 = v[(i + 1) % 4]
            area += x1 * y2 - x2 * y1
        jacobian_signs.append(np.sign(area))

    skew_vals = np.array(skew_vals)
    ortho_vals = np.array(ortho_vals)
    jacobian_signs = np.array(jacobian_signs)

    def stats(arr):
        return {
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "p5": float(np.percentile(arr, 5)),
            "p95": float(np.percentile(arr, 95)),
        }

    return {
        "n": n,
        "skewness": stats(skew_vals),
        "orthogonality": stats(ortho_vals),
        "jacobian": {
            "positive_fraction": float(np.mean(jacobian_signs > 0)),
            "negative_fraction": float(np.mean(jacobian_signs < 0)),
        },
    }
