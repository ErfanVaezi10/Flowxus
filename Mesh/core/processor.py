# -*- coding: utf-8 -*-
# Flowxus/mesh/core/processor.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 11/28/2025

Purpose:
--------
Domain processing and validation logic extracted from writer.py. Handles input
validation, geometry processing, and data preparation for mesh assembly.

Main Tasks:
-----------
    1. Validate domain geometry and input parameters
    2. Process airfoil geometry (closed points, chord scaling)
    3. Handle size data (CSV mapping, point size arrays)
    4. Prepare processed data structure for assembly

Notes:
------
- This module focuses purely on data processing and validation
- No Gmsh-specific logic - can be reused by any mesh generator
- Maintains identical error handling and validation as original writer.py
"""

from typing import Dict, Optional, Sequence, Callable, Any
import csv


def process_domain(domain, inflation_settings: Dict[str, float],
                   mesh_size_settings: Dict[str, float],
                   thickness: Optional[float] = None,
                   distance_points_per_curve: int = 200,
                   dist_min: float = 0.05,
                   dist_max: float = 5.0,
                   edge_dist_min: float = 0.0,
                   edge_dist_max: float = 0.02,
                   hybrid_bl: bool = True,
                   airfoil_point_sizes: Optional[Sequence[float]] = None,
                   scalars_csv_path: Optional[str] = None,
                   size_map: Optional[Callable[[Dict[str, str]], float]] = None) -> Dict[str, Any]:
    """
    Process and validate domain data for mesh generation.

    Parameters
    ----------
    domain : Any
        Domain object with airfoil geometry and bounding box
    inflation_settings : Dict[str, float]
        Boundary layer parameters
    mesh_size_settings : Dict[str, float]
        Global and edge mesh sizes
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
    airfoil_point_sizes : Sequence[float], optional
        Per-vertex size specifications
    scalars_csv_path : str, optional
        CSV file for size data mapping
    size_map : Callable, optional
        Function to map CSV data to sizes

    Returns
    -------
    Dict[str, Any]
        Processed domain data ready for assembly

    Raises
    ------
    ValueError
        If domain validation fails or parameters are invalid
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
                f"airfoil_point_sizes must have length {N} (closed) or {N - 1} (open), got {len(point_sizes)}"
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

    # Enable BL only if requested AND there are layers
    nlayers = int(inflation_settings.get("n_layers", 0))
    hybrid_bl_eff = bool(hybrid_bl and nlayers > 0)

    # --- Return processed data structure ---
    processed_data = {
        'airfoil_points_closed': airfoil_pts_closed,
        'bounding_box': bbox,
        'physical_tags': physical_tags,
        'chord_scale': chord_scale,
        'airfoil_point_sizes': point_sizes,
        'inflation_settings': inflation_settings,
        'mesh_size_settings': mesh_size_settings,
        'thickness': thickness,
        'distance_points_per_curve': distance_points_per_curve,
        'dist_min': dist_min,
        'dist_max': dist_max,
        'edge_dist_min': edge_dist_min,
        'edge_dist_max': edge_dist_max,
        'hybrid_bl': hybrid_bl_eff,
        'n_layers': nlayers,
    }

    return processed_data
