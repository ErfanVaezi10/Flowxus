# -*- coding: utf-8 -*-
# Flowxus/mesh/core/writer.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/29/2025

Purpose
-------
Emit a complete Gmsh `.geo` script for 2D airfoil cases by combining:
   1. pure geometry from the geometry package (airfoil + farfield box with physical groups)
   2. mesh sizing fields (near-wall taper, per-edge thresholds, optional BoundaryLayer extrusion).

Main Tasks
----------
    1. Build the geometry-only section via `emit_geometry_only_geo`:
        - Spline(1) closed on the same point id
        - Farfield rectangle (lines 1001..1004)
        - Plane Surface(100) = {100, 1} (box minus airfoil hole)
        - Physical groups: inlet/outlet/top/bottom/airfoil/fluid

    2. Append sizing fields via `emit_sizing_fields`:
        - Threshold taper from the airfoil curve using chord-scaled distances
        - Optional per-vertex MeshSize pins on airfoil points
        - Optional BoundaryLayer (Field[3]) with Quads=1 and optional FanNodesList
        - Per-edge threshold fields for box edges
        - Background Field as Min of the scalar metrics (BL runs independently)

    3. Emit minimal Gmsh meshing controls just before `Mesh 2;`:
        - Triangular surface algorithm (e.g., 6 = Frontal-Delaunay)
        - No global recombination (quads remain local to BL if enabled)

Notes:
------
    - The module does not call Gmsh itself; it only returns the text of a `.geo` that downstream
      code (runner) can pass to the Gmsh CLI.
    - The BoundaryLayer is emitted only when requested and when `n_layers > 0`.
    - The global surface meshing method is set to a triangular algorithm when BL is on, so you get
      **quad layers near the airfoil and triangles elsewhere**.
"""


import io, os, csv
from typing import Dict, Optional, Sequence, Callable
from geometry.geo.geo_writer import emit_geometry_only_geo
from .fields import emit_sizing_fields


def gmsh_geo_from_domain(
    domain,
    inflation_settings: Dict[str, float],
    mesh_size_settings: Dict[str, float],
    thickness: Optional[float] = None,
    *,
    distance_points_per_curve: int = 200,
    dist_min: float = 0.05,
    dist_max: float = 5.0,
    edge_dist_min: float = 0.0,
    edge_dist_max: float = 0.02,
    hybrid_bl: bool = True,
    airfoil_point_sizes: Optional[Sequence[float]] = None,
    scalars_csv_path: Optional[str] = None,
    size_map: Optional[Callable[[Dict[str, str]], float]] = None,
) -> str:
    """
    Construct the full `.geo` text (geometry + fields + meshing controls).

    Parameters
    ----------
    domain :
        A DomainBuilder-like object exposing:
        - `airfoil.points` (Nx2) and `airfoil.get_closed_points()`
        - `airfoil.chord_length()` (optional; bbox-based fallback used otherwise)
        - `bounding_box` dict with keys {"xmin","xmax","ymin","ymax"}
        - `physical_tags` dict with {"inlet","outlet","top","bottom","airfoil"}.

    inflation_settings : Dict[str, float]
        Boundary-layer parameters: {"first_layer", "n_layers", "growth_rate"}.
        BL is emitted only if `hybrid_bl` is True and `n_layers > 0`.

    mesh_size_settings : Dict[str, float]
        Global/edge/near-foil sizes, e.g.
        {"inlet","outlet","top","bottom","interior","airfoil"}.
        The "airfoil" entry is used as the near-wall in-plane SizeMin in the
        Threshold field (per-vertex pins, if present, still take precedence).

    thickness : float, optional
        Total BL thickness to impose. If None, it is computed from the geometric
        series (first_layer, growth_rate, n_layers) inside `emit_sizing_fields`.

    distance_points_per_curve : int, optional
        Sampling density for Gmsh Distance field along the airfoil curve.

    dist_min, dist_max : float, optional
        Chord-based taper distances (inner/outer) for the near-foil Threshold.

    edge_dist_min, edge_dist_max : float, optional
        Chord-based taper distances for per-edge Thresholds on the farfield box.

    hybrid_bl : bool, optional
        If True and `n_layers > 0`, emit a BL field with quad layers near wall.
        The farfield remains triangulated (no global recombination).

    airfoil_point_sizes : Sequence[float], optional
        Optional per-vertex target sizes for airfoil points (ids 1..N).
        If N-1 values are provided, the list is closed automatically.

    scalars_csv_path : str, optional
        CSV file path whose rows can be mapped to a size using `size_map` to
        generate `airfoil_point_sizes` automatically when the latter is not given.

    size_map : Callable[[Dict[str, str]], float], optional
        Function mapping a CSV row (as dict) to a numeric size. Only used when
        `scalars_csv_path` is provided and `airfoil_point_sizes` is None.

    Returns
    -------
    str
        The complete Gmsh `.geo` script text ready to be written to disk.

    Raises
    ------
    ValueError
        If the domain lacks airfoil geometry, or distance parameters are invalid,
        or point size arrays have inconsistent lengths.
    """
    # --- Basic validation of inputs and distances ---
    if getattr(domain, "airfoil", None) is None or getattr(domain.airfoil, "points", None) is None:
        raise ValueError("Domain has no loaded airfoil geometry. Call geo.load() before building the domain.")
    if dist_min <= 0.0 or dist_max <= 0.0 or dist_min >= dist_max:
        raise ValueError("dist_min/dist_max must be > 0 and dist_min < dist_max.")
    if edge_dist_max <= edge_dist_min:
        raise ValueError("edge_dist_max must be > edge_dist_min.")

    # --- Closed airfoil polyline (Nx2); prefer get_closed_points() when available ---
    if getattr(domain.airfoil, "get_closed_points", None) is not None:
        airfoil_pts_closed = domain.airfoil.get_closed_points()
    else:
        airfoil_pts_closed = domain.airfoil.points
    N = airfoil_pts_closed.shape[0]

    bbox = domain.bounding_box
    physical_tags = domain.physical_tags

    # --- Chord scaling for chord-based distances (robust to missing chord_length) ---
    try:
        chord = float(domain.airfoil.chord_length())
    except Exception:
        chord = float(max(1e-12, bbox["xmax"] - bbox["xmin"]))
    chord_scale = chord if chord > 0.0 else 1.0

    # --- Optional per-vertex airfoil point sizes: ensure a closed list if provided ---
    point_sizes = airfoil_point_sizes
    if point_sizes is not None:
        if len(point_sizes) == N - 1:
            point_sizes = list(point_sizes) + [point_sizes[0]]
        elif len(point_sizes) != N:
            raise ValueError(
                f"airfoil_point_sizes must have length {N} (closed) or {N-1} (open), got {len(point_sizes)}"
            )

    # --- Optionally derive per-vertex sizes from a CSV via size_map ---
    if point_sizes is None and scalars_csv_path and size_map:
        sizes = []
        try:
            with open(scalars_csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    val = size_map(row)
                    if val is not None:
                        sizes.append(float(val))
        except Exception:
            sizes = []
        if sizes and len(sizes) in (N, N - 1):
            if len(sizes) == N - 1:
                sizes.append(sizes[0])
            point_sizes = sizes

    # --- Geometry section (airfoil + box + physicals; no mesh fields here) ---
    geo_txt = emit_geometry_only_geo(
        airfoil_points_closed=airfoil_pts_closed,
        bbox=bbox,
        physical_tags=physical_tags,
    )

    # Enable BL only if requested AND there are layers
    nlayers = int(inflation_settings.get("n_layers", 0))
    hybrid_bl_eff = bool(hybrid_bl and nlayers > 0)

    # --- Fields section (BoundaryLayer is NOT part of Background Min list) ---
    fields_txt = emit_sizing_fields(
        inflation_settings=inflation_settings,
        mesh_size_settings=mesh_size_settings,
        chord_scale=chord_scale,
        thickness=thickness,
        distance_points_per_curve=distance_points_per_curve,
        dist_min=dist_min,
        dist_max=dist_max,
        edge_dist_min=edge_dist_min,
        edge_dist_max=edge_dist_max,
        hybrid_bl=hybrid_bl_eff,
        airfoil_curve_id=1,              # Spline id from geo_writer
        airfoil_point_sizes=point_sizes,
        fan_node_ids=[1],                # assume Point(1) is TE; adjust if needed
    )

    # --- Assemble final .geo ---
    buf = io.StringIO(); W = buf.write
    W("// ===== AUTO-GENERATED BY mesh.gmsh.writer =====\n\n")

    # 1) Geometry first
    W(geo_txt); W("\n")

    # 2) Then fields
    W(fields_txt); W("\n")

    # 3) Right before meshing, enforce triangle-friendly global options.
    #    The BL field will still create quads locally along the airfoil.
    if hybrid_bl_eff:
        # Use a TRIANGULAR surface algorithm; BL will still create quads locally
        # 6 = Frontal-Delaunay (triangles), 5 = Delaunay (triangles)
        W("Mesh.Algorithm = 6;\n")
        W("Mesh.RecombineAll = 0;\n")  # do NOT globally recombine
        # (Intentionally no 'Recombine Surface {100};' here)
        W("Mesh.Optimize = 1;\n")
        W("Mesh.CharacteristicLengthExtendFromBoundary = 0;\n")
        W("\n")

    # 4) Generate 2D mesh
    W("Mesh 2;\n")

    return buf.getvalue()


def write_geo_file(geo_text: str, path: str) -> str:
    """
    Write a `.geo` string to disk, creating parent directories if needed.

    Parameters
    ----------
    geo_text : str
        The complete Gmsh `.geo` script text.
    path : str
        Output file path (e.g., "mesh/mesh_ready.geo").

    Returns
    -------
    str
        The path that was written.

    Notes
    -----
    This function does no validation of the `.geo` content. It is typically
    followed by a call to the runner (`mesh.gmsh.runner.mesh_geo`) which will
    invoke the Gmsh binary and report any CLI errors.
    """
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(geo_text)
    return path
