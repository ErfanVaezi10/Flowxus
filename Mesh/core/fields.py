# -*- coding: utf-8 -*-
# Flowxus/mesh/core/fields.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose
-------
Emit Gmsh mesh-sizing fields for a 2D airfoil-in-box domain. This includes:
   - A near-foil Threshold field based on distance to the airfoil curve.
   - Optional per-vertex MeshSize pins along the airfoil.
   - Optional BoundaryLayer extrusion (quads near wall) with fan nodes.
   - Per-edge Threshold fields for each farfield boundary.
The BoundaryLayer field is activated explicitly and kept separate from the background Min list.

Main Tasks
----------
    1. Define `Field[1]=Distance` to the airfoil spline and `Field[2]=Threshold`
       (SizeMin near wall, SizeMax far).
    2. Optionally define `Field[3]=BoundaryLayer` with Quads and FanNodesList,
       and **activate** it via `BoundaryLayer Field = 3;`.
    3. Define per-edge Distance/Threshold fields for bottom/outlet/top/inlet.
    4. Combine scalar metrics via `Field[10]=Min` and set `Background Field = 10`.

Notes:
------
    - Units: all sizes/heights are in model units; taper distances accept chord lengths
    - Gmsg compatibility: BoundaryLayer options used here are compatible with Gmsh 4.14.
"""

from typing import Dict, Sequence, Optional
import io
import math


def emit_sizing_fields(
    *,
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
    Emit the Gmsh field block (as text) controlling mesh sizes and the optional BL.

    Parameters
    ----------
    inflation_settings : Dict[str, float]
        Boundary-layer parameters:
        - ``first_layer`` : float > 0 — first layer height (model units)
        - ``n_layers``    : int >= 0 — number of layers (0 disables BL)
        - ``growth_rate`` : float >= 1 — geometric growth between layers
    mesh_size_settings : Dict[str, float]
        Global/edge/near-foil targets (model units):
        - ``inlet``, ``outlet``, ``top``, ``bottom`` : farfield edge targets
        - ``interior`` : interior size target away from the foil
        - ``airfoil``  : **near-wall in-plane** SizeMin around the foil
    chord_scale : float
        Chord length used to scale distance thresholds (``dist_min/max``,
        ``edge_dist_min/max``) from chord units to model units.
    thickness : float, optional
        Total BL thickness. If ``None``, computed from (first_layer, growth_rate,
        n_layers) using a geometric series.
    distance_points_per_curve : int, optional
        Sampling density for ``Field[1]=Distance`` along the airfoil curve.
    dist_min, dist_max : float, optional
        Inner/outer taper distances **in chord lengths** for the near-foil
        Threshold (converted internally using ``chord_scale``).
    edge_dist_min, edge_dist_max : float, optional
        Taper distances **in chord lengths** for per-edge Thresholds.
    hybrid_bl : bool, optional
        If ``True`` and ``n_layers > 0``, emit a BoundaryLayer field with
        ``Quads=1`` so layers are structured near the wall.
    airfoil_curve_id : int, optional
        Entity id of the airfoil spline (usually 1 from the geometry writer).
    airfoil_point_sizes : Sequence[float], optional
        Optional per-vertex MeshSize values for airfoil points (ids 1..N).
        If provided, these pins override the local size exactly at vertices.
    fan_node_ids : Sequence[int], optional
        Optional list of vertex ids where layers should “fan” (e.g., trailing edge).

    Returns
    -------
    str
        A string containing the Gmsh field definitions (Distance, Threshold,
        optional BoundaryLayer, per-edge fields, Min + Background Field).

    Notes
    -----
    - The BoundaryLayer field is **not** included in the Min list; it is
      **activated** with ``BoundaryLayer Field = 3;`` to avoid treating it as
      a scalar metric.
    - This text is concatenated by the writer with geometry and meshing
      controls to form a complete `.geo`.
    """
    def fmt(x) -> str:
        return "{:.16g}".format(float(x))

    # Scale distances from chord units to model units
    dmin = dist_min * chord_scale
    dmax = dist_max * chord_scale
    edmin = edge_dist_min * chord_scale
    edmax = edge_dist_max * chord_scale

    if dmin > dmax: dmin, dmax = dmax, dmin
    if abs(dmax - dmin) < 1e-12: dmax = dmin * (1.0 + 1e-6)
    if edmin > edmax: edmin, edmax = edmax, edmin
    if abs(edmax - edmin) < 1e-12: edmax = edmin * (1.0 + 1e-6)

    # Boundary-layer inputs
    first_layer = float(inflation_settings["first_layer"])
    growth_rate = float(inflation_settings["growth_rate"])
    n_layers = int(inflation_settings["n_layers"])

    # Total BL thickness (if not provided)
    if thickness is None:
        if abs(growth_rate - 1.0) < 1e-12:
            bl_thickness = first_layer * n_layers
        else:
            bl_thickness = first_layer * (math.pow(growth_rate, n_layers) - 1.0) / (growth_rate - 1.0)
    else:
        bl_thickness = float(thickness)

    # Global/edge sizes
    s_inlet    = float(mesh_size_settings["inlet"])
    s_outlet   = float(mesh_size_settings["outlet"])
    s_top      = float(mesh_size_settings["top"])
    s_bottom   = float(mesh_size_settings["bottom"])
    s_interior = float(mesh_size_settings["interior"])
    s_airfoil  = float(mesh_size_settings["airfoil"])
    s_far = max(s_inlet, s_outlet, s_top, s_bottom, s_interior)
    if s_airfoil >= s_far:
        s_airfoil = max(1e-12, 0.99 * s_far)

    buf = io.StringIO(); W = buf.write
    W("// --- Mesh Fields: Distance -> Threshold + (optional) BoundaryLayer (+ per-edge) ---\n")

    # Optional per-point MeshSize pins on the airfoil (ids 1..N)
    if airfoil_point_sizes is not None and len(airfoil_point_sizes) > 0:
        W("// Per-point MeshSize on airfoil vertices (ids 1..N)\n")
        for i, h in enumerate(airfoil_point_sizes, start=1):
            W(f"MeshSize {{ {i} }} = {fmt(h)};\n")
        W("\n")

    # Distance to airfoil curve
    W("Field[1] = Distance;\n")
    W(f"Field[1].CurvesList = {{{airfoil_curve_id}}};\n")
    W(f"Field[1].NumPointsPerCurve = {int(distance_points_per_curve)};\n\n")

    # Threshold taper based on distance to airfoil
    W("Field[2] = Threshold;\n")
    W("Field[2].InField = 1;\n")
    W(f"Field[2].SizeMin = {fmt(s_airfoil)};\n")
    W(f"Field[2].SizeMax = {fmt(s_far)};\n")
    W(f"Field[2].DistMin = {fmt(dmin)};\n")
    W(f"Field[2].DistMax = {fmt(dmax)};\n\n")

    # Background metrics (BoundaryLayer is NOT included)
    active_fields = [2]

    # Boundary layer (emit only if n_layers > 0). NOTE: no 'nLayers' for Gmsh 4.14
    if n_layers > 0:
        W("Field[3] = BoundaryLayer;\n")
        W(f"Field[3].EdgesList = {{{airfoil_curve_id}}};\n")
        if fan_node_ids:
            W("Field[3].FanNodesList = {" + ", ".join(str(int(i)) for i in fan_node_ids) + "};\n")
        W(f"Field[3].hwall_n = {fmt(first_layer)};\n")
        W(f"Field[3].ratio = {fmt(growth_rate)};\n")
        W(f"Field[3].thickness = {fmt(bl_thickness)};\n")
        W("Field[3].IntersectMetrics = 1;\n")
        W("Field[3].AnisoMax = 1000;\n")
        if hybrid_bl:
            W("Field[3].Quads = 1;\n")
        W("\n")
        # Activate BL explicitly; do NOT add it to the Min list.
        W("BoundaryLayer Field = 3;\n")

    # Per-edge sizing: bottom (1001), outlet (1002), top (1003), inlet (1004)
    def edge_block(base_id: int, curve_id: int, size_min: float, size_max: float) -> int:
        d_id = base_id
        t_id = base_id + 1
        W(f"// --- Per-edge sizing: curve {curve_id} ---\n")
        W(f"Field[{d_id}] = Distance;\n")
        W(f"Field[{d_id}].CurvesList = {{{curve_id}}};\n")
        W(f"Field[{d_id}].NumPointsPerCurve = 2;\n")
        W(f"Field[{t_id}] = Threshold;\n")
        W(f"Field[{t_id}].InField = {d_id};\n")
        W(f"Field[{t_id}].SizeMin = {fmt(size_min)};\n")
        W(f"Field[{t_id}].SizeMax = {fmt(size_max)};\n")
        W(f"Field[{t_id}].DistMin = {fmt(edmin)};\n")
        W(f"Field[{t_id}].DistMax = {fmt(edmax)};\n\n")
        return t_id  # return Threshold field id


    def maybe_edge_block(base_id, curve_id, size_min, size_max):
        return edge_block(base_id, curve_id, size_min, size_max) if size_min < size_max else None

    f_bottom = maybe_edge_block(21, 1001, s_bottom, s_far)
    f_outlet = maybe_edge_block(23, 1002, s_outlet, s_far)
    f_top = maybe_edge_block(25, 1003, s_top, s_far)
    f_inlet = maybe_edge_block(27, 1004, s_inlet, s_far)

    active_fields.extend([fid for fid in (f_bottom, f_outlet, f_top, f_inlet) if fid is not None])

    # Combine background metrics (Threshold + per-edge thresholds)
    active_fields = sorted(set(active_fields))
    W("Field[10] = Min;\n")
    W("Field[10].FieldsList = {" + ", ".join(str(fid) for fid in active_fields) + "};\n")
    W("Background Field = 10;\n\n")

    return buf.getvalue()
