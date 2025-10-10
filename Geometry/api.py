# -*- coding: utf-8 -*-
# Flowxus/geometry/api.py
"""
A thin, import-only facade for Flowxus geometry.

Typical usage in main.py:
    from geometry.api import load_and_normalize, build_farfield_domain, write_geo_and_csv

    geo = load_and_normalize("naca0010.dat", translate_to_le=True, scale_to_chord1=True)
    domain = build_farfield_domain(geo, {"up":5.0, "down":5.0, "front":5.0, "back":10.0})
    write_geo_and_csv(
        domain,
        export_path="domain.geo",
        emit_metadata=True,
        emit_scalars_csv=True,
        scalars_path="airfoil_scalars.csv",
        provenance={"version": "0.4.0"},
    )
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
    Load geometry and (optionally) normalize in place.
    Returns the GeometryLoader instance (closed + CCW after load()).
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
    Build a rectangular far-field domain around the already-loaded airfoil.
    `box_dims` uses keys: {"up","down","front","back"} in *chord* units if you normalized.
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
    Emit the geometry-only .geo file and (optionally) per-vertex CSV + embedded JSON metadata.
    Returns the written .geo path.
    """
    return domain.generate_geo_file(
        export_path=export_path,
        emit_metadata=emit_metadata,
        emit_scalars_csv=emit_scalars_csv,
        scalars_path=scalars_path,
        provenance=provenance,
    )
