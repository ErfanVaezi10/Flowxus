# -*- coding: utf-8 -*-
# Flowxus/geometry/ops/__init__.py

"""
Project: Flowxus
Author: Erfan Vaezi
Date: 10/10/2025

Ops Subfolder:
--------------
Lightweight 2D geometry utilities for airfoil curve processing. Maintains stable import
paths for downstream modules while organizing functionality into logical submodules.


Contents
--------
- basic:    Foundational geometry operations including duplicate removal,
            feature detection, normalization, and arclength computation

- analysis: Advanced geometric analysis with curvature estimation and
            distance calculations along curves

- Re-exports from topology (single source of truth):
    * ensure_closed, signed_area, orientation  (geometry.topology.loop)
    * le_te_indices                            (geometry.topology.indices)

Public API
----------
Exported functions form the stable interface used by GeometryLoader, DomainBuilder,
and metrics modules. Internal implementations may change without breaking callers.
"""

from .basic import (
    drop_consecutive_duplicates, leading_edge, chord_length,
    trailing_edge, normalize, cumulative_arclength,
)
from .analysis import curvature_polyline, dist_along_curve
from ..topology.loop import signed_area, orientation, ensure_closed
from ..topology.indices import le_te_indices

__all__ = [
    # basic
    "drop_consecutive_duplicates", "leading_edge", "trailing_edge",
    "chord_length", "normalize", "cumulative_arclength",
    # topology-sourced
    "signed_area", "orientation", "ensure_closed", "le_te_indices",
    # analysis
    "curvature_polyline", "dist_along_curve",
]
