# -*- coding: utf-8 -*-
# Flowxus/mesh/stats/report.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose:
--------
Compute a compact, mesh-quality summary from a mesh file and return a structured dictionary
ready for export (CSV/JSON/Excel) or downstream checks.
The code aggregates: topology/valence, element-quality stats (tri/quad), sizefield grading &
h(distance-to-wall), and boundary-layer diagnostics, then compares key metrics to thresholds.

Main Tasks:
-----------
    1) Load mesh data from `path` using `.data.reader.read`.
    2) Compute:
        - Topology inventory and node/element valence.
        - Triangle/quad quality statistics.
        - Sizefield grading and h vs. wall distance.
        - Boundary-layer presence/first-layer/growth (optional).
    3) Evaluate threshold violations and set an overall "ok" flag.
    4) Return a structured dictionary for easy serialization or inspection.

Notes:
------
    - Thresholds are user-tunable via `thresholds` (merged over defaults).
    - BL checks can be disabled with `include_bl=False`.
    - The `flags.violations` section contains per-metric pass/fail info with observed values.
"""

from typing import Dict, Optional, Any
from .data.reader import read
from .data.topology import inventory, valence
from .data.quality import tri_quality, quad_quality
from .data import sizefield as _sizefield
from .data.bl import (
    presence as bl_presence,
    first_layer as bl_first_layer,
    growth_and_thickness as bl_growth,
)

# ----------------------------
# Default quality thresholds
# ----------------------------
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "tri_min_angle_deg": 20.0,  # p5 of triangle min angle must be >= this
    "tri_aspect_p95": 10.0,     # p95 of triangle aspect ratio must be <= this
    "quad_skew_p95": 0.85,      # p95 of quad skewness must be <= this
    "grading_p95": 2.5,         # p95 of sizefield grading must be <= this
}


def _get(d: Any, *keys: str, default: Any = None) -> Any:
    """
    Safely fetch a nested value from dictionaries.

    Traverses `d[keys[0]][keys[1]]...`. If any key is missing or an
    intermediate value is not a dict, returns `default`.

    Parameters
    ----------
    d : Any
        Root object (usually a dictionary).
    *keys : str
        Sequence of nested keys to traverse.
    default : Any, optional
        Fallback value if the path does not exist (default: None).

    Returns
    -------
    Any
        The found value or `default`.
    """
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def summarize(
    path: str,
    wall_name: str = "airfoil",
    thresholds: Optional[Dict[str, float]] = None,
    include_bl: bool = True,
) -> Dict[str, Any]:
    """
    Build a full mesh-quality summary and threshold evaluation.

    Pipeline
    --------
    1) Read mesh: `m = read(path)`.
    2) Topology & valence: element counts, node/edge/face statistics.
    3) Quality: triangle and quadrilateral metrics (percentiles bundled by helpers).
    4) Sizefield:
        - `grading`: distribution and percentiles of local size ratio.
        - `h_vs_distance`: bin statistics of element size vs. distance to `wall_name`.
    5) Boundary layer (optional): presence, first-layer metrics, growth/thickness.
    6) Thresholds: compare selected metrics to (defaults ⟶ merged with `thresholds`).

    Threshold Checks
    ----------------
    - `tri_min_angle_p5`  >= `tri_min_angle_deg`
    - `tri_aspect_p95`    <= `tri_aspect_p95`
    - `quad_skew_p95`     <= `quad_skew_p95`
    - `grading_p95`       <= `grading_p95`

    Parameters
    ----------
    path : str
        Path to the mesh file to read.
    wall_name : str, optional
        Name of the boundary used as the "wall" for BL and distance-to-wall metrics (default "airfoil").
    thresholds : dict, optional
        Dict overriding/adding limits (merged over `DEFAULT_THRESHOLDS`).
    include_bl : bool, optional
        If True, compute BL diagnostics (default True).

    Returns
    -------
    dict
        {
          "topology": {...},
          "valence": {...},
          "quality": {"tri": {...}, "quad": {...}},
          "sizefield": {"grading": {...}, "h_vs_distance": {...}},
          "bl": {...} or None,
          "thresholds": {...},        # the effective limits used
          "flags": {
              "ok": bool,             # overall pass/fail across all checks
              "violations": {
                 "<metric>": {"value": float, "min_allowed" or "max_allowed": float, "ok": bool},
                 ...
              }
          }
        }
    """
    # Effective thresholds
    thr = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        thr.update(thresholds)

    # Read mesh
    m = read(path)

    # Core statistics
    topo = inventory(m)
    val = valence(m)

    triq = tri_quality(m)
    quaq = quad_quality(m)

    # Sizefield metrics (call through module for static analyzers)
    grad = _sizefield.grading(m)
    hdist = _sizefield.h_vs_distance(m, wall_name=wall_name, nbins=30)

    # Boundary-layer diagnostics
    bl = None
    if include_bl:
        pres = bl_presence(m, wall_name=wall_name)
        fl = bl_first_layer(m, wall_name=wall_name, target_first_layer=None)
        gro = bl_growth(m, wall_name=wall_name, target_ratio=None, target_thickness=None)
        bl = {"presence": pres, "first_layer": fl, "growth": gro}

    # Threshold evaluation
    flags = {"violations": {}, "ok": True}

    tri_min_angle_p5 = _get(triq, "min_angle", "p5")
    if tri_min_angle_p5 is not None:
        bad = tri_min_angle_p5 < thr["tri_min_angle_deg"]
        flags["violations"]["tri_min_angle_p5"] = {
            "value": tri_min_angle_p5,
            "min_allowed": thr["tri_min_angle_deg"],
            "ok": not bad,
        }
        flags["ok"] = flags["ok"] and (not bad)

    tri_aspect_p95 = _get(triq, "aspect", "p95")
    if tri_aspect_p95 is not None:
        bad = tri_aspect_p95 > thr["tri_aspect_p95"]
        flags["violations"]["tri_aspect_p95"] = {
            "value": tri_aspect_p95,
            "max_allowed": thr["tri_aspect_p95"],
            "ok": not bad,
        }
        flags["ok"] = flags["ok"] and (not bad)

    quad_skew_p95 = _get(quaq, "skewness", "p95")
    if quad_skew_p95 is not None:
        bad = quad_skew_p95 > thr["quad_skew_p95"]
        flags["violations"]["quad_skew_p95"] = {
            "value": quad_skew_p95,
            "max_allowed": thr["quad_skew_p95"],
            "ok": not bad,
        }
        flags["ok"] = flags["ok"] and (not bad)

    grading_p95 = grad.get("p95", None)
    if grading_p95 is not None:
        bad = grading_p95 > thr["grading_p95"]
        flags["violations"]["grading_p95"] = {
            "value": grading_p95,
            "max_allowed": thr["grading_p95"],
            "ok": not bad,
        }
        flags["ok"] = flags["ok"] and (not bad)

    return {
        "topology": topo,
        "valence": val,
        "quality": {"tri": triq, "quad": quaq},
        "sizefield": {"grading": grad, "h_vs_distance": hdist},
        "bl": bl,
        "thresholds": thr,
        "flags": flags,
    }
