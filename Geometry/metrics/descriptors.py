# -*- coding: utf-8 -*-
# Flowxus/geometry/metrics/descriptors.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/24/2025

Purpose:
--------
Compute global airfoil descriptors for meshing/ML. Transforms point coordinates into
quantitative shape characteristics. Provides standardized geometric representations
for automated CFD processing and quality assessment.

Main Tasks:
-----------
    1. Validate closed polyline input.
    2. Identify LE/TE indices and split suction/pressure sides.
    3. Compute global scalars:
       - Arc length, LE radius, TE thickness and wedge angle,
       - Maximum thickness and camber (with x-locations).
    4. Package results in a dictionary for JSON/metadata export.
"""

from __future__ import division
from typing import Dict
import numpy as np
from ._num import (
    orientation as _orientation, le_te_indices as _le_te_indices,
    cumulative_arclength, curvature_polyline, assert_closed_xy,
    split_sides, interp_on_common_x, angle_deg, unit,
)


def compute_descriptors(points_closed: np.ndarray, bbox: Dict[str, float]) -> Dict[str, object]:
    """
    Returns a dict with:
      - orientation, LE_idx, TE_idx, ranges{pressure,suction}
      - bbox
      - desc: arc_length_total, LE_radius, TE_thickness, TE_wedge_angle_deg,
              thickness_max, x_thickness_max, camber_max, x_camber_max
    """
    assert_closed_xy(points_closed)
    orient = _orientation(points_closed)
    le_idx, te_idx = _le_te_indices(points_closed)

    pressure, suction, pressure_range, suction_range = split_sides(points_closed, le_idx, te_idx, orient)

    arc_total = float(cumulative_arclength(points_closed)[-1])

    kappa = curvature_polyline(points_closed, window=7)
    k_le = float(abs(kappa[le_idx]))
    le_radius = float(1.0 / k_le) if k_le > 0.0 else float("inf")

    # TE thickness from endpoints of each LE→TE path
    p_te = pressure[-1]
    s_te = suction[-1]
    te_thickness = float(np.linalg.norm(p_te - s_te))

    # TE wedge angle from end tangents on each side
    def end_tangent(path: np.ndarray) -> np.ndarray:
        if path.shape[0] >= 3:
            v = path[-1] - path[-3]
        else:
            v = path[-1] - path[-2]
        return unit(v)

    t_p = end_tangent(pressure)
    t_s = end_tangent(suction)
    if float(np.dot(t_p, t_s)) < 0:
        t_s = -t_s
    wedge = float(abs(angle_deg(t_p) - angle_deg(t_s)))
    if wedge > 180.0:
        wedge = 360.0 - wedge

    # thickness / camber over common x grid
    xg, yu, yl = interp_on_common_x(suction, pressure, n=600)
    thickness = yu - yl
    camber = 0.5 * (yu + yl)
    i_tmax = int(np.argmax(thickness))
    thickness_max = float(thickness[i_tmax])
    x_thickness_max = float(xg[i_tmax])
    i_cmax = int(np.argmax(np.abs(camber)))
    camber_max = float(camber[i_cmax])
    x_camber_max = float(xg[i_cmax])

    meta = {
        "orientation": orient,
        "LE_idx": int(le_idx + 1),
        "TE_idx": int(te_idx + 1),
        "ranges": {
            "pressure": [int(pressure_range[0]), int(pressure_range[1])],
            "suction": [int(suction_range[0]), int(suction_range[1])],
        },
        "bbox": {
            "xmin": float(bbox["xmin"]), "xmax": float(bbox["xmax"]),
            "ymin": float(bbox["ymin"]), "ymax": float(bbox["ymax"]),
        },
        "desc": {
            "arc_length_total": arc_total,
            "LE_radius": le_radius,
            "TE_thickness": te_thickness,
            "TE_wedge_angle_deg": wedge,
            "thickness_max": thickness_max,
            "x_thickness_max": x_thickness_max,
            "camber_max": camber_max,
            "x_camber_max": x_camber_max,
        },
    }
    return meta
