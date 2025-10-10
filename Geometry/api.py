# -*- coding: utf-8 -*-
# Flowxus/geometry/api.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/15/2025 (Updated: 10/10/2025)

Purpose
-------
Thin, import-only façade for Flowxus geometry workflows. Exposes three high-level
helpers to (1) load and normalize an airfoil polyline, (2) construct a far-field
domain around it, and (3) emit a geometry-only `.geo` plus optional CSV/metadata.

Main Tasks
----------
    1. `load_and_normalize` → parse points, close/CCW, translate to LE, scale to chord=1.
    2. `build_farfield_domain` → create rectangular far-field box from chord-based extents.
    3. `write_geo_and_csv` → write `.geo` and optional per-vertex CSV + JSON metadata header.

Notes
-----
- This module is a convenience façade; detailed behavior lives in `geo_loader` and
  `domain_builder`. All dimensions in `box_dims` are assumed in *chord units* if you
  normalized the geometry (recommended).
"""

from typing import Dict, Optional

# Internal: needed to implement helpers (not exported in __all__)
from .geo.geo_loader import GeometryLoader       # load/normalize/plot, get_closed_points
from .domain.domain_builder import DomainBuilder # builds box + .generate_geo_file(...)

__all__ = [
    "load_and_normalize",
    "build_farfield_domain",
    "write_geo_and_csv",
]

# --------
# Helpers
# --------
def load_and_normalize(
    filename: str,
    *,
    translate_to_le: bool = True,
    scale_to_chord1: bool = True,
) -> GeometryLoader:
    """
    Load an airfoil polyline and optionally normalize in place.

    After `load()`, the geometry is closed and oriented CCW. Normalization translates
    the LE to (0, 0) and scales the chord to 1.0 if requested.

    Args
    ----
    filename : str
        Path to the geometry file (e.g., .dat, .txt).
    translate_to_le : bool, optional
        Move geometry so the leading edge is at the origin (default: True).
    scale_to_chord1 : bool, optional
        Scale geometry so the chord length equals 1.0 (default: True).

    Returns
    -------
    GeometryLoader
        Loader instance with in-memory geometry ready for domain building.
    """
    geo = GeometryLoader(filename)
    geo.load()
    geo.normalize(translate_to_le=translate_to_le, scale_to_chord1=scale_to_chord1)
    return geo


def build_farfield_domain(
    geo: GeometryLoader,
    box_dims: Dict[str, float],
) -> DomainBuilder:
    """
    Construct a rectangular far-field domain around the loaded airfoil.

    `box_dims` keys: {"up", "down", "front", "back"} measured in chord units
    if the input was normalized (recommended).

    Args
    ----
    geo : GeometryLoader
        Loaded/normalized geometry.
    box_dims : Dict[str, float]
        Extents of the far-field box in chord units.

    Returns
    -------
    DomainBuilder
        Configured domain builder capable of writing `.geo`.
    """
    return DomainBuilder(geo, box_dims)


def write_geo_and_csv(
    domain: DomainBuilder,
    *,
    export_path: str = "domain.geo",
    emit_metadata: bool = True,
    emit_scalars_csv: bool = True,
    scalars_path: str = "airfoil_scalars.csv",
    provenance: Optional[Dict[str, object]] = None,
) -> str:
    """
    Emit the geometry-only `.geo` file and optional per-vertex CSV + embedded JSON metadata.

    Args
    ----
    domain : DomainBuilder
        Domain builder returned by `build_farfield_domain`.
    export_path : str, optional
        Output path for the `.geo` file (default: "domain.geo").
    emit_metadata : bool, optional
        Insert a commented JSON header (provenance/metadata) in the `.geo` (default: True).
    emit_scalars_csv : bool, optional
        Also write a sidecar CSV with per-vertex scalars (default: True).
    scalars_path : str, optional
        Path for the scalars CSV (default: "airfoil_scalars.csv").
    provenance : Optional[Dict[str, object]], optional
        Additional provenance fields to embed in the `.geo` metadata.

    Returns
    -------
    str
        Path to the written `.geo` file.
    """
    return domain.generate_geo_file(
        export_path=export_path,
        emit_metadata=emit_metadata,
        emit_scalars_csv=emit_scalars_csv,
        scalars_path=scalars_path,
        provenance=provenance,
    )
