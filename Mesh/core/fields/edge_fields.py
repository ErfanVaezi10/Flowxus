# -*- coding: utf-8 -*-
# Flowxus/mesh/core/fields/edge_fields.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Purpose:
--------
Per-edge sizing fields for farfield boundary refinement. Handles individual
size control for inlet, outlet, top, and bottom boundaries.

Main Tasks:
-----------
    1. Generate per-edge Distance/Threshold field pairs for farfield boundaries
    2. Provide independent size control for each boundary type
    3. Handle edge-specific size transitions and taper distances
    4. Manage field ID allocation to avoid conflicts

Notes:
------
- Each edge gets a Distance field (odd IDs) and Threshold field (even IDs)
- Field IDs start from base_id to avoid conflicts with core fields
- Edge curves are typically IDs 1001-1004 (bottom, outlet, top, inlet)
"""

from typing import Tuple
import io


def emit_edge_sizing_field(
        base_id: int,
        curve_id: int,
        size_min: float,
        size_max: float,
        dist_min: float,
        dist_max: float,
        description: str = ""
) -> Tuple[str, int]:
    """
    Emit Distance/Threshold field pair for a single edge.

    Parameters
    ----------
    base_id : int
        Base field ID (Distance field = base_id, Threshold = base_id + 1)
    curve_id : int
        Gmsh curve ID for the edge
    size_min : float
        Minimum mesh size at the edge
    size_max : float
        Maximum mesh size away from the edge
    dist_min : float
        Inner taper distance in model units
    dist_max : float
        Outer taper distance in model units
    description : str, optional
        Description for comment in output

    Returns
    -------
    Tuple[str, int]
        (field_definition_text, threshold_field_id) or empty if size_min >= size_max

    Notes
    -----
    - Returns empty string and None if size_min >= size_max (no refinement needed)
    - Distance field uses base_id, Threshold field uses base_id + 1
    """
    if size_min >= size_max:
        return "", None

    buf = io.StringIO()
    W = buf.write

    if description:
        W(f"// --- {description}: curve {curve_id} ---\n")

    # Distance field
    W(f"Field[{base_id}] = Distance;\n")
    W(f"Field[{base_id}].CurvesList = {{{curve_id}}};\n")
    W(f"Field[{base_id}].NumPointsPerCurve = 2;\n")

    # Threshold field
    threshold_id = base_id + 1
    W(f"Field[{threshold_id}] = Threshold;\n")
    W(f"Field[{threshold_id}].InField = {base_id};\n")
    W(f"Field[{threshold_id}].SizeMin = {_fmt_float(size_min)};\n")
    W(f"Field[{threshold_id}].SizeMax = {_fmt_float(size_max)};\n")
    W(f"Field[{threshold_id}].DistMin = {_fmt_float(dist_min)};\n")
    W(f"Field[{threshold_id}].DistMax = {_fmt_float(dist_max)};\n\n")

    return buf.getvalue(), threshold_id


def emit_all_edge_fields(
        mesh_size_settings: dict,
        edmin: float,
        edmax: float,
        s_far: float
) -> Tuple[str, list]:
    """
    Emit sizing fields for all farfield edges.

    Parameters
    ----------
    mesh_size_settings : dict
        Mesh size settings with keys: bottom, outlet, top, inlet
    edmin : float
        Inner taper distance for edges in model units
    edmax : float
        Outer taper distance for edges in model units
    s_far : float
        Farfield mesh size

    Returns
    -------
    Tuple[str, list]
        (combined_field_text, list_of_threshold_field_ids)

    Notes
    -----
    - Edge curve IDs: bottom=1001, outlet=1002, top=1003, inlet=1004
    - Field ID ranges: bottom(21-22), outlet(23-24), top(25-26), inlet(27-28)
    """
    buf = io.StringIO()
    active_fields = []

    # Bottom edge (1001)
    bottom_text, bottom_id = emit_edge_sizing_field(
        base_id=21, curve_id=1001,
        size_min=float(mesh_size_settings["bottom"]),
        size_max=s_far,
        dist_min=edmin, dist_max=edmax,
        description="Bottom edge sizing"
    )
    if bottom_text:
        buf.write(bottom_text)
        active_fields.append(bottom_id)

    # Outlet edge (1002)
    outlet_text, outlet_id = emit_edge_sizing_field(
        base_id=23, curve_id=1002,
        size_min=float(mesh_size_settings["outlet"]),
        size_max=s_far,
        dist_min=edmin, dist_max=edmax,
        description="Outlet edge sizing"
    )
    if outlet_text:
        buf.write(outlet_text)
        active_fields.append(outlet_id)

    # Top edge (1003)
    top_text, top_id = emit_edge_sizing_field(
        base_id=25, curve_id=1003,
        size_min=float(mesh_size_settings["top"]),
        size_max=s_far,
        dist_min=edmin, dist_max=edmax,
        description="Top edge sizing"
    )
    if top_text:
        buf.write(top_text)
        active_fields.append(top_id)

    # Inlet edge (1004)
    inlet_text, inlet_id = emit_edge_sizing_field(
        base_id=27, curve_id=1004,
        size_min=float(mesh_size_settings["inlet"]),
        size_max=s_far,
        dist_min=edmin, dist_max=edmax,
        description="Inlet edge sizing"
    )
    if inlet_text:
        buf.write(inlet_text)
        active_fields.append(inlet_id)

    return buf.getvalue(), active_fields


def _fmt_float(x: float) -> str:
    """Format float for Gmsh compatibility."""
    return "{:.16g}".format(float(x))
