# -*- coding: utf-8 -*-
# Flowxus/geometry/metrics/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 8/21/2025

Modules:
--------
- descriptors: Compute global, chord-normalized airfoil descriptors
               (LE radius, TE thickness/wedge, max thickness/camber, arc length, orientation, ranges).

- per_vertex:  Compute per-vertex arrays for meshing/ML
               (arclength s, curvature, side masks, distances to LE/TE)
               and serialization helpers (CSV).

- _num:        Private numerical helpers shared across metrics
               (arclength, tangents, curvature, split_sides, interpolation).

Exports:
--------
- compute_descriptors
- compute_per_vertex_scalars
- write_scalars_csv
- dumps_metadata_json
"""

from __future__ import division
import json

from .descriptors import compute_descriptors
from .per_vertex import compute_per_vertex_scalars, write_scalars_csv

__all__ = [
    "compute_descriptors",
    "compute_per_vertex_scalars",
    "write_scalars_csv",
    "dumps_metadata_json",
]


def dumps_metadata_json(meta):
    """Serialize metadata dict to a compact JSON string for embedding in `.geo` comments."""
    return json.dumps(meta, separators=(",", ":"), ensure_ascii=False)
