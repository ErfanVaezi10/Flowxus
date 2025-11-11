# -*- coding: utf-8 -*-
# Flowxus/mesh/core/fields/boundary_layer.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Purpose:
--------
Boundary layer field generation for structured quad extrusion near walls.
Handles Gmsh BoundaryLayer field definition with quad elements and fan nodes.

Main Tasks:
-----------
    1. Emit BoundaryLayer field definition for near-wall extrusion
    2. Configure quad elements and fan nodes for trailing edge treatment
    3. Set boundary layer parameters (first layer height, growth rate, thickness)
    4. Activate BoundaryLayer field separately from background scalar fields

Notes:
------
- BoundaryLayer field is activated explicitly, not included in Min field
- Compatible with Gmsh 4.14+ boundary layer options
- Supports hybrid meshing (quads near wall, triangles elsewhere)
"""

from typing import Dict, Optional, Sequence
import math


def emit_boundary_layer_field(
        inflation_settings: Dict[str, float],
        chord_scale: float,
        thickness: Optional[float] = None,
        hybrid_bl: bool = True,
        airfoil_curve_id: int = 1,
        fan_node_ids: Optional[Sequence[int]] = None,
) -> str:
    """
    Emit Gmsh BoundaryLayer field definition for structured quad extrusion.

    Parameters
    ----------
    inflation_settings : Dict[str, float]
        Boundary layer parameters:
        - ``first_layer`` : float > 0 — first layer height (model units)
        - ``n_layers``    : int >= 0 — number of layers (0 disables BL)
        - ``growth_rate`` : float >= 1 — geometric growth between layers
    chord_scale : float
        Chord length in model units for distance scaling
    thickness : float, optional
        Total BL thickness. If None, computed from geometric series.
    hybrid_bl : bool, optional
        If True, emit field with Quads=1 for structured layers
    airfoil_curve_id : int, optional
        Entity id of the airfoil spline (usually 1)
    fan_node_ids : Sequence[int], optional
        List of vertex ids where layers should fan (e.g., trailing edge)

    Returns
    -------
    str
        Gmsh field definition text for BoundaryLayer field

    Notes
    -----
    - The BoundaryLayer field is activated with ``BoundaryLayer Field = 3;``
    - This field is NOT included in the background Min field list
    - Returns empty string if n_layers == 0
    """
    import io

    n_layers = int(inflation_settings["n_layers"])
    if n_layers <= 0:
        return ""

    first_layer = float(inflation_settings["first_layer"])
    growth_rate = float(inflation_settings["growth_rate"])

    # Calculate BL thickness if not provided
    if thickness is None:
        if abs(growth_rate - 1.0) < 1e-12:
            bl_thickness = first_layer * n_layers
        else:
            bl_thickness = first_layer * (math.pow(growth_rate, n_layers) - 1.0) / (growth_rate - 1.0)
    else:
        bl_thickness = float(thickness)

    buf = io.StringIO()
    W = buf.write

    W("// Boundary Layer field for structured quad extrusion\n")
    W("Field[3] = BoundaryLayer;\n")
    W(f"Field[3].EdgesList = {{{airfoil_curve_id}}};\n")

    if fan_node_ids:
        W("Field[3].FanNodesList = {" + ", ".join(str(int(i)) for i in fan_node_ids) + "};\n")

    W(f"Field[3].hwall_n = {_fmt_float(first_layer)};\n")
    W(f"Field[3].ratio = {_fmt_float(growth_rate)};\n")
    W(f"Field[3].thickness = {_fmt_float(bl_thickness)};\n")
    W("Field[3].IntersectMetrics = 1;\n")
    W("Field[3].AnisoMax = 1000;\n")

    if hybrid_bl:
        W("Field[3].Quads = 1;\n")

    W("\n")
    W("// Activate BoundaryLayer field explicitly\n")
    W("BoundaryLayer Field = 3;\n\n")

    return buf.getvalue()


def _fmt_float(x: float) -> str:
    """Format float for Gmsh compatibility."""
    return "{:.16g}".format(float(x))
