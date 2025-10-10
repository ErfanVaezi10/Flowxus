# -*- coding: utf-8 -*-
# Flowxus/geometry/domain/domain_builder.py 

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 7/12/2025 (Updated: 10/10/2025)

Purpose
-------
    1. Build a rectangular far-field domain around an airfoil, aligned with global axes and
       referenced to the airfoil LE. Geometry-only; no meshing fields are defined here.
    2. Optional emission of **metadata** (airfoil descriptors) into the `.geo` as a commented
       JSON header, and optional writing of a **sidecar CSV** with per-vertex scalars.

New keyword arguments (opt-in):
   - emit_metadata: bool = False
   - emit_scalars_csv: bool = False
   - scalars_path: str = "airfoil_scalars.csv"
   - provenance: Optional[dict] = None  # override/add provenance fields
"""

import logging
import os
import hashlib
from datetime import datetime
from typing import Dict, Optional, List, cast
from ..geo.geo_writer import emit_geometry_only_geo
from .domain_math import (
    validate_box_dims,
    leading_edge_from_points,
    compute_box_bounds,
    default_physical_tags,
)

from geometry.metrics import (
    compute_descriptors,
    compute_per_vertex_scalars,
    dumps_metadata_json,
    write_scalars_csv,
)

logger = logging.getLogger(__name__)


class DomainBuilder:
    """
    Construct a rectangular farfield domain around an airfoil (2D).

    The domain is aligned with the global x/y axes and referenced to the airfoil
    **leading edge**. You provide distances in each direction relative to the LE:

        box_dims = {
            "up":    <float>,   # +y direction extent from LE
            "down":  <float>,   # -y direction extent from LE
            "front": <float>,   # -x direction (upstream) extent from LE
            "back":  <float>,   # +x direction (downstream) extent from LE
        }
    """

    def __init__(self, airfoil, box_dims: Dict[str, float]):
        self.airfoil = airfoil
        self.box_dims = validate_box_dims(dict(box_dims))  # validated copy

        if getattr(self.airfoil, "points", None) is None:
            raise ValueError("Airfoil geometry not loaded. Call GeometryLoader.load() first.")

        self.leading_edge = leading_edge_from_points(self.airfoil.points)
        self.bounding_box = compute_box_bounds(self.leading_edge, self.box_dims)
        self.physical_tags = default_physical_tags()

    # --------------------
    # Public API
    # --------------------
    def generate_geo_file(
        self,
        export_path: str = "domain.geo",
        *,
        emit_metadata: bool = False,
        emit_scalars_csv: bool = False,
        scalars_path: str = "airfoil_scalars.csv",
        provenance: Optional[Dict[str, object]] = None,
    ) -> str:
        """
        Write a **geometry-only** Gmsh `.geo` file.

        Optional extras (opt-in):
          - Embed a commented JSON metadata header with airfoil descriptors.
          - Write a sidecar CSV with per-vertex scalars used for meshing/ML.

        Parameters
        ----------
        export_path : str
            Path to save the `.geo` file (default "domain.geo").
        emit_metadata : bool
            If True, compute descriptors and embed metadata header in the `.geo`.
        emit_scalars_csv : bool
            If True, compute per-vertex scalars and write a CSV next to the `.geo`.
        scalars_path : str
            Output path for the CSV (default "airfoil_scalars.csv").
        provenance : Optional[dict]
            Additional/override fields to include in metadata (e.g., {"version":"0.4.0"}).

        Returns
        -------
        str
            The path that was written.
        """
        # Guard: the GeometryLoader must expose `get_closed_points`
        if getattr(self.airfoil, "get_closed_points", None) is None:
            raise ValueError("Airfoil loader missing get_closed_points().")

        airfoil_pts_closed = self.airfoil.get_closed_points()

        # --- Optional metadata & scalars ---
        metadata_json = None
        rows = None
        if emit_metadata or emit_scalars_csv:
            # Compute descriptors
            meta = compute_descriptors(airfoil_pts_closed, self.bounding_box)

            # Attach provenance defaults
            prov = {
                "units": "chord",
                "normalized": True,
                "source_file": getattr(self.airfoil, "filename", None),
                "sha256": _sha256_or_none(getattr(self.airfoil, "filename", None)),
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
            }
            if provenance:
                prov.update(provenance)
            meta.update(prov)

            if emit_metadata:
                metadata_json = dumps_metadata_json(meta)

            if emit_scalars_csv:
                ranges = cast(Dict[str, List[int]], meta["ranges"])
                le_idx = cast(int, meta["LE_idx"])
                te_idx = cast(int, meta["TE_idx"])

                rows = compute_per_vertex_scalars(
                    airfoil_pts_closed,
                    ranges,
                    le_idx,
                    te_idx,
                )
                write_scalars_csv(rows, scalars_path)
                logger.info("[DomainBuilder] Scalars CSV written to: %s", scalars_path)

        # --- Build .geo text via writer (geometry unchanged) ---
        geo_text = emit_geometry_only_geo(
            airfoil_points_closed=airfoil_pts_closed,
            bbox=self.bounding_box,
            physical_tags=self.physical_tags,
            metadata_json=metadata_json,
        )

        # Write file with explicit encoding
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(geo_text)

        logger.info("[DomainBuilder] Gmsh .geo file written to: %s", export_path)
        return export_path


# -----------------
# helpers (private)
# -----------------
def _sha256_or_none(path: Optional[str]) -> Optional[str]:
    try:
        if not path or not os.path.exists(path):
            return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None
