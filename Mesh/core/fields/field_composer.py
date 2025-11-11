# -*- coding: utf-8 -*-
# Flowxus/mesh/core/fields/field_composer.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Purpose:
--------
Orchestrates the combination of all field types into a complete field definition.
Handles field ID management, composition order, and final background field setup.

Main Tasks:
-----------
    1. Coordinate emission of all field types in correct order
    2. Manage field ID allocation and avoid conflicts
    3. Combine scalar fields into Min background field
    4. Handle BoundaryLayer field activation separately
    5. Provide the complete field definition block for .geo files

Notes:
------
- BoundaryLayer field is activated but not included in Min field
- Field IDs: 1-2 (airfoil), 3 (BL), 21-28 (edges), 10 (Min background)
- Maintains compatibility with original emit_sizing_fields function
"""

from typing import Dict, Optional, Sequence
import io
from .boundary_layer import emit_boundary_layer_field
from .sizing_fields import emit_airfoil_sizing_fields, emit_background_field
from .edge_fields import emit_all_edge_fields


def _fmt_float(x: float) -> str:
    """Format float for Gmsh compatibility."""
    return "{:.16g}".format(float(x))


def compose_fields(
        inflation_settings: Dict[str, float],
        mesh_size_settings: Dict[str, float],
        chord_scale: float,
        thickness: Optional[float] = None,
        distance_points_per_curve: int = 200,
        dist_min: float = 0.05,
        dist_max: float = 5.0,
        edge_dist_min: float = 0.0,
        edge_dist_max: float = 0.02,
        hybrid_bl: bool = True,
        airfoil_curve_id: int = 1,
        airfoil_point_sizes: Optional[Sequence[float]] = None,
        fan_node_ids: Optional[Sequence[int]] = None,
) -> str:
    """
    Compose complete field definitions from modular field components.

    Parameters
    ----------
    inflation_settings : Dict[str, float]
        Boundary layer parameters
    mesh_size_settings : Dict[str, float]
        Global and edge mesh sizes
    chord_scale : float
        Chord length in model units for distance scaling
    thickness : float, optional
        Total boundary layer thickness
    distance_points_per_curve : int, optional
        Sampling density for distance field
    dist_min, dist_max : float, optional
        Near-foil taper distances in chord lengths
    edge_dist_min, edge_dist_max : float, optional
        Edge taper distances in chord lengths
    hybrid_bl : bool, optional
        Enable hybrid boundary layer generation
    airfoil_curve_id : int, optional
        Airfoil curve entity ID
    airfoil_point_sizes : Sequence[float], optional
        Per-vertex size specifications
    fan_node_ids : Sequence[int], optional
        Fan node IDs for boundary layer

    Returns
    -------
    str
        Complete Gmsh field definitions block

    Notes
    -----
    - Maintains identical output to original emit_sizing_fields function
    - Uses modular field components for better organization
    """
    # Scale distances from chord units to model units
    dmin = dist_min * chord_scale
    dmax = dist_max * chord_scale
    edmin = edge_dist_min * chord_scale
    edmax = edge_dist_max * chord_scale

    # Validate and adjust distance parameters
    if dmin > dmax:
        dmin, dmax = dmax, dmin
    if abs(dmax - dmin) < 1e-12:
        dmax = dmin * (1.0 + 1e-6)
    if edmin > edmax:
        edmin, edmax = edmax, edmin
    if abs(edmax - edmin) < 1e-12:
        edmax = edmin * (1.0 + 1e-6)

    # Calculate farfield size
    s_inlet = float(mesh_size_settings["inlet"])
    s_outlet = float(mesh_size_settings["outlet"])
    s_top = float(mesh_size_settings["top"])
    s_bottom = float(mesh_size_settings["bottom"])
    s_interior = float(mesh_size_settings["interior"])
    s_airfoil = float(mesh_size_settings["airfoil"])
    s_far = max(s_inlet, s_outlet, s_top, s_bottom, s_interior)

    # Adjust airfoil size if needed
    if s_airfoil >= s_far:
        s_airfoil = max(1e-12, 0.99 * s_far)

    buf = io.StringIO()
    W = buf.write
    W("// --- Mesh Fields: Distance -> Threshold + (optional) BoundaryLayer (+ per-edge) ---\n")

    active_fields = [2]  # Start with airfoil threshold field (Field 2)

    # 1. Airfoil sizing fields (Fields 1-2)
    airfoil_fields = emit_airfoil_sizing_fields(
        airfoil_curve_id=airfoil_curve_id,
        airfoil_point_sizes=airfoil_point_sizes,
        distance_points_per_curve=distance_points_per_curve,
        s_airfoil=s_airfoil,
        s_far=s_far,
        dmin=dmin,
        dmax=dmax
    )
    W(airfoil_fields)

    # 2. Boundary layer field (Field 3) - activated separately
    n_layers = int(inflation_settings["n_layers"])
    if n_layers > 0:
        bl_fields = emit_boundary_layer_field(
            inflation_settings=inflation_settings,
            chord_scale=chord_scale,
            thickness=thickness,
            hybrid_bl=hybrid_bl,
            airfoil_curve_id=airfoil_curve_id,
            fan_node_ids=fan_node_ids
        )
        W(bl_fields)
        # Note: BL field (3) is NOT added to active_fields

    # 3. Edge sizing fields (Fields 21-28)
    edge_fields_text, edge_field_ids = emit_all_edge_fields(
        mesh_size_settings=mesh_size_settings,
        edmin=edmin,
        edmax=edmax,
        s_far=s_far
    )
    W(edge_fields_text)
    active_fields.extend(edge_field_ids)

    # 4. Background field (Field 10)
    background_field = emit_background_field(active_fields)
    W(background_field)

    return buf.getvalue()
