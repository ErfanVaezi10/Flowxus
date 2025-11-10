# -*- coding: utf-8 -*-
# Flowxus/geometry/geo/geo_writer.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/15/2025 (Updated: 8/24/2025)

Purpose:
--------
Emit a geometry-only Gmsh `.geo` script for an airfoil inside a rectangular far-field box.
This mesh-agnostic module defines only geometry (points, splines, and surfaces), attaches
physical groups (inlet/outlet/top/bottom/airfoil), and does not define mesh sizing fields.
It accepts an optional `metadata_json: str = None`. When provided, a commented JSON header
is written at the top of the `.geo`.

Main Tasks:
-----------------------
    1. Emit a closed spline through the airfoil points.
    2. Define a rectangular far-field box around the geometry.
    3. Subtract the airfoil from the far-field box to form a "fluid" domain.
    4. Write consistent Physical Groups for solver compatibility.
"""

from typing import Dict, Sequence, Optional
import io


def emit_geometry_only_geo(
    airfoil_points_closed: Sequence[Sequence[float]],
    bbox: Dict[str, float],
    physical_tags: Dict[str, str],
    *,
    metadata_json: Optional[str] = None,
) -> str:
    """
    Generate Gmsh .geo script text for geometry definition.

    Produces a complete geometry specification including:
    - Optional JSON metadata header (commented)
    - Airfoil spline with topological closure
    - Rectangular far-field domain
    - Boolean operations for fluid domain
    - Physical group assignments

    Parameters
    ----------
    airfoil_points_closed : sequence of (x,y)
        Closed list of points (first point repeats at end).
    bbox : dict
        Rectangular farfield bounds with keys {"xmin","xmax","ymin","ymax"}.
    physical_tags : dict
        Physical names for Gmsh boundaries. Must include:
        {"inlet","outlet","top","bottom","airfoil"}.
    metadata_json : str or None, optional (keyword-only)
        If provided, will be written inside a commented block for downstream tools.

    Returns
    -------
    str
        Gmsh `.geo` text (geometry only, no mesh fields).
    """
    buf = io.StringIO()
    W = buf.write

    # --- Optional metadata (commented JSON) ---
    if metadata_json:
        W("// @flowxus:meta BEGIN\n")
        W("// " + str(metadata_json) + "\n")
        W("// @flowxus:meta END\n\n")

    # --- Airfoil points (write only unique vertices; skip the duplicated last) ---
    W("// --- Airfoil Points ---\n")
    n_all = len(airfoil_points_closed)
    if n_all < 3:
        raise ValueError("airfoil_points_closed must contain at least 3 points (closed list).")

    n_unique = n_all - 1  # last equals first in a closed list
    for i in range(n_unique):
        x, y = airfoil_points_closed[i]
        W("Point({}) = {{ {}, {}, 0 }};\n".format(i + 1, _fmt(x), _fmt(y)))

    # Spline must close on the *same point ID*: append '1' as the last control point
    ids_main = ", ".join(str(i) for i in range(1, n_unique + 1))  # "1,2,...,n_unique"
    W("\n")
    W("Spline(1) = { " + ids_main + ", 1 };\n")  # topologically closed
    W("Curve Loop(1) = {1};\n\n")

    # --- Farfield Box ---
    W("// --- Farfield Box ---\n")
    W("Point(1001) = {{ {}, {}, 0 }};\n".format(_fmt(bbox["xmin"]), _fmt(bbox["ymin"])))
    W("Point(1002) = {{ {}, {}, 0 }};\n".format(_fmt(bbox["xmax"]), _fmt(bbox["ymin"])))
    W("Point(1003) = {{ {}, {}, 0 }};\n".format(_fmt(bbox["xmax"]), _fmt(bbox["ymax"])))
    W("Point(1004) = {{ {}, {}, 0 }};\n".format(_fmt(bbox["xmin"]), _fmt(bbox["ymax"])))

    # Box edges
    W("Line(1001) = {1001, 1002};\n")  # bottom
    W("Line(1002) = {1002, 1003};\n")  # outlet
    W("Line(1003) = {1003, 1004};\n")  # top
    W("Line(1004) = {1004, 1001};\n")  # inlet

    W("Curve Loop(100) = {1001, 1002, 1003, 1004};\n")

    # Boolean subtraction: farfield box minus airfoil curve loop
    W("Plane Surface(100) = {100, 1}; // box minus airfoil\n\n")

    # --- Physical Groups ---
    W("// --- Physical Groups ---\n")
    W('Physical Line("{}") = {{1004}};\n'.format(physical_tags["inlet"]))
    W('Physical Line("{}") = {{1002}};\n'.format(physical_tags["outlet"]))
    W('Physical Line("{}") = {{1003}};\n'.format(physical_tags["top"]))
    W('Physical Line("{}") = {{1001}};\n'.format(physical_tags["bottom"]))
    W('Physical Line("{}") = {{1}};\n'.format(physical_tags["airfoil"]))
    W('Physical Surface("fluid") = {100};\n')

    return buf.getvalue()


def _fmt(x) -> str:
    """
    Format numbers to a compact, Gmsh-friendly representation.

    Parameters
    ----------
    x : float
        Number to format.

    Returns
    -------
    str
        String representation with ~16 digits precision.
    """
    return "{:.16g}".format(float(x))
