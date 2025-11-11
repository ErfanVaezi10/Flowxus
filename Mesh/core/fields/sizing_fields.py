# -*- coding: utf-8 -*-
# Flowxus/mesh/core/fields/sizing_fields.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Purpose:
--------
Distance and Threshold field generation for mesh size tapering.
Handles the core size transition from fine near-foil to coarse farfield.

Main Tasks:
-----------
    1. Generate Distance field to measure proximity to airfoil
    2. Create Threshold field for size tapering based on distance
    3. Handle per-vertex MeshSize pins for exact size specification
    4. Provide robust distance scaling and validation

Notes:
------
- Distance field samples curves at specified density for accuracy
- Threshold field provides smooth size transition from SizeMin to SizeMax
- All distances are scaled from chord units to model units
"""

from typing import Optional, Sequence
import io


def emit_airfoil_sizing_fields(
        airfoil_curve_id: int = 1,
        airfoil_point_sizes: Optional[Sequence[float]] = None,
        distance_points_per_curve: int = 200,
        s_airfoil: float = 0.001,
        s_far: float = 1.0,
        dmin: float = 0.05,
        dmax: float = 5.0,
) -> str:
    """
    Emit Distance and Threshold fields for near-foil size tapering.

    Parameters
    ----------
    airfoil_curve_id : int, optional
        Entity id of the airfoil spline
    airfoil_point_sizes : Sequence[float], optional
        Optional per-vertex MeshSize values for airfoil points
    distance_points_per_curve : int, optional
        Sampling density for Distance field along airfoil curve
    s_airfoil : float, optional
        Near-wall mesh size (SizeMin)
    s_far : float, optional
        Farfield mesh size (SizeMax)
    dmin : float, optional
        Inner taper distance in model units
    dmax : float, optional
        Outer taper distance in model units

    Returns
    -------
    str
        Gmsh field definitions for airfoil sizing (Fields 1 and 2)

    Notes
    -----
    - Field[1] = Distance to airfoil curve
    - Field[2] = Threshold field for size tapering
    - Returns field IDs [1, 2] for composition
    """
    buf = io.StringIO()
    W = buf.write

    # Optional per-point MeshSize pins on the airfoil
    if airfoil_point_sizes is not None and len(airfoil_point_sizes) > 0:
        W("// Per-point MeshSize on airfoil vertices (ids 1..N)\n")
        for i, h in enumerate(airfoil_point_sizes, start=1):
            W(f"MeshSize {{ {i} }} = {_fmt_float(h)};\n")
        W("\n")

    # Distance field to airfoil curve
    W("// Distance field to airfoil curve\n")
    W("Field[1] = Distance;\n")
    W(f"Field[1].CurvesList = {{{airfoil_curve_id}}};\n")
    W(f"Field[1].NumPointsPerCurve = {int(distance_points_per_curve)};\n\n")

    # Threshold field for size tapering
    W("// Threshold field for near-foil size transition\n")
    W("Field[2] = Threshold;\n")
    W("Field[2].InField = 1;\n")
    W(f"Field[2].SizeMin = {_fmt_float(s_airfoil)};\n")
    W(f"Field[2].SizeMax = {_fmt_float(s_far)};\n")
    W(f"Field[2].DistMin = {_fmt_float(dmin)};\n")
    W(f"Field[2].DistMax = {_fmt_float(dmax)};\n\n")

    return buf.getvalue()


def emit_background_field(active_field_ids: Sequence[int]) -> str:
    """
    Emit Min field and set as background field.

    Parameters
    ----------
    active_field_ids : Sequence[int]
        List of field IDs to include in Min field

    Returns
    -------
    str
        Gmsh field definition for background Min field
    """
    if not active_field_ids:
        return ""

    buf = io.StringIO()
    W = buf.write

    W("// Combine scalar metrics via Min field\n")
    W("Field[10] = Min;\n")
    W("Field[10].FieldsList = {" + ", ".join(str(fid) for fid in sorted(set(active_field_ids))) + "};\n")
    W("Background Field = 10;\n\n")

    return buf.getvalue()


def _fmt_float(x: float) -> str:
    """Format float for Gmsh compatibility."""
    return "{:.16g}".format(float(x))


def validate_distance_parameters(dmin: float, dmax: float) -> None:
    """
    Validate distance parameters for field generation.

    Parameters
    ----------
    dmin : float
        Minimum distance threshold
    dmax : float
        Maximum distance threshold

    Raises
    ------
    ValueError
        If distance parameters are invalid
    """
    if dmin <= 0 or dmax <= 0:
        raise ValueError("Distance parameters must be positive")
    if dmin >= dmax:
        raise ValueError("dmin must be less than dmax")
    if abs(dmax - dmin) < 1e-12:
        raise ValueError("Distance parameters are too close")
    
