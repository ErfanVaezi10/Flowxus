# -*- coding: utf-8 -*-
# Flowxus/mesh/core/writer.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/28/2025 (Updated: 11/11/2025)

Purpose:
--------
Thin orchestrator that coordinates domain processing and GEO assembly.
Maintains the original API while delegating to specialized modules.

Main Tasks:
-----------
    1. Provide backward-compatible API for existing code
    2. Orchestrate the processing → assembly pipeline
    3. Handle file I/O operations for .geo files
    4. Maintain identical function signatures as original

Notes:
------
- This module serves as a thin wrapper around processor and assembler
- All external APIs are preserved for zero breaking changes
- Internal implementation uses the new modular architecture
"""

import os
from typing import Dict, Optional, Sequence, Callable
from .processor import process_domain
from .assembler import assemble_geo_script


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

    Notes
    -----
    This function maintains backward compatibility with the original implementation
    while internally using the new modular architecture.
    """
    # Process domain data (validation and preparation)
    processed_data = process_domain(
        domain=domain,
        inflation_settings=inflation_settings,
        mesh_size_settings=mesh_size_settings,
        thickness=thickness,
        distance_points_per_curve=distance_points_per_curve,
        dist_min=dist_min,
        dist_max=dist_max,
        edge_dist_min=edge_dist_min,
        edge_dist_max=edge_dist_max,
        hybrid_bl=hybrid_bl,
        airfoil_point_sizes=airfoil_point_sizes,
        scalars_csv_path=scalars_csv_path,
        size_map=size_map,
    )

    # Assemble GEO script from processed data
    geo_script = assemble_geo_script(processed_data)

    return geo_script


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
